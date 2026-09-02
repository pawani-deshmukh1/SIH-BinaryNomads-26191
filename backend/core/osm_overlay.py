"""
osm_overlay.py — OSM building footprint fetch with mandatory pre-caching.

OSM Overpass API can take 5-15 minutes for a fresh fetch.
Strategy:
  1. Always check local cache file first (instant).
  2. If cache miss, fetch from Overpass and write to cache.
  3. Spatial-join the damage mask polygons onto building footprints
     to assign per-building damage levels.

Cache files live in: backend/fixtures/osm_cache/
Named by bbox hash so each unique area gets its own cache file.
"""
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Cache directory — committed to repo for the demo bbox(es)
CACHE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "osm_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Demo bbox — Kedarnath area (Uttarakhand landslide/flood reference site)
DEMO_BBOX_KEDARNATH = (79.0469, 30.7146, 79.0869, 30.7546)  # (min_lng, min_lat, max_lng, max_lat)

# Demo bbox — Assam flood region (Nagaon district)
DEMO_BBOX_ASSAM = (92.63, 26.32, 92.70, 26.39)


def _bbox_cache_key(bbox: tuple[float, float, float, float]) -> str:
    """Generate a stable filename key from a bounding box."""
    key = f"{bbox[0]:.4f}_{bbox[1]:.4f}_{bbox[2]:.4f}_{bbox[3]:.4f}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def _cache_path(bbox: tuple) -> Path:
    return CACHE_DIR / f"buildings_{_bbox_cache_key(bbox)}.geojson"


