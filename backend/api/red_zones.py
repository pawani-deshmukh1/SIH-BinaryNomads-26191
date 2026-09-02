"""
red_zones.py — Red Zone GeoJSON endpoint (IDENTIFY layer)

Reads from the last /analyze result via analysis_state.
This ensures a single source of truth: the standalone /red-zones
endpoint and the COP map both see the same data.

Fallback: if /analyze has not been called yet, loads from demo fixture.
"""
from fastapi import APIRouter, HTTPException
from core.analysis_state import get_last_cop
from core.cop_builder import build_cop_from_demo

router = APIRouter(prefix="/red-zones", tags=["IDENTIFY — Red Zones"])


@router.get("/")
def get_red_zones():
    """
    Returns fused Red Zone polygons from the latest /analyze run.
    Each feature carries: risk_score, color_tier (red/orange/green),
    contributing_factors (per-hazard weight + value + spatial overlap flag).

    If /analyze has not been called yet, returns the pre-cached demo COP's
    red zone features so the endpoint is never empty during a presentation.
    """
    try:
        cop = get_last_cop()
        if not cop:
            cop = build_cop_from_demo()

        features = [
            f for f in cop.get("features", [])
            if f.get("properties", {}).get("layer_type") == "red_zone"
        ]
        return {
            "type": "FeatureCollection",
            "count": len(features),
            "source": "analyze_pipeline" if get_last_cop() else "demo_fixture",
            "features": features,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
