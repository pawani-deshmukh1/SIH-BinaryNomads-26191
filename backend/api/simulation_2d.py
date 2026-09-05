from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import json
from pathlib import Path

router = APIRouter(prefix="/simulation/2d", tags=["RESPOND — 2D Simulation (Mobile)"])

class SimulationRequest(BaseModel):
    population: float
    capacity: float
    evacuationTime: float
    routeAvailability: float
    emergencyResources: float

@router.get("/{hab_id}")
def get_simulation_defaults(hab_id: str):
    """
    Returns initial terrain/demographic data to seed the 2D simulation sliders
    in the mobile app.
    """
    try:
        fixtures_dir = Path(__file__).resolve().parent.parent / "fixtures"
        hab_path = fixtures_dir / "habitations_assam.json"
        
        with open(hab_path, "r", encoding="utf-8") as f:
            habitations = json.load(f)
            
        hab = next((h for h in habitations if h.get("id") == hab_id or h.get("name") == hab_id), None)
        
        if not hab:
            # Fallback to defaults if hab_id not found (useful for demo with hardcoded "Borigaon")
            return {
                "population": 1240.0,
                "availableCapacity": 1850.0,
                "evacuationTime": 35.0,
                "routeAvailability": 82.0,
                "emergencyResources": 75.0,
            }
            
        # Get real population from fixture
        population = float(hab.get("population", 1000))
        
        # We estimate other values based on terrain for realistic simulation seed
        twi = hab.get("twi", 5.0)
        route_avail = max(10.0, min(100.0, 100.0 - (twi * 5))) # wetter terrain = worse routes
        
        return {
            "population": population,
            "availableCapacity": population * 1.5, # assume 1.5x capacity nearby
            "evacuationTime": 45.0, # default 45 mins
            "routeAvailability": route_avail,
            "emergencyResources": 80.0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{hab_id}")
def run_simulation(hab_id: str, request: SimulationRequest):
    """
    Runs the simulation math and returns the result.
    Matches the logic expected by the Flutter app.
    """
    occupancy = request.population / request.capacity if request.capacity > 0 else 1.0
    
    route_factor = max(30.0, min(100.0, request.routeAvailability)) / 100.0
    resource_factor = max(30.0, min(100.0, request.emergencyResources)) / 100.0
    combined_factor = (route_factor + resource_factor) / 2.0
    
    estimated_evac = request.evacuationTime / combined_factor if combined_factor > 0 else request.evacuationTime
    
    if occupancy >= 0.90 or request.routeAvailability < 45.0 or request.emergencyResources < 40.0:
        status = "CRITICAL"
    elif occupancy >= 0.75 or request.routeAvailability < 65.0 or request.emergencyResources < 60.0:
        status = "WARNING"
    else:
        status = "STABLE"
        
    return {
        "status": "success",
        "hab_id": hab_id,
        "results": {
            "occupancy_pct": occupancy,
            "estimated_evacuation_time": estimated_evac,
            "operational_status": status
        }
    }
