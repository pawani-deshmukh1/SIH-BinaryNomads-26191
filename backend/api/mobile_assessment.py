from fastapi import APIRouter, File, UploadFile, HTTPException
import numpy as np
from core.inference import engine
from core.image_utils import preprocess_image

flood_router = APIRouter(prefix="/flood-risk", tags=["Mobile Assessment"])
landslide_router = APIRouter(prefix="/landslide-risk", tags=["Mobile Assessment"])

@flood_router.post("/")
async def assess_flood(file: UploadFile = File(...)):
    """
    Real endpoint for mobile app image upload assessment for Flood Risk.
    Uses HuggingFace SegFormer ONNX model.
    """
    try:
        file_bytes = await file.read()
        
        # SegFormer expects 224x224
        tensor = preprocess_image(file_bytes, target_size=224)
        
        logits, confidence = await engine.run_async("flood", {"pixel_values": tensor})
        
        if logits is None:
            raise HTTPException(status_code=500, detail="Inference engine failed to run flood model.")
            
        # Logits shape [1, 2, 56, 56]. Convert to probability.
        risk_score = float(np.clip(np.mean(logits) / 10.0, 0.0, 1.0))
        
        return {
            "status": "success",
            "hazard": "FLOOD",
            "risk_score": round(risk_score, 2),
            "confidence": round(confidence.score, 2),
            "message": "Water accumulation assessment complete."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@landslide_router.post("/")
async def assess_landslide(file: UploadFile = File(...)):
    """
    Real endpoint for mobile app image upload assessment for Landslide Risk.
    Uses Monolith ResNet50 U-Net ONNX model.
    """
    try:
        file_bytes = await file.read()
        
        # Landslide model expects 512x512
        tensor = preprocess_image(file_bytes, target_size=512)
        
        logits, confidence = await engine.run_async("landslide", {"image": tensor})
        
        if logits is None:
            raise HTTPException(status_code=500, detail="Inference engine failed to run landslide model.")
            
        risk_score = float(np.clip(np.mean(logits) / 10.0, 0.0, 1.0))
        
        return {
            "status": "success",
            "hazard": "LANDSLIDE",
            "risk_score": round(risk_score, 2),
            "confidence": round(confidence.score, 2),
            "message": "Terrain instability assessment complete."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
