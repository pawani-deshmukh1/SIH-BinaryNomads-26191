"""
susceptibility.py — GET /susceptibility/ endpoint

Layer A: Static Susceptibility Scoring using XGBoost models trained on:
  - NASA Global Landslide Catalog
  - HydroRIVERS flood extents
  - NASA SRTM 30m DEM
  - CHIRPS 2.0 Rainfall
  - ESA WorldCover 2021

Also exposes:
  GET /susceptibility/habitations  → score ALL habitations in the fixture at once
  GET /susceptibility/zone-map     → returns a GeoJSON FeatureCollection 
                                     with zone_class for every habitation
"""
from fastapi import APIRouter, Query, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/susceptibility", tags=["Layer A — Static Susceptibility"])


@router.get("/")
async def score_point(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    region: str = Query(default="assam", description="Region (e.g., 'assam' or 'kerala')"),
    elevation: float = Query(default=100.0, description="Elevation in meters (NASA SRTM)"),
    slope: float = Query(default=10.0, description="Slope in degrees"),
    aspect: float = Query(default=180.0, description="Aspect in degrees"),
    tri: float = Query(default=5.0, description="Terrain Ruggedness Index"),
    twi: float = Query(default=6.0, description="Topographic Wetness Index"),
    dist_to_river_m: float = Query(default=5000.0, description="Distance to nearest river in meters"),
    precip_annual_mm: float = Query(default=1800.0, description="Annual rainfall mm (CHIRPS 2023)"),
    precip_daily_mm: float = Query(default=15.0, description="Peak daily rainfall mm (CHIRPS)"),
    vegetation_proxy: float = Query(default=0.5, description="Vegetation cover 0-1 (ESA WorldCover)"),
    hand_proxy_m: float = Query(default=5.0, description="Height Above Nearest Drainage in meters"),
):
    """
    Score a single coordinate using the proactive XGBoost models (Layer A).
    
    Returns landslide + flood susceptibility scores and zone classification.
    Can be called without an image — purely terrain/climate features.
    """
    from core.proactive_engine import proactive_engine

    features = {
        "lat": lat, "lng": lng,
        "elevation": elevation, "slope": slope, "aspect": aspect,
        "tri": tri, "twi": twi,
        "dist_to_river_m": dist_to_river_m,
        "precip_annual_mm": precip_annual_mm,
        "precip_daily_mm": precip_daily_mm,
        "vegetation_proxy": vegetation_proxy,
        "hand_proxy_m": hand_proxy_m,
    }

    result = proactive_engine.score(features, region=region)

    return JSONResponse(content={
        "status": "success",
        "coordinates": {"lat": lat, "lng": lng},
        "layer_a_susceptibility": result,
    })


@router.get("/habitations")
async def score_all_habitations(region: str = Query(default="assam")):
    """
    Score ALL habitations in the fixture file at once.
    
    Returns a list of habitations, each with:
      - Their existing fields (name, population, lat, lng)
      - layer_a: landslide_score, flood_score, zone_class
    
    This is what the dashboard calls to color the map Red/Orange/Yellow/Green.
    """
    import json
    from pathlib import Path
    from core.proactive_engine import proactive_engine

    fixtures_dir = Path(__file__).resolve().parent.parent / "fixtures"
    hab_path = fixtures_dir / f"habitations_{region}.json"

    if not hab_path.exists():
        return JSONResponse(
            status_code=404,
            content={"error": f"No habitation fixture for region '{region}'"}
        )

    with open(hab_path, "r", encoding="utf-8") as f:
        habitations = json.load(f)

    scored = []
    for hab in habitations:
        terrain = {
            "elevation":        hab.get("elevation_m", 80.0),
            "slope":            hab.get("slope_deg", 8.0),
            "aspect":           hab.get("aspect_deg", 180.0),
            "tri":              hab.get("tri", 4.0),
            "twi":              hab.get("twi", 7.0),
            "dist_to_river_m":  hab.get("dist_to_river_m", 3000.0),
            "precip_annual_mm": hab.get("precip_annual_mm", 1800.0),
            "precip_daily_mm":  hab.get("precip_daily_mm", 12.0),
            "vegetation_proxy": hab.get("vegetation_proxy", 0.6),
            "hand_proxy_m":     hab.get("hand_proxy_m", 8.0),
        }
        score = proactive_engine.score(terrain, region=region)
        scored.append({**hab, "layer_a": score})

    # Summary stats
    zone_counts = {}
    for s in scored:
        z = s["layer_a"]["zone_class"]
        zone_counts[z] = zone_counts.get(z, 0) + 1

    return JSONResponse(content={
        "status": "success",
        "region": region,
        "total_habitations": len(scored),
        "zone_summary": zone_counts,
        "habitations": scored,
    })


