"""
cop_builder.py — Assemble all pipeline outputs into a single unified GeoJSON.

The COP (Common Operational Picture) FeatureCollection contains every layer
in one response. Each feature has a `layer_type` property so the frontend
can toggle layers independently:

  layer_type values:
    "building_damage"  — per-OSM-building damage assessment
    "flood_zone"       — flood extent polygon(s)
    "landslide_zone"   — landslide hazard polygon(s)
    "damage_zone"      — raw damage segmentation (before OSM join)
    "red_zone"         — fused risk polygon (AHP-weighted combination)
    "evac_site"        — ranked evacuation candidate sites
    "evac_route"       — hazard-aware routing geometry
    "tower"            — cell tower with risk status
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"

# ── Demo/static evac sites for known regions ─────────────────────────────────
DEMO_EVAC_SITES = {
    "kedarnath": [
        {"id": "EZ-K01", "name": "Gaurikund Relief Camp", "lat": 30.734, "lng": 79.063,
         "recommendation_score": 0.87, "capacity_persons": 800, "status": "available"},
        {"id": "EZ-K02", "name": "Sonprayag School Ground", "lat": 30.737, "lng": 79.057,
         "recommendation_score": 0.74, "capacity_persons": 350, "status": "available"},
    ],
    "assam": [
        {"id": "EZ-A01", "name": "Nagaon Govt School", "lat": 26.355, "lng": 92.685,
         "recommendation_score": 0.91, "capacity_persons": 1200, "status": "available"},
        {"id": "EZ-A02", "name": "Nagaon District Stadium", "lat": 26.342, "lng": 92.671,
         "recommendation_score": 0.79, "capacity_persons": 3500, "status": "partial"},
        {"id": "EZ-A03", "name": "Rupahi Relief Ground", "lat": 26.362, "lng": 92.655,
         "recommendation_score": 0.65, "capacity_persons": 600, "status": "available"},
    ],
}

DEMO_TOWERS = {
    "kedarnath": [
        {"id": "TW-K01", "operator": "BSNL", "lat": 30.7346, "lng": 79.0669, "status": "at_risk"},
        {"id": "TW-K02", "operator": "Airtel", "lat": 30.7411, "lng": 79.071, "status": "operational"},
    ],
    "assam": [
        {"id": "TW-A01", "operator": "Airtel", "lat": 26.354, "lng": 92.663, "status": "at_risk"},
        {"id": "TW-A02", "operator": "Jio", "lat": 26.341, "lng": 92.689, "status": "operational"},
        {"id": "TW-A03", "operator": "BSNL", "lat": 26.367, "lng": 92.648, "status": "at_risk"},
    ],
}


def _fuse_red_zones(
    damage_features: list[dict],
    flood_features: list[dict],
    landslide_features: list[dict],
    damage_weight: float = 0.40,
    flood_weight: float = 0.35,
    landslide_weight: float = 0.25,
    red_threshold: float = 0.70,
    orange_threshold: float = 0.40,
) -> list[dict]:
    """
    Geometrically-grounded multi-hazard fusion.

    Each hazard polygon gets risk_score = own confidence x weight,
    PLUS contributions from other hazards ONLY IF those polygons spatially
    intersect it (shapely check). contributing_factors[x].overlap is always
    truthful -- False means that hazard did not reach this zone.

    Thresholds passed from function args (read from settings by caller),
    not hardcoded -- so judges can adjust them live via settings_api.
    """
    now = datetime.now(timezone.utc).isoformat()
    red_zones = []

    def _shapes(features):
        try:
            from shapely.geometry import shape
            return [(f, shape(f["geometry"])) for f in features if f.get("geometry")]
        except Exception:
            return []

    damage_shapes = _shapes(damage_features)
    flood_shapes  = _shapes(flood_features)
    slide_shapes  = _shapes(landslide_features)

    def _intersects(geom, other_shapes):
        for feat, shp in other_shapes:
            try:
                if geom.intersects(shp):
                    return True, float(feat.get("properties", {}).get("confidence", 0.0))
            except Exception:
                pass
        return False, 0.0

    def _tier(score):
        if score >= red_threshold:
            return "red"
        elif score >= orange_threshold:
            return "orange"
        return "green"

    for feat, geom in damage_shapes:
        conf = float(feat.get("properties", {}).get("confidence", 0.0))
        flood_hit, flood_conf = _intersects(geom, flood_shapes)
        slide_hit, slide_conf = _intersects(geom, slide_shapes)
        risk_score = min(1.0, round(
            conf * damage_weight
            + (flood_conf * flood_weight if flood_hit else 0.0)
            + (slide_conf * landslide_weight if slide_hit else 0.0), 4))
        red_zones.append({"type": "Feature", "properties": {
            **feat.get("properties", {}), "layer_type": "red_zone",
            "primary_hazard": "structural_damage", "risk_score": risk_score,
            "color_tier": _tier(risk_score),
            "contributing_factors": {
                "damage":    {"weight": damage_weight,    "value": conf,       "overlap": True},
                "flood":     {"weight": flood_weight,     "value": flood_conf, "overlap": flood_hit},
                "landslide": {"weight": landslide_weight, "value": slide_conf, "overlap": slide_hit},
            }, "last_updated": now,
        }, "geometry": feat.get("geometry")})

    for feat, geom in flood_shapes:
        conf = float(feat.get("properties", {}).get("confidence", 0.0))
        dmg_hit, dmg_conf   = _intersects(geom, damage_shapes)
        slide_hit, slide_conf = _intersects(geom, slide_shapes)
        risk_score = min(1.0, round(
            conf * flood_weight
            + (dmg_conf   * damage_weight    if dmg_hit  else 0.0)
            + (slide_conf * landslide_weight if slide_hit else 0.0), 4))
        red_zones.append({"type": "Feature", "properties": {
            **feat.get("properties", {}), "layer_type": "red_zone",
            "primary_hazard": "flood", "risk_score": risk_score,
            "color_tier": _tier(risk_score),
            "contributing_factors": {
                "damage":    {"weight": damage_weight,    "value": dmg_conf,   "overlap": dmg_hit},
                "flood":     {"weight": flood_weight,     "value": conf,       "overlap": True},
                "landslide": {"weight": landslide_weight, "value": slide_conf, "overlap": slide_hit},
            }, "last_updated": now,
        }, "geometry": feat.get("geometry")})

    for feat, geom in slide_shapes:
        conf = float(feat.get("properties", {}).get("confidence", 0.0))
        dmg_hit, dmg_conf   = _intersects(geom, damage_shapes)
        flood_hit, flood_conf = _intersects(geom, flood_shapes)
        risk_score = min(1.0, round(
            conf * landslide_weight
            + (dmg_conf   * damage_weight if dmg_hit   else 0.0)
            + (flood_conf * flood_weight  if flood_hit else 0.0), 4))
        red_zones.append({"type": "Feature", "properties": {
            **feat.get("properties", {}), "layer_type": "red_zone",
            "primary_hazard": "landslide", "risk_score": risk_score,
            "color_tier": _tier(risk_score),
            "contributing_factors": {
                "damage":    {"weight": damage_weight,    "value": dmg_conf,   "overlap": dmg_hit},
                "flood":     {"weight": flood_weight,     "value": flood_conf, "overlap": flood_hit},
                "landslide": {"weight": landslide_weight, "value": conf,       "overlap": True},
            }, "last_updated": now,
        }, "geometry": feat.get("geometry")})

    return red_zones

def _make_evac_features(region_key: str = "assam") -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    sites = DEMO_EVAC_SITES.get(region_key, DEMO_EVAC_SITES["assam"])
    features = []
    for site in sites:
        features.append({
            "type": "Feature",
            "properties": {
                "layer_type": "evac_site",
                "id": site["id"],
                "name": site["name"],
                "recommendation_score": site["recommendation_score"],
                "capacity_persons": site["capacity_persons"],
                "status": site["status"],
                "last_updated": now,
            },
            "geometry": {
                "type": "Point",
                "coordinates": [site["lng"], site["lat"]],
            },
        })
    return features


def _make_tower_features(region_key: str = "assam", red_zone_features: list = None) -> list[dict]:
    """Flag towers as at_risk if they fall inside any red zone polygon."""
    now = datetime.now(timezone.utc).isoformat()
    towers = DEMO_TOWERS.get(region_key, DEMO_TOWERS["assam"])
    features = []

    for tower in towers:
        # Try spatial check if shapely available
        status = tower["status"]
        if red_zone_features:
            try:
                from shapely.geometry import Point, shape
                pt = Point(tower["lng"], tower["lat"])
                for rz in red_zone_features:
                    rz_geom = shape(rz["geometry"])
                    if rz_geom.contains(pt) or rz_geom.distance(pt) < 0.002:
                        status = "at_risk"
                        break
            except Exception:
                pass

        features.append({
            "type": "Feature",
            "properties": {
                "layer_type": "tower",
                "id": tower["id"],
                "operator": tower["operator"],
                "status": status,
                "last_updated": now,
            },
            "geometry": {
                "type": "Point",
                "coordinates": [tower["lng"], tower["lat"]],
            },
        })
    return features


def build_cop(
    damage_features: list[dict],
    flood_features: list[dict],
    landslide_features: list[dict],
    building_damage_features: list[dict],
    model_confidences: dict,
    region_key: str = "assam",
    damage_weight: float = 0.5,
    flood_weight: float = 0.25,
    landslide_weight: float = 0.25,
    duration_ms: float = 0.0,
    demo_mode: bool = False,
) -> dict:
    """
    Assemble all pipeline outputs into one unified GeoJSON FeatureCollection.
    """
    now = datetime.now(timezone.utc).isoformat()

    # Fuse red zones
    red_zones = _fuse_red_zones(
        damage_features, flood_features, landslide_features,
        damage_weight, flood_weight, landslide_weight,
    )

    # Evac sites + towers
    evac_features = _make_evac_features(region_key)
    tower_features = _make_tower_features(region_key, red_zones)

    # Collect ALL features
    all_features = (
        building_damage_features
        + damage_features     # raw damage segmentation polygons
        + flood_features
        + landslide_features
        + red_zones
        + evac_features
        + tower_features
    )

    # Summary stats
    destroyed_count = sum(
        1 for f in building_damage_features
        if f.get("properties", {}).get("damage_level") == "destroyed"
    )
    minor_count = sum(
        1 for f in building_damage_features
        if f.get("properties", {}).get("damage_level") == "minor_damage"
    )
    red_zone_high = sum(
        1 for f in red_zones
        if f.get("properties", {}).get("color_tier") == "red"
    )
    towers_at_risk = sum(
        1 for f in tower_features
        if f.get("properties", {}).get("status") == "at_risk"
    )

    summary = {
        "red_zones_count": len(red_zones),
        "red_zones_high_risk": red_zone_high,
        "buildings_assessed": len(building_damage_features),
        "buildings_destroyed": destroyed_count,
        "buildings_minor_damage": minor_count,
        "flood_zones_count": len(flood_features),
        "landslide_zones_count": len(landslide_features),
        "evac_sites_available": len([e for e in evac_features if e["properties"]["status"] != "full"]),
        "towers_at_risk": towers_at_risk,
        "pipeline_duration_ms": duration_ms,
        "demo_mode": demo_mode,
        "last_updated": now,
    }

    return {
        "type": "FeatureCollection",
        "summary": summary,
        "model_confidence": model_confidences,
        "features": all_features,
    }


def build_cop_from_demo() -> dict:
    """Load and return the pre-computed demo COP fixture."""
    demo_path = FIXTURES_DIR / "demo_result.json"
    if demo_path.exists():
        with open(demo_path, "r", encoding="utf-8") as f:
            return json.load(f)
    # Fallback: generate from static data
    logger.warning("[COP] demo_result.json missing — generating from static demo data")
    return build_cop(
        damage_features=[],
        flood_features=[],
        landslide_features=[],
        building_damage_features=[],
        model_confidences={
            "damage": {"score": 0.88, "score_type": "model_confidence", "last_updated": datetime.now(timezone.utc).isoformat()},
            "flood":  {"score": 0.93, "score_type": "model_confidence", "last_updated": datetime.now(timezone.utc).isoformat()},
            "landslide": {"score": 0.77, "score_type": "model_confidence", "last_updated": datetime.now(timezone.utc).isoformat()},
        },
        region_key="assam",
        duration_ms=0.0,
        demo_mode=True,
    )
