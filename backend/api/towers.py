"""
towers.py — Cell tower risk endpoint (RESPOND bonus layer)

Reads from the last /analyze result via analysis_state (single source of truth).
Tower risk is computed in cop_builder: a tower is flagged 'at_risk' when it
falls within or within ~100m of a Red Zone polygon (shapely spatial check).

Fallback: demo fixture if /analyze has not been called yet.
"""
from fastapi import APIRouter, HTTPException
from core.analysis_state import get_last_cop
from core.cop_builder import build_cop_from_demo

router = APIRouter(prefix="/towers", tags=["RESPOND — Comms Risk"])


@router.get("/")
def get_towers():
    """
    Returns cell towers with computed operational status (operational | at_risk).
    at_risk = tower centroid is within or within 100m of a Red Zone polygon.

    Source: last /analyze run. Falls back to demo fixture if no analysis yet.
    """
    try:
        cop = get_last_cop()
        if not cop:
            cop = build_cop_from_demo()

        features = [
            f for f in cop.get("features", [])
            if f.get("properties", {}).get("layer_type") == "tower"
        ]
        at_risk = sum(1 for f in features if f["properties"].get("status") == "at_risk")
        return {
            "type": "FeatureCollection",
            "count": len(features),
            "at_risk_count": at_risk,
            "source": "analyze_pipeline" if get_last_cop() else "demo_fixture",
            "features": features,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
