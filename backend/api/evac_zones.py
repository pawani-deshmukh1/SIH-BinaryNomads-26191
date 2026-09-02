from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone

router = APIRouter(prefix="/evac-zones", tags=["Intelligence"])

@router.get("/")
def get_evac_zones():
    """
    Returns ranked relocation candidate sites with capacity and suitability.
    """
    # Stub for Phase 4
    try:
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "id": "EZ-001",
                        "name": "Nagaon Govt School Ground",
                        "recommendation_score": 0.88,
                        "capacity_persons": 1200,
                        "suitability_score": 0.9,
                        "last_updated": datetime.now(timezone.utc).isoformat()
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [92.65, 26.35]
                    }
                },
                {
                    "type": "Feature",
                    "properties": {
                        "id": "EZ-002",
                        "name": "District Stadium",
                        "recommendation_score": 0.74,
                        "capacity_persons": 3500,
                        "suitability_score": 0.7,
                        "last_updated": datetime.now(timezone.utc).isoformat()
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [92.68, 26.34]
                    }
                }
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
