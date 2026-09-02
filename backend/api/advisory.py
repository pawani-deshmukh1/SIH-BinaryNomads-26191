"""
advisory.py — GET /advisory/{habitation_id}

Generates a structured relocation advisory for an at-risk habitation.
1. Loads the habitation from fixtures.
2. Loads available safe zones from fixtures.
3. Evaluates all safe zones against the habitation's population and location.
4. Generates a Sphere-standard resource plan.
"""
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
import json
from pathlib import Path
from core.carrying_capacity import evaluate_safe_zones, calculate_resources
from core.hazard_trigger import get_live_weather_trigger

router = APIRouter(prefix="/advisory", tags=["Relocation Advisory"])

def load_json_fixture(filename: str):
    path = Path(__file__).resolve().parent.parent / "fixtures" / filename
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@router.get("/safe-zones")
async def get_all_safe_zones(region: str = Query(default="assam")):
    """Return all safe zones in the region as a GeoJSON FeatureCollection."""
    safe_zones = load_json_fixture(f"safe_zones_{region}.json")
    
    features = []
    for sz in safe_zones:
        # Calculate new relaxed capacity based on SPHERE_M2_PER_PERSON = 3.5
        capacity = int(sz.get("site_area_sqm", 0) / 3.5)
        
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [sz.get("lng", 0), sz.get("lat", 0)]
            },
            "properties": {
                "id": sz.get("id", ""),
                "name": sz.get("name", "Unknown Safe Zone"),
                "capacity": capacity,
                "district": sz.get("district", ""),
                "type": sz.get("type", "safe_zone")
            }
        })
        
    return JSONResponse(content={
        "type": "FeatureCollection",
        "features": features,
        "metadata": {"total": len(features)}
    })

@router.get("/{habitation_id}")
async def generate_advisory(habitation_id: str, region: str = Query(default="assam")):
    """
    Generate a full relocation advisory for a specific habitation.
    Finds the best safe zone that passes all hard filters (capacity, distance, hazard).
    """
    # 1. Load data
    habitations = load_json_fixture(f"habitations_{region}.json")
    safe_zones = load_json_fixture(f"safe_zones_{region}.json")
    
    hab = next((h for h in habitations if h["id"] == habitation_id), None)
    if not hab:
        raise HTTPException(status_code=404, detail="Habitation not found")
        
    pop = hab.get("population", 0)
    if pop == 0:
        raise HTTPException(status_code=400, detail="Habitation has no population data")
        
    # 2. Get live weather trigger for context
    live_trigger = await get_live_weather_trigger(hab["lat"], hab["lng"])
    
    # 3. Evaluate Safe Zones
    evaluation = evaluate_safe_zones(
        safe_zones=safe_zones,
        displaced_population=pop,
        hab_lat=hab["lat"],
        hab_lng=hab["lng"]
    )
    
    valid_candidates = evaluation["valid_candidates"]
    rejected_sites = evaluation["rejected_sites"]
    
    if not valid_candidates:
        return JSONResponse(status_code=404, content={
            "status": "error",
            "message": "NO VALID SAFE ZONES FOUND. All candidates failed hard filters.",
            "rejected_sites": rejected_sites
        })
        
    best_site = valid_candidates[0]
    
    # 4. Calculate Resource Needs
    resources = calculate_resources(pop)
    
    # 5. Generate structured advisory
    advisory = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "urgency": "CRITICAL",
        "habitation": {
            "id": hab["id"],
            "name": hab["name"],
            "type": hab.get("type"),
            "population": pop,
            "households": hab.get("households", 0),
            "vulnerability_sc_st_pct": hab.get("sc_st_percent", 0)
        },
        "trigger": {
            "reason": "Risk threshold exceeded",
            "live_weather": live_trigger
        },
        "relocation_plan": {
            "recommended_site": best_site,
            "alternative_sites": valid_candidates[1:3],
            "logistics": {
                "evacuation_mode": best_site["access_mode"],
                "distance_km": best_site["distance_km"],
            },
            "resources_required": resources
        },
        "rejected_sites_log": rejected_sites
    }
    
    return JSONResponse(content={"status": "success", "advisory": advisory})
