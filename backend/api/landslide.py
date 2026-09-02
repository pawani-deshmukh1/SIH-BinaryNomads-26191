from fastapi import APIRouter, File, UploadFile, HTTPException
from core.inference import engine
from core.scoring_types import ModelConfidence
import numpy as np

router = APIRouter(prefix="/landslide-risk", tags=["Inference"])

@router.post("/")
async def assess_landslide(image: UploadFile = File(...)):
    """
    Takes a single satellite image, runs the Monolith ResNet50 U-Net model,
    and returns a landslide-extent polygon GeoJSON.
    """
    try:
        # Mocking input tensor. The landslide model expects [1, 3, 512, 512].
        dummy_img = np.random.randn(1, 3, 512, 512).astype(np.float32)
        
        inputs = {
            "image": dummy_img
        }
        
        logits, confidence = engine.run("landslide", inputs)
        
        if logits is None:
            raise HTTPException(status_code=500, detail="Inference engine failed to run the model.")
            
        # Mocking the post-processing to GeoJSON
        return {
            "type": "FeatureCollection",
            "features": [],
            "model_confidence": confidence.model_dump()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
