import logging
import math
import time
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import json
import os

from core.flood_inundation import compute_inundation_scenarios
from core.hazard_trigger import get_live_weather_trigger

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/simulation", tags=["3D Growth Simulation"])

# Base water level increments in meters per stage
# (Assuming baseline overflow at T+0 is 0.5m)
STAGE_HOURS = [0, 6, 18, 36]

# Static fallback water levels (used only when Open-Meteo is unavailable)
FALLBACK_WATER_LEVELS = {0: 0.5, 6: 1.5, 18: 3.0, 36: 5.0}

# Runoff/basin parameters for Brahmaputra tributary floodplains
RUNOFF_COEFFICIENT  = 0.65   # flat agricultural land in Assam (standard)
BASIN_FACTOR        = 0.009  # empirical for small Brahmaputra char tributaries
CHANNEL_WIDTH_M     = 50     # avg channel width (m) for Manning's approximation
MANNINGS_C          = 25     # roughness coeff for braided rivers

# ── API Caching ─────────────────────────────────────────────────────────────
# Cache API responses for 1 hour to prevent timeouts and rate limiting
CACHE_TTL_SECONDS = 3600
_GLOFAS_CACHE = {}  # {(lat, lng): (timestamp, discharge_series)}
_RAIN_CACHE = {}    # {(lat, lng): (timestamp, hourly_rain)}


async def _get_openmeteo_water_levels(lat: float, lng: float, risk_multiplier: float) -> list:
    """
    3-level fallback chain for real water level data.

    Level 1 (PRIMARY): Open-Meteo Flood API - GloFAS v4 river discharge (m3/s)
                       No API key. 30-day forecast. Covers Brahmaputra and all
                       its tributaries in Assam. Free for non-commercial use.
                       https://flood-api.open-meteo.com/v1/flood
    Level 2 (FALLBACK): Open-Meteo precipitation -> Manning rational method
    Level 3 (OFFLINE):  Static hardcoded values scaled by risk_multiplier
    """
    import httpx

    # ── Level 1: GloFAS river discharge (Open-Meteo Flood API, no key needed) ─
    try:
        now = time.time()
        cache_key = (round(lat, 3), round(lng, 3))
        
        # Check cache first
        if cache_key in _GLOFAS_CACHE and (now - _GLOFAS_CACHE[cache_key][0]) < CACHE_TTL_SECONDS:
            discharge_series = _GLOFAS_CACHE[cache_key][1]
            logger.info("[Simulation] Using cached GloFAS discharge")
        else:
            flood_url = (
                "https://flood-api.open-meteo.com/v1/flood"
                f"?latitude={lat}&longitude={lng}"
                "&daily=river_discharge&forecast_days=7"
            )
            async with httpx.AsyncClient() as client:
                resp = await client.get(flood_url, timeout=6.0)

            if resp.status_code != 200:
                raise ValueError(f"HTTP {resp.status_code}")
                
            discharge_series = resp.json().get("daily", {}).get("river_discharge", [])
            if not discharge_series:
                raise ValueError("Empty discharge series from GloFAS")
                
            _GLOFAS_CACHE[cache_key] = (now, discharge_series)

        if len(discharge_series) >= 2:
            # Map T+hours to approximate day index in the daily GloFAS series
            day_map = {0: 0, 6: 0, 18: 1, 36: 2}
            levels = []

            for hour in STAGE_HOURS:
                day_idx = min(day_map[hour], len(discharge_series) - 1)
                Q = float(discharge_series[day_idx] or 0.0)

                # Manning depth from discharge: h = (Q / (width * C))^0.6
                # 200m width / C=20 for main river reported by GloFAS
                h = (max(Q, 1.0) / (200 * 20)) ** 0.6
                h_scaled = min(8.0, round(h * risk_multiplier, 2))
                if levels:
                    h_scaled = max(h_scaled, levels[-1])
                levels.append(h_scaled)

            levels[0] = max(0.3, levels[0])
            logger.info(
                "[Simulation] GloFAS Q=%.1fm3/s -> levels: %s",
                discharge_series[0], levels
            )
            return levels
        raise ValueError("Invalid discharge series from GloFAS")

    except Exception as e:
        logger.warning("[Simulation] Level 1 GloFAS failed: %s - trying Level 2", e)

    # ── Level 2: Rainfall -> Manning rational method ───────────────────────────
    try:
        if cache_key in _RAIN_CACHE and (time.time() - _RAIN_CACHE[cache_key][0]) < CACHE_TTL_SECONDS:
            hourly_rain = _RAIN_CACHE[cache_key][1]
            logger.info("[Simulation] Using cached Open-Meteo rainfall")
        else:
            rain_url = (
                "https://api.open-meteo.com/v1/forecast"
                f"?latitude={lat}&longitude={lng}"
                "&hourly=precipitation&forecast_days=2"
            )
            async with httpx.AsyncClient() as client:
                resp = await client.get(rain_url, timeout=6.0)

            if resp.status_code != 200:
                raise ValueError(f"HTTP {resp.status_code}")

            hourly_rain = resp.json().get("hourly", {}).get("precipitation", [])
            _RAIN_CACHE[cache_key] = (time.time(), hourly_rain)

        levels = []

        for hour in STAGE_HOURS:
            cumulative_mm = sum(hourly_rain[:max(1, hour)])
            runoff_mm = cumulative_mm * RUNOFF_COEFFICIENT
            catchment_m2 = 10_000_000
            duration_s = max(3600, hour * 3600)
            Q = (runoff_mm / 1000) * catchment_m2 / duration_s
            h = (Q / (CHANNEL_WIDTH_M * MANNINGS_C)) ** 0.6 if Q > 0 else FALLBACK_WATER_LEVELS[hour]
            h_scaled = min(8.0, round(h * risk_multiplier, 2))
            if levels:
                h_scaled = max(h_scaled, levels[-1])
            levels.append(h_scaled)

        levels[0] = max(0.3, levels[0])
        logger.info("[Simulation] Level 2 rainfall -> levels: %s", levels)
        return levels

    except Exception as e:
        logger.warning("[Simulation] Level 2 rainfall failed: %s - Level 3 static", e)

    # ── Level 3: Static fallback ───────────────────────────────────────────────
    logger.info("[Simulation] Level 3: static fallback")
    return [
        round(FALLBACK_WATER_LEVELS[h] * (risk_multiplier if h > 0 else 1.0), 2)
        for h in STAGE_HOURS
    ]

