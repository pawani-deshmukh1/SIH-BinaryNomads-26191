"""
flood_inundation.py — Flood Inundation Simulation Engine
=========================================================
Simulates the spatial footprint of a flood at multiple water level scenarios
using a DEM-based bathtub model (connected flood fill).

Algorithm:
  1. Fetch elevation grid (SRTM 30m via srtm.py, cached locally after first run)
  2. Find the lowest point in the area center (approximate river source)
  3. For each water level scenario (+0.5m → +5m above river base):
       - Mark all cells at or below that elevation
       - BFS/connected-label flood fill from the river source
       - Convert the flooded mask to a GeoJSON polygon
  4. Return GeoJSON FeatureCollection with one feature per scenario

This is equivalent to the "Bathtub Model" used in rapid flood assessment.
It is not as accurate as HEC-RAS but runs in <10 seconds and is visually compelling.
"""

import numpy as np
import logging
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)


# ── DEM Fetching ──────────────────────────────────────────────────────────────

def _fetch_dem_srtm(lat_center: float, lng_center: float, radius_km: float, resolution_m: int = 300):
    """
    Fetch elevation grid using srtm.py (pure Python SRTM reader, no GDAL needed).
    Downloads SRTM tiles on first call, then uses local cache.

    Returns: (dem_array [H,W], lat_array [H], lng_array [W])
    """
    try:
        import srtm
        srtm_data = srtm.get_data()
    except ImportError:
        logger.warning("[Inundation] srtm package not installed — using synthetic DEM. "
                       "Run: pip install srtm.py")
        return _synthetic_dem(lat_center, lng_center, radius_km, resolution_m)

    delta_lat = radius_km / 111.0
    delta_lng = radius_km / (111.0 * abs(np.cos(np.radians(lat_center))) + 1e-9)

    # Grid dimensions
    n_lat = max(int(radius_km * 1000 / resolution_m), 20)
    n_lng = max(int(radius_km * 1000 / resolution_m), 20)

    lat_arr = np.linspace(lat_center - delta_lat, lat_center + delta_lat, n_lat)
    lng_arr = np.linspace(lng_center - delta_lng, lng_center + delta_lng, n_lng)

    dem = np.full((n_lat, n_lng), fill_value=np.nan, dtype=np.float32)

    logger.info(f"[Inundation] Fetching {n_lat}x{n_lng} elevation grid ...")
    for i, lat in enumerate(lat_arr):
        for j, lng in enumerate(lng_arr):
            elev = srtm_data.get_elevation(lat, lng)
            dem[i, j] = float(elev) if elev is not None else np.nan

    # Fill NaN with interpolated values (coasts, water bodies in SRTM)
    nan_mask = np.isnan(dem)
    if nan_mask.any():
        from scipy.ndimage import generic_filter
        def nanmean(v):
            vals = v[~np.isnan(v)]
            return np.mean(vals) if len(vals) > 0 else 0.0
        dem = generic_filter(dem, nanmean, size=3)
        dem = np.nan_to_num(dem, nan=0.0)

    logger.info(f"[Inundation] DEM fetched. Elevation range: {dem.min():.1f}–{dem.max():.1f}m")
    return dem, lat_arr, lng_arr


def _synthetic_dem(lat_center: float, lng_center: float, radius_km: float, resolution_m: int = 300):
    """
    Fallback synthetic DEM for testing without SRTM.
    Creates a realistic river-valley shape (low center, rising edges).
    """
    delta = radius_km / 111.0
    n = max(int(radius_km * 1000 / resolution_m), 20)

    lat_arr = np.linspace(lat_center - delta, lat_center + delta, n)
    lng_arr = np.linspace(lat_center - delta, lat_center + delta, n)

    rows, cols = np.mgrid[0:n, 0:n]
    center = n // 2

    # Valley: low along a diagonal river, rising on both sides
    dist_from_river = np.abs(rows - center - (cols - center) * 0.3)
    dem = 15.0 + dist_from_river * 0.8 + np.random.RandomState(42).uniform(0, 1, (n, n))

    logger.warning("[Inundation] Using SYNTHETIC DEM — install srtm.py for real elevation data.")
    return dem.astype(np.float32), lat_arr, lng_arr


# ── Flood Fill ────────────────────────────────────────────────────────────────

def _connected_flood_fill(dem: np.ndarray, src_row: int, src_col: int, water_level_m: float) -> np.ndarray:
    """
    BFS flood fill. Marks all cells reachable from (src_row, src_col)
    that are at or below water_level_m. Returns boolean mask.
    """
    from scipy.ndimage import label

    below = (dem <= water_level_m).astype(np.int32)
    labeled, _ = label(below, structure=np.ones((3, 3), dtype=int))

    src_label = labeled[src_row, src_col]
    if src_label == 0:
        return np.zeros_like(dem, dtype=bool)

    return labeled == src_label


def _find_river_source(dem: np.ndarray) -> tuple[int, int]:
    """
    Find the lowest elevation point in the central 20% of the DEM.
    This approximates where a river would overflow its banks.
    """
    H, W = dem.shape
    margin_h = H // 5
    margin_w = W // 5
    center_region = dem[margin_h:H - margin_h, margin_w:W - margin_w]
    local_min = np.unravel_index(np.argmin(center_region), center_region.shape)
    return local_min[0] + margin_h, local_min[1] + margin_w


# ── Mask → GeoJSON ────────────────────────────────────────────────────────────

