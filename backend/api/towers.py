"""
towers.py — Cell tower risk endpoint (RESPOND bonus layer)

Reads from the last /analyze result via analysis_state (single source of truth).
Tower risk is computed in cop_builder: a tower is flagged 'at_risk' when it
falls within or within ~100m of a Red Zone polygon (shapely spatial check).

Fallback: demo fixture if /analyze has not been called yet.
"""
from fastapi import APIRouter, HTTPException, Query
from core.analysis_state import check_geofence
import json
import os

router = APIRouter(prefix="/towers", tags=["RESPOND — Comms Risk"])


@router.get("/")
def get_towers(region: str = Query(default="assam", description="Region to fetch towers for")):
    """
    Returns cell towers with computed operational status (operational | at_risk).
    at_risk = tower centroid is within or within 100m of a Red Zone polygon.

    Source: OpenCelliD mock fixture. Evaluated dynamically against active red zones.
    """
    try:
        region = region.lower()
        base_dir = os.path.join(os.path.dirname(__file__), "..", "fixtures")
        towers_file = os.path.join(base_dir, f"cell_towers_{region}.json")
        
        if not os.path.exists(towers_file):
            towers_file = os.path.join(base_dir, "cell_towers_assam.json")
            
        with open(towers_file, 'r') as f:
            data = json.load(f)
            
        features = data.get("features", [])
        at_risk = 0
        
        for f in features:
            lng, lat = f["geometry"]["coordinates"]
            is_inside, _, _ = check_geofence(lat, lng)
            if is_inside:
                f["properties"]["status"] = "at_risk"
                at_risk += 1
            else:
                f["properties"]["status"] = "operational"

        return {
            "type": "FeatureCollection",
            "count": len(features),
            "at_risk_count": at_risk,
            "source": f"opencellid_{region}",
            "features": features,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