# Base landslide cone radius in km per stage
BASE_LANDSLIDE_RADIUS = {
    0: 0.3,
    6: 0.8,
    18: 1.5,
    36: 2.5
}

def load_habitation(hab_id: str):
    fixtures_dir = os.path.join(os.path.dirname(__file__), "..", "fixtures")
    with open(os.path.join(fixtures_dir, "habitations_assam.json"), "r", encoding="utf-8") as f:
        habitations = json.load(f)
        for hab in habitations:
            if hab["id"] == hab_id:
                return hab
    return None

def build_landslide_cone(lat, lng, aspect_deg, radius_km, risk_multiplier):
    """
    Build a GeoJSON polygon representing a risk cone pointing downhill.
    """
    from shapely.geometry import Point, Polygon, mapping
    import pyproj
    
    # Scale radius by risk
    scaled_radius_km = radius_km * risk_multiplier
    
    # 30 degrees each side of the downhill aspect
    half_angle = 30.0
    start_angle = (aspect_deg - half_angle) % 360
    end_angle = (aspect_deg + half_angle) % 360
    
    # Create the wedge using geodetic calculation
    geodesic = pyproj.Geod(ellps='WGS84')
    
    points = [(lng, lat)] # Apex
    
    # Generate points along the arc
    num_points = 10
    
    # Handle angle wrapping
    if start_angle > end_angle:
        angles = list(range(int(start_angle), 360)) + list(range(0, int(end_angle) + 1))
    else:
        angles = list(range(int(start_angle), int(end_angle) + 1))
        
    step = max(1, len(angles) // num_points)
    selected_angles = [angles[i] for i in range(0, len(angles), step)]
    if angles[-1] not in selected_angles:
        selected_angles.append(angles[-1])
        
    for angle in selected_angles:
        # Forward azimuth calculates destination given dist and bearing
        # Geod uses bearing from north clockwise
        lon2, lat2, _ = geodesic.fwd(lng, lat, angle, scaled_radius_km * 1000)
        points.append((lon2, lat2))
        
    points.append((lng, lat)) # Close polygon
    
    polygon = Polygon(points)
    
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": mapping(polygon),
                "properties": {
                    "layer_type": "landslide_cone",
                    "radius_km": round(scaled_radius_km, 2),
                    "aspect_deg": aspect_deg
                }
            }
        ]
    }

@router.get("/{habitation_id}")
async def get_simulation_data(habitation_id: str):
    """
    Returns the 4-stage flood growth GeoJSON polygons and landslide risk cone
    for the specified habitation, mapped to live weather triggers.
    """
    try:
        hab = load_habitation(habitation_id)
        if not hab:
            raise HTTPException(status_code=404, detail="Habitation not found")
            
        lat = hab["lat"]
        lng = hab["lng"]
        
        # 1. Get Live Weather Trigger
        trigger = await get_live_weather_trigger(lat, lng)
        risk_multiplier = trigger.get("risk_multiplier", 1.0)
        
        # 2. Derive water levels from real Open-Meteo rainfall forecast
        water_levels = await _get_openmeteo_water_levels(lat, lng, risk_multiplier)

        # 3. Run Bathtub Scenarios
        inundation_result = compute_inundation_scenarios(
            lat=lat, 
            lng=lng, 
            radius_km=15.0, # 15km radius is standard for our local sim
            water_levels_m=water_levels,
            resolution_m=300
        )
        
        # 4. Format Flood Stages
        stages = []
        features = inundation_result.get("features", [])
        
        # Map features back to stages
        for i, hour in enumerate(STAGE_HOURS):
            feature = features[i] if i < len(features) else None
            
            # wrap feature in FeatureCollection for Cesium
            fc = None
            if feature:
                fc = {
                    "type": "FeatureCollection",
                    "metadata": inundation_result.get("metadata", {}),
                    "features": [feature]
                }
                
            stages.append({
                "t_plus_hours": hour,
                "stage_label": f"T+{hour}h",
                "water_level_m": water_levels[i],
                "geojson": fc
            })
            
        # 5. Format Landslide Cone
        aspect_deg = hab.get("aspect_deg", 90) # Default east if missing
        ls_stages = []
        for hour in STAGE_HOURS:
            r = BASE_LANDSLIDE_RADIUS[hour]
            cone = build_landslide_cone(lat, lng, aspect_deg, r, risk_multiplier)
            ls_stages.append({
                "t_plus_hours": hour,
                "radius_km": r,
                "cone_geojson": cone
            })
            
        landslide_cone = {
            "epicenter": [lat, lng],
            "aspect_deg": aspect_deg,
            "stages": ls_stages
        }
        
        return {
            "habitation_id": habitation_id,
            "habitation_name": hab["name"],
            "trigger": trigger,
            "stages": stages,
            "landslide_cone": landslide_cone
        }
        
    except Exception as e:
        logger.error(f"[/simulation] Failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
