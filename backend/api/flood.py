from fastapi import APIRouter, File, UploadFile, HTTPException
from core.inference import engine
from core.scoring_types import ModelConfidence
import numpy as np

router = APIRouter(prefix="/flood-risk", tags=["Inference"])

@router.post("/")
async def assess_flood(image: UploadFile = File(...)):
    """
    Takes a single satellite image, runs the SegFormer flood model,
    and returns a flood-extent polygon GeoJSON.
    """
    try:
        # Mocking input tensor. The SegFormer expects [1, 3, 224, 224] in our export script.
        dummy_img = np.random.randn(1, 3, 224, 224).astype(np.float32)
        
        inputs = {
            "pixel_values": dummy_img
        }
        
        logits, confidence = engine.run("flood", inputs)
        
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