@router.get("/zone-map")
async def get_zone_map(region: str = Query(default="assam")):
    """
    Returns a GeoJSON FeatureCollection with zone_class for every habitation.
    Plug this directly into Leaflet as a layer.
    
    Feature colors:
      RED    → #ef4444
      ORANGE → #f97316
      YELLOW → #eab308
      GREEN  → #22c55e
    """
    import json
    from pathlib import Path
    from core.proactive_engine import proactive_engine

    ZONE_COLORS = {
        "RED":    "#ef4444",
        "ORANGE": "#f97316",
        "YELLOW": "#eab308",
        "GREEN":  "#22c55e",
    }

    fixtures_dir = Path(__file__).resolve().parent.parent / "fixtures"
    hab_path = fixtures_dir / f"habitations_{region}.json"

    if not hab_path.exists():
        return JSONResponse(status_code=404, content={"error": f"No fixture for region '{region}'"})

    with open(hab_path, "r", encoding="utf-8") as f:
        habitations = json.load(f)

    features = []
    for hab in habitations:
        terrain = {
            "elevation":        hab.get("elevation_m", 80.0),
            "slope":            hab.get("slope_deg", 8.0),
            "aspect":           hab.get("aspect_deg", 180.0),
            "tri":              hab.get("tri", 4.0),
            "twi":              hab.get("twi", 7.0),
            "dist_to_river_m":  hab.get("dist_to_river_m", 3000.0),
            "precip_annual_mm": hab.get("precip_annual_mm", 1800.0),
            "precip_daily_mm":  hab.get("precip_daily_mm", 12.0),
            "vegetation_proxy": hab.get("vegetation_proxy", 0.6),
            "hand_proxy_m":     hab.get("hand_proxy_m", 8.0),
        }
        score = proactive_engine.score(terrain, region=region)
        zone = score["zone_class"]

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [hab.get("lng", 91.7), hab.get("lat", 26.1)]
            },
            "properties": {
                "id":               hab.get("id", ""),
                "name":             hab.get("name", "Unknown"),
                "population":       hab.get("population", 0),
                "households":       hab.get("households", 0),
                "zone_class":       zone,
                "landslide_score":  score["landslide_score"],
                "flood_score":      score["flood_score"],
                "combined_score":   score["combined_score"],
                "sc_st_percent":    hab.get("sc_st_percent", 0),
                "landless_pct":     hab.get("landless_households_pct", 40),
                "literacy_rate_pct": hab.get("literacy_rate_pct", 70),
                "nearest_hospital_km": hab.get("nearest_hospital_km", 20),
                "twi":              terrain["twi"],
                "tri":              terrain["tri"],
                "color":            ZONE_COLORS[zone],
                "top_factors":      score["top_landslide_factors"],
                "model_used":       score["model_used"],
            }
        })

    return JSONResponse(content={
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "region": region,
            "total": len(features),
            "zone_counts": {
                z: sum(1 for f in features if f["properties"]["zone_class"] == z)
                for z in ["RED", "ORANGE", "YELLOW", "GREEN"]
            }
        }
    })


