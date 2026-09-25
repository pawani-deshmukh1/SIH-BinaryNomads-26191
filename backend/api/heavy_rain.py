from fastapi import APIRouter, HTTPException, Query
from core.heavy_rain import evaluate_heavy_rain_onset
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/heavy-rain", tags=["LAYER 0 — Imminent Threat"])

@router.get("/predict")
def predict_heavy_rain(
    lat: float = Query(..., description="Latitude of the location"),
    lon: float = Query(..., description="Longitude of the location")
):
    """
    Evaluates the Heavy Rainfall Onset model for a given location.
    Pulls live Open-Meteo forecast and physical DEM data, runs thermodynamic
    feature engineering, and returns a continuous risk percentile.
    """
    try:
        result = evaluate_heavy_rain_onset(lat, lon)
        return {
            "status": "success",
            "location": {"lat": lat, "lon": lon},
            "risk_percentile": result["risk_percentile"],
            "probability_raw": result["probability_raw"],
            "is_imminent": result["is_imminent"],
            "features": result["features"]
        }
    except Exception as e:
        logger.error(f"Failed to evaluate heavy rain: {e}")
        raise HTTPException(status_code=500, detail=str(e))
