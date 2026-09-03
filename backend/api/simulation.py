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
BASE_WATER_LEVELS = {
    0: 0.5,
    6: 1.5,
    18: 3.0,
    36: 5.0
}

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
        
        # 2. Map rainfall escalation to water levels
        water_levels = []
        for hour in STAGE_HOURS:
            if hour == 0:
                water_levels.append(BASE_WATER_LEVELS[hour]) # Current state
            else:
                water_levels.append(round(BASE_WATER_LEVELS[hour] * risk_multiplier, 2))
                
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
