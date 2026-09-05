from fastapi import APIRouter, File, UploadFile, HTTPException
import random

flood_router = APIRouter(prefix="/flood-risk", tags=["Mobile Assessment"])
landslide_router = APIRouter(prefix="/landslide-risk", tags=["Mobile Assessment"])

@flood_router.post("/")
async def assess_flood(file: UploadFile = File(...)):
    """
    Dummy endpoint for mobile app image upload assessment for Flood Risk.
    Returns a dummy risk percentage.
    """
    try:
        # We would pass 'file' to the inference engine here
        return {
            "status": "success",
            "hazard": "FLOOD",
            "risk_score": round(random.uniform(0.65, 0.95), 2),
            "confidence": 0.88,
            "message": "Water accumulation detected in image."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@landslide_router.post("/")
async def assess_landslide(file: UploadFile = File(...)):
    """
    Dummy endpoint for mobile app image upload assessment for Landslide Risk.
    """
    try:
        return {
            "status": "success",
            "hazard": "LANDSLIDE",
            "risk_score": round(random.uniform(0.50, 0.90), 2),
            "confidence": 0.91,
            "message": "Terrain instability detected in image."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