def _mask_to_geojson(mask: np.ndarray, lat_arr: np.ndarray, lng_arr: np.ndarray) -> Optional[dict]:
    """
    Convert boolean raster mask to a GeoJSON geometry (MultiPolygon).
    Uses shapely's unary_union on grid cell polygons.
    For larger grids, uses convex hull approximation for speed.
    """
    from shapely.geometry import box, mapping
    from shapely.ops import unary_union

    rows, cols = np.where(mask)
    if len(rows) == 0:
        return None

    dlat = abs(lat_arr[1] - lat_arr[0]) / 2.0
    dlng = abs(lng_arr[1] - lng_arr[0]) / 2.0

    # For large grids, build cell polygons in batches
    if len(rows) > 2000:
        # Use convex hull of flooded points for speed (good enough for visualization)
        from shapely.geometry import MultiPoint
        pts = [(float(lng_arr[c]), float(lat_arr[r])) for r, c in zip(rows, cols)]
        geom = MultiPoint(pts).convex_hull
    else:
        cells = [
            box(float(lng_arr[c]) - dlng,
                float(lat_arr[r]) - dlat,
                float(lng_arr[c]) + dlng,
                float(lat_arr[r]) + dlat)
            for r, c in zip(rows, cols)
        ]
        geom = unary_union(cells).simplify(dlng * 0.5, preserve_topology=True)

    if geom.is_empty:
        return None

    return mapping(geom)


# ── Main Public API ───────────────────────────────────────────────────────────

def compute_inundation_scenarios(
    lat: float,
    lng: float,
    radius_km: float = 15.0,
    water_levels_m: Optional[list[float]] = None,
    resolution_m: int = 300,
) -> dict:
    """
    Compute flood inundation footprints at multiple water level scenarios.

    Args:
        lat, lng:       Center of the area to simulate
        radius_km:      Radius of the simulation area
        water_levels_m: List of water levels above the river base to simulate.
                        Default: [0.5, 1.0, 1.5, 2.0, 3.0, 5.0] meters
        resolution_m:   DEM grid resolution in meters (default 300m)

    Returns:
        GeoJSON FeatureCollection. One Feature per water level scenario.
        Each Feature's properties include:
          - water_level_above_base_m: the simulated water level
          - affected_area_km2: approximate flooded area
          - affected_habitations: placeholder (wired in the API layer)
          - scenario_label: human-readable label for UI animation
    """
    if water_levels_m is None:
        water_levels_m = [0.5, 1.0, 1.5, 2.0, 3.0, 5.0]

    logger.info(f"[Inundation] Starting simulation: center=({lat:.4f},{lng:.4f}), "
                f"radius={radius_km}km, levels={water_levels_m}")

    # 1. Fetch DEM
    dem, lat_arr, lng_arr = _fetch_dem_srtm(lat, lng, radius_km, resolution_m)

    # 2. Find river source (lowest center point)
    src_row, src_col = _find_river_source(dem)
    src_lat = float(lat_arr[src_row])
    src_lng = float(lng_arr[src_col])
    base_elev = float(dem[src_row, src_col])

    logger.info(f"[Inundation] River source: ({src_lat:.4f},{src_lng:.4f}), base elevation={base_elev:.1f}m")

    # 3. Compute per-scenario footprints
    features = []
    prev_area = 0.0

    for level in sorted(water_levels_m):
        actual_level = base_elev + level
        mask = _connected_flood_fill(dem, src_row, src_col, actual_level)

        n_cells = int(mask.sum())
        if n_cells == 0:
            logger.debug(f"[Inundation] Level +{level}m: no cells flooded")
            continue

        # Area estimate
        cell_lat_km = (lat_arr[-1] - lat_arr[0]) / len(lat_arr) * 111.0
        cell_lng_km = (lng_arr[-1] - lng_arr[0]) / len(lng_arr) * 111.0 * abs(np.cos(np.radians(lat)))
        cell_area_km2 = abs(cell_lat_km * cell_lng_km)
        area_km2 = round(n_cells * cell_area_km2, 2)
        new_area = round(area_km2 - prev_area, 2)
        prev_area = area_km2

        # Convert mask to polygon
        geom = _mask_to_geojson(mask, lat_arr, lng_arr)
        if geom is None:
            continue

        # Risk color: light blue → deep blue → red at extreme
        intensity = min(level / 5.0, 1.0)

        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "layer_type": "flood_inundation",
                "water_level_above_base_m": level,
                "absolute_water_level_m": round(actual_level, 1),
                "affected_area_km2": area_km2,
                "incremental_area_km2": max(new_area, 0.0),
                "flooded_cells": n_cells,
                "color_intensity": round(intensity, 3),
                "scenario_label": f"+{level}m water level",
                "scenario_description": _level_description(level),
                "scenario_index": len(features),
            }
        })
        logger.info(f"[Inundation] Level +{level}m: {n_cells} cells, {area_km2} km²")

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "river_source_lat": round(src_lat, 5),
            "river_source_lng": round(src_lng, 5),
            "base_elevation_m": round(base_elev, 1),
            "center_lat": lat,
            "center_lng": lng,
            "radius_km": radius_km,
            "resolution_m": resolution_m,
            "scenarios_computed": len(features),
        }
    }


def _level_description(level_m: float) -> str:
    if level_m <= 0.5:
        return "Minor overflow — low-lying paths and fields affected"
    elif level_m <= 1.0:
        return "Moderate flood — ground floors at risk"
    elif level_m <= 2.0:
        return "Major flood — habitations and roads submerged"
    elif level_m <= 3.0:
        return "Severe flood — rescue boats required"
    else:
        return "Extreme flood — complete inundation, immediate evacuation"
