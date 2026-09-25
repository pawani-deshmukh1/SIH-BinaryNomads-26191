from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from typing import Optional
from core.inference import engine
from core.scoring_types import ModelConfidence
import numpy as np
from core.image_utils import preprocess_image
from core.mask_to_geojson import damage_mask_to_features

router = APIRouter(prefix="/damage", tags=["Inference"])

@router.post("/")
async def assess_damage(
    pre_image: UploadFile = File(...),
    post_image: UploadFile = File(...),
    bbox: Optional[str] = Form(None)
):
    """
    Takes a pre-disaster and post-disaster image pair, runs the Siamese ResNet50 model,
    and returns a 3-class damage severity GeoJSON.
    """
    try:
        # Read file bytes
        pre_bytes = await pre_image.read()
        post_bytes = await post_image.read()
        
        # Preprocess using authentic PIL transformation
        pre_tensor = preprocess_image(pre_bytes, target_size=512)
        post_tensor = preprocess_image(post_bytes, target_size=512)
        
        inputs = {
            "pre_image": pre_tensor,
            "post_image": post_tensor
        }
        
        # Run through ONNX model in VRAM
        logits, confidence = await engine.run_async("damage", inputs)
        
        if logits is None:
            raise HTTPException(status_code=500, detail="Inference engine failed to run the model.")
            
        # The Siamese UNet outputs a dense prediction map of shape [1, 3, 512, 512] for 3 classes
        # Argmax along class dimension (dim=1)
        mask = np.argmax(logits, axis=1)[0].astype(np.int32)
        severity_score = float(np.mean(logits))
        
        features = []
        if bbox:
            try:
                # Expecting 'min_lng,min_lat,max_lng,max_lat'
                bbox_tuple = tuple(map(float, bbox.split(",")))
                features = damage_mask_to_features(mask, bbox_tuple, float(confidence.score))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid bbox format. Use 'min_lng,min_lat,max_lng,max_lat'")
        else:
            # Fallback dummy bbox if not provided
            fallback_bbox = (0.0, 0.0, 1.0, 1.0)
            features = damage_mask_to_features(mask, fallback_bbox, float(confidence.score))
        
        return {
            "type": "FeatureCollection",
            "features": features,
            "model_confidence": confidence.model_dump(),
            "severity_score": severity_score
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
