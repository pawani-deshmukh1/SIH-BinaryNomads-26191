import logging
import math
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


async def _get_openmeteo_water_levels(lat: float, lng: float, risk_multiplier: float) -> list:
    """
    Derive stage-specific water levels from Open-Meteo hourly precipitation.

    Method:
      1. Fetch 36h hourly precipitation forecast.
      2. Compute cumulative rainfall at T+0, T+6, T+18, T+36.
      3. Convert rainfall -> surface runoff -> approximate channel discharge
         -> water depth via Manning's simplified equation.
      4. Scale by risk_multiplier from hazard_trigger.

    Fallback: static FALLBACK_WATER_LEVELS if API call fails.
    """
    import httpx
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lng}"
            f"&hourly=precipitation&forecast_days=2"
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=6.0)
        if resp.status_code != 200:
            raise ValueError(f"HTTP {resp.status_code}")

        hourly_rain = resp.json().get("hourly", {}).get("precipitation", [])

        levels = []
        for hour in STAGE_HOURS:
            # Cumulative rainfall from T=0 to T=hour
            cumulative_mm = sum(hourly_rain[:max(1, hour)])

            # Surface runoff (mm) using rational method
            runoff_mm = cumulative_mm * RUNOFF_COEFFICIENT

            # Approximate discharge Q (m3/s) for a unit catchment (~10 km2)
            catchment_m2 = 10_000_000  # 10 km2 typical small char tributary catchment
            duration_s   = max(3600, hour * 3600)  # avoid division by zero
            Q = (runoff_mm / 1000) * catchment_m2 / duration_s  # m3/s

            # Water depth via Manning's simplified: h = (Q / (w * C))^0.6
            if Q > 0:
                h = (Q / (CHANNEL_WIDTH_M * MANNINGS_C)) ** 0.6
            else:
                h = FALLBACK_WATER_LEVELS[hour]  # use static if no rain

            # Scale by risk multiplier and cap at 8m
            h_scaled = min(8.0, round(h * risk_multiplier, 2))
            # Ensure water levels are monotonically increasing across stages
            if levels:
                h_scaled = max(h_scaled, levels[-1])

            levels.append(h_scaled)

        # Ensure at least 0.3m at T+0 (minimum bankfull condition)
        levels[0] = max(0.3, levels[0])
        logger.info(f"[Simulation] Open-Meteo water levels: {levels}")
        return levels

    except Exception as e:
        logger.warning(f"[Simulation] Open-Meteo water level fetch failed ({e}) — using static fallback")
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
