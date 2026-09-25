from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from typing import Optional
from core.inference import engine
from core.scoring_types import ModelConfidence
import numpy as np
from core.image_utils import preprocess_image
from core.mask_to_geojson import landslide_mask_to_features

router = APIRouter(prefix="/landslide-risk", tags=["Inference"])

@router.post("/")
async def assess_landslide(
    image: UploadFile = File(...),
    bbox: Optional[str] = Form(None)
):
    """
    Takes a single satellite/drone image, runs the Monolith ResNet50 U-Net model,
    and returns a landslide-extent polygon GeoJSON.
    """
    try:
        # Authentic preprocessing
        file_bytes = await image.read()
        tensor = preprocess_image(file_bytes, target_size=512)
        
        inputs = {
            "image": tensor
        }
        
        logits, confidence = await engine.run_async("landslide", inputs)
        
        if logits is None:
            raise HTTPException(status_code=500, detail="Inference engine failed to run the model.")
            
        # ResNet50 U-Net output shape: [1, 1, 512, 512]
        # Sigmoid threshold at 0.5
        sigmoid_logits = 1 / (1 + np.exp(-logits))
        mask = (sigmoid_logits[0, 0] > 0.5).astype(np.int32)
        risk_score = float(np.clip(np.mean(logits) / 10.0, 0.0, 1.0))
        
        features = []
        if bbox:
            try:
                # Expecting 'min_lng,min_lat,max_lng,max_lat'
                bbox_tuple = tuple(map(float, bbox.split(",")))
                features = landslide_mask_to_features(mask, bbox_tuple, float(confidence.score))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid bbox format. Use 'min_lng,min_lat,max_lng,max_lat'")
        else:
            # Fallback dummy bbox if not provided
            fallback_bbox = (0.0, 0.0, 1.0, 1.0)
            features = landslide_mask_to_features(mask, fallback_bbox, float(confidence.score))
        
        return {
            "type": "FeatureCollection",
            "features": features,
            "model_confidence": confidence.model_dump(),
            "risk_score": risk_score
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