@router.get("/auto-score")
async def auto_score_coordinate(
    lat: float = Query(..., description="Latitude of any point on Earth"),
    lng: float = Query(..., description="Longitude of any point on Earth"),
    region: str = Query(default="assam", description="Model region: 'assam' or 'kerala'"),
):
    """
    Score ANY coordinate automatically by fetching real terrain data.

    Sources used:
      - NASA SRTM 30m DEM → elevation, slope, aspect, TRI, TWI, HAND
      - Open-Meteo API    → live + annual precipitation (CHIRPS-equivalent)
      - Overpass API      → nearest waterway distance
      - Regional heuristic → vegetation proxy (ESA WorldCover proxy)

    No fixture required. Works for any habitation in India.
    """
    from core.terrain_fetcher import fetch_terrain_features
    from core.proactive_engine import proactive_engine

    # 1. Fetch real terrain from live sources
    try:
        features = await fetch_terrain_features(lat, lng)
        data_source = "live"
    except Exception as e:
        logger.warning(f"[auto-score] Terrain fetch failed ({e}), using region defaults")
        features = {
            "elevation": 80.0, "slope": 10.0, "aspect": 180.0,
            "tri": 4.0, "twi": 7.0, "hand_proxy_m": 8.0,
            "dist_to_river_m": 3000.0, "precip_annual_mm": 1800.0,
            "precip_daily_mm": 12.0, "vegetation_proxy": 0.6,
        }
        data_source = "regional_defaults"

    # 2. Score with XGBoost
    result = proactive_engine.score(features, region=region)

    return JSONResponse(content={
        "status": "success",
        "coordinates": {"lat": lat, "lng": lng},
        "data_source": data_source,
        "terrain_features": features,
        "risk_assessment": result,
        "zone_class": result["zone_class"],
        "flood_score": result["flood_score"],
        "landslide_score": result["landslide_score"],
        "combined_score": result["combined_score"],
        "explanation": {
            "flood": result.get("flood_explanation", {}),
            "landslide": result.get("landslide_explanation", {}),
        }
    })

class AddHabitationRequest(BaseModel):
    name: str
    lat: float
    lng: float
    population: int
    households: int
    sc_st_percent: int = 0
    type: str = "rural"
    type_label: str = "Rural Village"
    district: str = "Custom"
    block: str = "Custom"
    road_accessible: bool = True
    nearest_road_km: float = 1.0
    women_percent: float = 50.0
    children_percent: float = 25.0
    elderly_percent: float = 10.0
    # Include terrain features
    elevation_m: float
    slope_deg: float
    aspect_deg: float
    tri: float
    twi: float
    dist_to_river_m: float
    precip_annual_mm: float
    precip_daily_mm: float
    vegetation_proxy: float
    hand_proxy_m: float

@router.post("/habitations/add")
async def add_habitation(req: AddHabitationRequest, region: str = Query(default="assam")):
    """
    Save a dynamically monitored custom coordinate into the main habitation database.
    This integrates it with Layer 2 relocation engine instantly.
    """
    import json
    from pathlib import Path
    
    fixtures_dir = Path(__file__).resolve().parent.parent / "fixtures"
    hab_path = fixtures_dir / f"habitations_{region}.json"

    if not hab_path.exists():
        return JSONResponse(status_code=404, content={"error": f"No habitation fixture for region '{region}'"})

    with open(hab_path, "r", encoding="utf-8") as f:
        habitations = json.load(f)

    new_id = f"HAB_CUSTOM_{len(habitations) + 1:03d}"
    
    new_hab = req.dict()
    new_hab["id"] = new_id
    new_hab["historical_floods_10yr"] = 0
    new_hab["historical_landslides_10yr"] = 0
    
    habitations.append(new_hab)

    with open(hab_path, "w", encoding="utf-8") as f:
        json.dump(habitations, f, indent=2)

    return JSONResponse(content={"status": "success", "id": new_id, "message": f"Added {req.name} to monitoring grid"})

