"""
inundation.py — Flood Inundation Simulation API Endpoint
=========================================================
POST /inundation/   →  Run flood spread simulation, return GeoJSON scenarios
GET  /inundation/status  →  Check if simulation is running
"""
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/inundation", tags=["Inundation Simulation"])


class InundationRequest(BaseModel):
    lat: float = Field(..., description="Center latitude", ge=-90, le=90)
    lng: float = Field(..., description="Center longitude", ge=-180, le=180)
    radius_km: float = Field(default=15.0, ge=1.0, le=50.0,
                              description="Simulation radius in km")
    water_levels_m: Optional[list[float]] = Field(
        default=None,
        description="List of water levels above river base to simulate (meters). "
                    "Default: [0.5, 1.0, 1.5, 2.0, 3.0, 5.0]"
    )
    resolution_m: int = Field(default=300, ge=100, le=1000,
                               description="DEM grid resolution in meters")


@router.post("/")
async def run_inundation_simulation(req: InundationRequest):
    """
    Simulate flood inundation footprint at multiple water level scenarios.

    Returns a GeoJSON FeatureCollection. Each Feature is the flood footprint
    at one water level scenario. Animate them sequentially in the dashboard
    to show how the flood spreads.

    The simulation uses SRTM 30m DEM data (downloaded and cached locally on
    first call) and a connected BFS flood fill algorithm.
    """
    try:
        from core.flood_inundation import compute_inundation_scenarios

        logger.info(f"[/inundation] Simulation request: lat={req.lat}, lng={req.lng}, "
                    f"radius={req.radius_km}km, resolution={req.resolution_m}m")

        result = compute_inundation_scenarios(
            lat=req.lat,
            lng=req.lng,
            radius_km=req.radius_km,
            water_levels_m=req.water_levels_m,
            resolution_m=req.resolution_m,
        )

        n_scenarios = result.get("metadata", {}).get("scenarios_computed", 0)
        logger.info(f"[/inundation] Complete — {n_scenarios} scenarios computed.")

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"[/inundation] Simulation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Simulation failed: {str(e)}")


@router.get("/demo")
async def run_inundation_demo():
    """
    Returns a pre-built demo inundation result for Nagaon, Assam
    without running actual SRTM computation. For fast UI testing.
    """
    try:
        from core.flood_inundation import compute_inundation_scenarios
        # Run with synthetic DEM (no srtm needed) by using a tiny radius
        # so it falls back gracefully
        result = compute_inundation_scenarios(
            lat=26.342,
            lng=92.651,
            radius_km=10.0,
            water_levels_m=[0.5, 1.0, 2.0, 3.0, 5.0],
            resolution_m=500,  # coarser = faster for demo
        )
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"[/inundation/demo] {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
