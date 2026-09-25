from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from typing import Optional
from core.inference import engine
from core.scoring_types import ModelConfidence
import numpy as np
from core.image_utils import preprocess_image
from core.mask_to_geojson import flood_mask_to_features

router = APIRouter(prefix="/flood-risk", tags=["Inference"])

@router.post("/")
async def assess_flood(
    image: UploadFile = File(...),
    bbox: Optional[str] = Form(None)
):
    """
    Takes a single satellite/drone image, runs the SegFormer flood model,
    and returns a flood-extent polygon GeoJSON.
    """
    try:
        # Authentic preprocessing
        file_bytes = await image.read()
        tensor = preprocess_image(file_bytes, target_size=224)
        
        inputs = {
            "pixel_values": tensor
        }
        
        logits, confidence = await engine.run_async("flood", inputs)
        
        if logits is None:
            raise HTTPException(status_code=500, detail="Inference engine failed to run the model.")
            
        # Segformer output shape: [1, 2, 56, 56]
        # Argmax along class dimension (dim=1)
        mask = np.argmax(logits, axis=1)[0].astype(np.int32)
        risk_score = float(np.clip(np.mean(logits) / 10.0, 0.0, 1.0))
        
        features = []
        if bbox:
            try:
                # Expecting 'min_lng,min_lat,max_lng,max_lat'
                bbox_tuple = tuple(map(float, bbox.split(",")))
                features = flood_mask_to_features(mask, bbox_tuple, float(confidence.score))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid bbox format. Use 'min_lng,min_lat,max_lng,max_lat'")
        else:
            # Fallback dummy bbox if not provided
            fallback_bbox = (0.0, 0.0, 1.0, 1.0)
            features = flood_mask_to_features(mask, fallback_bbox, float(confidence.score))
        
        return {
            "type": "FeatureCollection",
            "features": features,
            "model_confidence": confidence.model_dump(),
            "risk_score": risk_score
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
