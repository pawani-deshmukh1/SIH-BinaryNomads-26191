"""
pipeline.py — Master orchestration for the DISHA COP pipeline.

Runs all 3 models in parallel, converts masks to GeoJSON, fetches buildings,
overlays damage on OSM footprints. Returns a structured PipelineResult.

Two modes:
  - demo_mode=True  → returns pre-cached fixture from backend/fixtures/demo_result.json
  - demo_mode=False → runs live inference (requires .onnx models + image bytes)
"""
import asyncio
import io
import json
import logging
import numpy as np
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
DEMO_RESULT_PATH = FIXTURES_DIR / "demo_result.json"


@dataclass
class ModelResult:
    mask: Optional[np.ndarray] = None     # [H, W] integer mask
    confidence: float = 0.0
    features: list[dict] = field(default_factory=list)  # GeoJSON features from mask


@dataclass
class PipelineResult:
    damage: ModelResult = field(default_factory=ModelResult)
    flood: ModelResult = field(default_factory=ModelResult)
    landslide: ModelResult = field(default_factory=ModelResult)
    building_damage_features: list[dict] = field(default_factory=list)
    red_zone_features: list[dict] = field(default_factory=list)
    evac_site_features: list[dict] = field(default_factory=list)
    route_features: list[dict] = field(default_factory=list)
    tower_features: list[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    duration_ms: float = 0.0
    demo_mode: bool = False
    error: Optional[str] = None
    annotated_image_base64: Optional[str] = None


def _preprocess_image(image_bytes: bytes, target_size: tuple[int, int] = (512, 512)) -> np.ndarray:
    """
    Decode image bytes → normalize → return CHW float32 tensor shape [1, 3, H, W].
    """
    try:
        from PIL import Image
    except ImportError:
        raise ImportError("Pillow required: pip install Pillow")

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = img.resize(target_size, Image.BILINEAR)
    arr = np.array(img, dtype=np.float32) / 255.0

    # ImageNet normalization
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std  = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    arr = (arr - mean) / std

    # HWC → CHW → NCHW
    arr = arr.transpose(2, 0, 1)[np.newaxis, ...]
    return arr


def _mask_from_logits(logits: np.ndarray, binary: bool = False) -> np.ndarray:
    """
    Convert raw ONNX logits to an integer class mask.
    - Multi-class (damage, 3 classes): argmax over channel dim
    - Binary (flood, landslide): sigmoid threshold at 0.5
    """
    if logits is None:
        return np.zeros((512, 512), dtype=np.int32)

    if binary:
        # logits shape: [1, 1, H, W] or [1, H, W]
        squeezed = logits.squeeze()
        prob = 1.0 / (1.0 + np.exp(-squeezed))  # sigmoid
        return (prob > 0.5).astype(np.int32)
    else:
        # logits shape: [1, C, H, W]
        if logits.ndim == 4:
            return np.argmax(logits[0], axis=0).astype(np.int32)
        return np.argmax(logits, axis=0).astype(np.int32)


async def _run_damage(pre_bytes: bytes, post_bytes: bytes, bbox: tuple) -> ModelResult:
    """Run Siamese damage model. Needs pre + post image pair."""
    from .inference import engine
    from .mask_to_geojson import damage_mask_to_features

    try:
        pre_tensor  = _preprocess_image(pre_bytes,  (512, 512))
        post_tensor = _preprocess_image(post_bytes, (512, 512))
        inputs = {"pre_image": pre_tensor, "post_image": post_tensor}
        logits, conf = await engine.run_async("damage", inputs)

        if logits is None:
            return ModelResult()

        mask = _mask_from_logits(logits, binary=False)
        confidence = conf.score if conf else 0.0
        features = damage_mask_to_features(mask, bbox, confidence)
        return ModelResult(mask=mask, confidence=confidence, features=features)
    except Exception as e:
        logger.error(f"[Pipeline] Damage model error: {e}")
        return ModelResult()


async def _run_flood(image_bytes: bytes, bbox: tuple) -> ModelResult:
    """Run SegFormer flood model. Single image input."""
    from .inference import engine
    from .mask_to_geojson import flood_mask_to_features

    try:
        tensor = _preprocess_image(image_bytes, (224, 224))
        inputs = {"pixel_values": tensor}
        logits, conf = await engine.run_async("flood", inputs)

        if logits is None:
            return ModelResult()

        mask = _mask_from_logits(logits, binary=False)
        confidence = conf.score if conf else 0.0
        features = flood_mask_to_features(mask, bbox, confidence)
        return ModelResult(mask=mask, confidence=confidence, features=features)
    except Exception as e:
        logger.error(f"[Pipeline] Flood model error: {e}")
        return ModelResult()


async def _run_landslide(image_bytes: bytes, bbox: tuple) -> ModelResult:
    """Run ResNet50 U-Net landslide model. Single image input."""
    from .inference import engine
    from .mask_to_geojson import landslide_mask_to_features

    try:
        tensor = _preprocess_image(image_bytes, (512, 512))
        inputs = {"image": tensor}
        logits, conf = await engine.run_async("landslide", inputs)

        if logits is None:
            return ModelResult()

        mask = _mask_from_logits(logits, binary=True)
        confidence = conf.score if conf else 0.0
        features = landslide_mask_to_features(mask, bbox, confidence)
        return ModelResult(mask=mask, confidence=confidence, features=features)
    except Exception as e:
        logger.error(f"[Pipeline] Landslide model error: {e}")
        return ModelResult()


def _lat_lng_to_bbox(lat: float, lng: float, radius_km: float) -> tuple[float, float, float, float]:
    """Convert center point + radius to (min_lng, min_lat, max_lng, max_lat)."""
    # Rough approximation: 1 degree lat ≈ 111 km
    delta_lat = radius_km / 111.0
    delta_lng = radius_km / (111.0 * abs(np.cos(np.radians(lat))) + 1e-9)
    return (
        round(lng - delta_lng, 6),
        round(lat - delta_lat, 6),
        round(lng + delta_lng, 6),
        round(lat + delta_lat, 6),
    )


async def run_full_pipeline(
    post_image_bytes: bytes,
    lat: float,
    lng: float,
    radius_km: float = 2.0,
    pre_image_bytes: Optional[bytes] = None,
    demo_mode: bool = False,
) -> PipelineResult:
    """
    Master pipeline entry point.

    Args:
        post_image_bytes: Post-disaster satellite/drone image
        lat, lng: Center of area of interest
        radius_km: Analysis radius in km
        pre_image_bytes: Pre-disaster image. If None, the system auto-fetches
                         a baseline satellite tile from ESRI World Imagery (free).
        demo_mode: If True, returns pre-cached fixture instantly

    Returns:
        PipelineResult with all layers populated
    """
    import time
    t_start = time.monotonic()

    # ── Demo Mode ─────────────────────────────────────────────────────────────
    if demo_mode:
        logger.info("[Pipeline] DEMO MODE — loading pre-cached result")
        if DEMO_RESULT_PATH.exists():
            with open(DEMO_RESULT_PATH, "r", encoding="utf-8") as f:
                demo_data = json.load(f)
            result = PipelineResult(demo_mode=True)
            result.summary = demo_data.get("summary", {})
            result.duration_ms = round((time.monotonic() - t_start) * 1000, 1)
            # Attach features to result for cop_builder
            result._raw_geojson = demo_data
            return result
        else:
            logger.warning("[Pipeline] demo_result.json not found — falling back to live mode")

    # ── Live Mode ─────────────────────────────────────────────────────────────
    bbox = _lat_lng_to_bbox(lat, lng, radius_km)
    logger.info(f"[Pipeline] Starting live inference | bbox={bbox}")

    result = PipelineResult(demo_mode=False)

    # Step 1: Auto-fetch pre-image if not supplied
    if not pre_image_bytes and post_image_bytes:
        logger.info("[Pipeline] No pre-image supplied — auto-fetching baseline from ESRI World Imagery")
        from .pre_image_cache import fetch_pre_image
        pre_image_bytes = fetch_pre_image(lat, lng, radius_km, zoom=15)
        if pre_image_bytes:
            logger.info("[Pipeline] Pre-image ready (cached baseline) — running Siamese damage model")
        else:
            logger.warning("[Pipeline] Pre-image fetch failed — damage model will be skipped")

    # Step 2: Run all 3 models in parallel
    if pre_image_bytes:
        damage_task = _run_damage(pre_image_bytes, post_image_bytes, bbox)
    else:
        async def _no_damage():
            logger.warning("[Pipeline] No pre-image available — skipping damage model")
            return ModelResult()
        damage_task = _no_damage()

    flood_task     = _run_flood(post_image_bytes, bbox)
    landslide_task = _run_landslide(post_image_bytes, bbox)

    result.damage, result.flood, result.landslide = await asyncio.gather(
        damage_task, flood_task, landslide_task
    )

    logger.info(
        f"[Pipeline] Model confidences — "
        f"damage={result.damage.confidence:.2f} "
        f"flood={result.flood.confidence:.2f} "
        f"landslide={result.landslide.confidence:.2f}"
    )

    # Step 2: OSM building overlay (cache-first — never blocks on Overpass during demo)
    from .osm_overlay import get_buildings, overlay_damage_on_buildings

    buildings_geojson = get_buildings(bbox, allow_fetch=False)  # cache-only during API call
    result.building_damage_features = overlay_damage_on_buildings(
        result.damage.features, buildings_geojson
    )

    # Annotate image with OpenCV and return as base64
    try:
        import cv2
        import base64
        nparr = np.frombuffer(post_image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is not None:
            H, W = img.shape[:2]
            overlay = img.copy()
            
            if result.flood.mask is not None and result.flood.mask.max() > 0:
                flood_resized = cv2.resize(result.flood.mask.astype(np.uint8), (W, H), interpolation=cv2.INTER_NEAREST)
                overlay[flood_resized == 1] = (255, 0, 0) # BGR Blue
                
            if result.landslide.mask is not None and result.landslide.mask.max() > 0:
                landslide_resized = cv2.resize(result.landslide.mask.astype(np.uint8), (W, H), interpolation=cv2.INTER_NEAREST)
                overlay[landslide_resized == 1] = (200, 0, 200) # BGR Purple
                
            cv2.addWeighted(overlay, 0.5, img, 0.5, 0, img)
            _, buffer = cv2.imencode('.jpg', img)
            result.annotated_image_base64 = base64.b64encode(buffer).decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to annotate image: {e}")

    result.duration_ms = round((time.monotonic() - t_start) * 1000, 1)
    logger.info(f"[Pipeline] Complete in {result.duration_ms:.0f}ms")
    return result