def load_cached_buildings(bbox: tuple) -> Optional[dict]:
    """Load pre-cached OSM buildings GeoJSON if available."""
    path = _cache_path(bbox)
    if path.exists():
        logger.info(f"[OSM] Cache hit: {path.name}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_buildings_cache(bbox: tuple, geojson: dict) -> None:
    """Save fetched OSM data to local cache."""
    path = _cache_path(bbox)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(geojson, f)
    logger.info(f"[OSM] Cache written: {path.name} ({len(geojson.get('features', []))} buildings)")


def fetch_buildings_overpass(bbox: tuple[float, float, float, float]) -> dict:
    """
    Fetch building footprints from Overpass API.
    bbox: (min_lng, min_lat, max_lng, max_lat)
    WARNING: this can take 5-15 minutes on cold cache. Always try load_cached_buildings() first.
    """
    import requests

    min_lng, min_lat, max_lng, max_lat = bbox
    # Overpass uses (south, west, north, east)
    overpass_bbox = f"{min_lat},{min_lng},{max_lat},{max_lng}"

    query = f"""
    [out:json][timeout:120];
    (
      way["building"]({overpass_bbox});
      relation["building"]({overpass_bbox});
    );
    out body geom;
    """

    url = "https://overpass-api.de/api/interpreter"
    logger.info(f"[OSM] Fetching from Overpass for bbox {bbox} — this may take several minutes...")

    headers = {
        "User-Agent": "DISHA-DisasterResponse-SIH2026/1.0",
        "Accept": "application/json"
    }

    try:
        resp = requests.post(url, data={"data": query}, headers=headers, timeout=180)
        resp.raise_for_status()
        osm_data = resp.json()
    except Exception as e:
        logger.error(f"[OSM] Overpass fetch failed: {e}")
        return {"type": "FeatureCollection", "features": []}

    features = []
    for element in osm_data.get("elements", []):
        if element["type"] == "way" and "geometry" in element:
            coords = [[pt["lon"], pt["lat"]] for pt in element["geometry"]]
            if len(coords) < 4:
                continue
            if coords[0] != coords[-1]:
                coords.append(coords[0])  # close ring

            tags = element.get("tags", {})
            feature = {
                "type": "Feature",
                "properties": {
                    "osm_id": f"way/{element['id']}",
                    "building": tags.get("building", "yes"),
                    "name": tags.get("name", ""),
                    "amenity": tags.get("amenity", ""),
                    "layer_type": "osm_building",
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [coords],
                },
            }
            features.append(feature)

    geojson = {"type": "FeatureCollection", "features": features}
    logger.info(f"[OSM] Fetched {len(features)} buildings from Overpass")
    return geojson


def get_buildings(bbox: tuple[float, float, float, float], allow_fetch: bool = True) -> dict:
    """
    Get OSM buildings for a bbox. Always checks cache first.
    If cache miss and allow_fetch=True, fetches from Overpass (slow!).
    If cache miss and allow_fetch=False, returns empty FeatureCollection.
    """
    cached = load_cached_buildings(bbox)
    if cached is not None:
        return cached

    if not allow_fetch:
        logger.warning(f"[OSM] No cache for bbox {bbox} and fetch disabled — returning empty")
        return {"type": "FeatureCollection", "features": []}

    logger.warning(f"[OSM] No cache found — fetching from Overpass (SLOW). Pre-cache with: python -m backend.core.osm_overlay prefetch")
    data = fetch_buildings_overpass(bbox)
    if data["features"]:
        save_buildings_cache(bbox, data)
    return data


def overlay_damage_on_buildings(
    damage_features: list[dict],
    buildings_geojson: dict,
) -> list[dict]:
    """
    Spatially join damage polygons onto OSM building footprints.
    Each building gets a damage_level property: 'none' | 'minor_damage' | 'destroyed'

    Returns a list of GeoJSON Features (one per building that has damage).
    Buildings with no damage overlap are omitted to keep the output clean.
    """
    if not buildings_geojson.get("features"):
        return []
    if not damage_features:
        return []

    try:
        import geopandas as gpd
        from shapely.geometry import shape
    except ImportError:
        logger.error("[OSM] geopandas/shapely not available — skipping building overlay")
        return []

    now = datetime.now(timezone.utc).isoformat()

    # Build GeoDataFrame for buildings
    try:
        buildings_gdf = gpd.GeoDataFrame.from_features(buildings_geojson["features"], crs="EPSG:4326")
    except Exception as e:
        logger.error(f"[OSM] Failed to build buildings GDF: {e}")
        return []

    if buildings_gdf.empty:
        return []

    # Build GeoDataFrame for damage zones (only minor/destroyed classes)
    damage_gdf_rows = []
    for feat in damage_features:
        props = feat.get("properties", {})
        label = props.get("label", "")
        if label not in ("minor_damage", "destroyed"):
            continue
        try:
            geom = shape(feat["geometry"])
            damage_gdf_rows.append({"label": label, "confidence": props.get("confidence", 0.0), "geometry": geom})
        except Exception:
            continue

    if not damage_gdf_rows:
        return []

    damage_gdf = gpd.GeoDataFrame(damage_gdf_rows, crs="EPSG:4326")

    # Spatial join: find which buildings intersect which damage zones
    try:
        joined = gpd.sjoin(buildings_gdf, damage_gdf[["label", "confidence", "geometry"]], how="left", predicate="intersects")
    except Exception as e:
        logger.error(f"[OSM] Spatial join failed: {e}")
        return []

    # For buildings hit by multiple damage zones, take worst label
    label_priority = {"destroyed": 2, "minor_damage": 1, "none": 0}

    result_features = []
    seen_osm_ids = set()

    for osm_id, group in joined.groupby("osm_id"):
        if osm_id in seen_osm_ids:
            continue
        seen_osm_ids.add(osm_id)

        # Find worst damage label for this building
        best_label = "none"
        best_conf = 0.0
        for _, row in group.iterrows():
            lbl = row.get("label", "none") if not (hasattr(row, "isna") and row.isna().get("label", False)) else "none"
            if lbl and label_priority.get(lbl, 0) > label_priority.get(best_label, 0):
                best_label = lbl
                best_conf = float(row.get("confidence", 0.0))

        if best_label == "none":
            continue  # skip undamaged buildings

        # Get building geometry
        building_rows = buildings_gdf[buildings_gdf["osm_id"] == osm_id]
        if building_rows.empty:
            continue

        building_row = building_rows.iloc[0]
        try:
            from shapely.geometry import mapping
            geom = mapping(building_row.geometry)
        except Exception:
            continue

        feature = {
            "type": "Feature",
            "properties": {
                "layer_type": "building_damage",
                "osm_id": osm_id,
                "damage_level": best_label,
                "confidence": round(best_conf, 4),
                "building_type": building_row.get("building", "yes"),
                "name": building_row.get("name", ""),
                "last_updated": now,
            },
            "geometry": geom,
        }
        result_features.append(feature)

    logger.info(f"[OSM] Building overlay: {len(result_features)} damaged buildings identified")
    return result_features


# ─── CLI prefetch tool ────────────────────────────────────────────────────────

def prefetch_demo_areas():
    """
    Pre-fetch and cache OSM data for all known demo areas.
    Run this ONCE before the demo:
        python -m backend.core.osm_overlay
    Takes ~10-15 min total but only needs to run once.
    """
    demo_areas = [
        ("Kedarnath (Uttarakhand)", DEMO_BBOX_KEDARNATH),
        ("Assam Flood Region (Nagaon)", DEMO_BBOX_ASSAM),
    ]
    for name, bbox in demo_areas:
        print(f"\n[Prefetch] {name} — bbox {bbox}")
        cached = load_cached_buildings(bbox)
        if cached:
            print(f"  [OK] Already cached ({len(cached.get('features', []))} buildings)")
            continue
        print(f"  [WAIT] Fetching from Overpass (may take several minutes)...")
        data = fetch_buildings_overpass(bbox)
        if data["features"]:
            save_buildings_cache(bbox, data)
            print(f"  [OK] Cached {len(data['features'])} buildings")
        else:
            print(f"  [WARN] No buildings returned — check your internet connection")

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    print("DISHA — OSM Cache Prefetch Tool")
    print("=" * 40)
    prefetch_demo_areas()
    print("\n[OK] Done. Cache files saved to backend/fixtures/osm_cache/")
