from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone

router = APIRouter(prefix="/evac-zones", tags=["Intelligence"])

@router.get("/")
def get_evac_zones():
    """
    Returns ranked relocation candidate sites with capacity and suitability.
    """
    try:
        from core.optimization import evaluate_safe_zones
        import json
        import os
        
        safe_zones_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "safe_zones_assam.json")
        with open(safe_zones_path, 'r') as f:
            safe_zones = json.load(f)
            
        evaluated = evaluate_safe_zones(safe_zones)
        
        features = []
        for sz in evaluated:
            features.append({
                "type": "Feature",
                "properties": {
                    "id": sz["id"],
                    "name": sz["name"],
                    "recommendation_score": sz.get("suitability_score", 0.8),
                    "capacity_persons": sz.get("capacity_persons", 1000),
                    "suitability_score": sz.get("suitability_score", 0.8),
                    "district": sz.get("district", "Unknown"),
                    "last_updated": datetime.now(timezone.utc).isoformat()
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [sz["lng"], sz["lat"]]
                }
            })
            
        return {
            "type": "FeatureCollection",
            "features": features
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
