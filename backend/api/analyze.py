"""
analyze.py — POST /analyze/ master endpoint.

One endpoint to run the full DISHA pipeline:
  1. Accepts pre + post imagery (or just post)
  2. Runs all 3 models in parallel
  3. Cross-references damage with OSM buildings
  4. Fuses hazard layers into red zones
  5. Attaches evac sites, routes, tower risk
  6. Returns one unified GeoJSON FeatureCollection

demo_mode=true skips inference and returns pre-cached fixtures instantly.
"""
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
import json
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analyze", tags=["COP Pipeline"])


@router.post("/")
async def analyze_area(
    post_image: UploadFile = File(...),
    pre_image: Optional[UploadFile] = File(default=None),
    lat: float = Form(...),
    lng: float = Form(...),
    radius_km: float = Form(default=2.0),
    demo_mode: bool = Form(default=False),
    region: str = Form(default="assam"),
    damage_weight: float = Form(default=0.5),
    flood_weight: float = Form(default=0.25),
    landslide_weight: float = Form(default=0.25),
):
    """
    Run the full DISHA Common Operational Picture pipeline.

    Returns a single GeoJSON FeatureCollection containing ALL layers:
    - building_damage: per-building OSM-cross-referenced damage assessment
    - flood_zone: flood extent polygons
    - landslide_zone: landslide hazard polygons
    - red_zone: fused risk polygons (AHP-weighted)
    - evac_site: ranked evacuation candidate sites
    - evac_route: hazard-aware routing geometries
    - tower: cell tower status (operational / at_risk)

    Use demo_mode=true for instant pre-cached results (no GPU needed).
    """
    # ── Weight validation ─────────────────────────────────────────────────────
    weight_sum = round(damage_weight + flood_weight + landslide_weight, 4)
    if abs(weight_sum - 1.0) > 0.05:
        raise HTTPException(
            status_code=422,
            detail=f"Weights must sum to 1.0. Got {weight_sum}."
        )

    # ── Demo Mode ─────────────────────────────────────────────────────────────
    if demo_mode:
        logger.info("[/analyze] Demo mode requested")
        from core.cop_builder import build_cop_from_demo
        from core.analysis_state import set_last_cop
        result_geojson = build_cop_from_demo()
        set_last_cop(result_geojson)
        
        # Trigger background relocation refresh
        import asyncio
        asyncio.create_task(_refresh_relocation_plan(region))
        return JSONResponse(content=result_geojson)

    # ── Live Pipeline ─────────────────────────────────────────────────────────
    try:
        post_bytes = await post_image.read()
        pre_bytes  = await pre_image.read() if pre_image else None

        from core.pipeline import run_full_pipeline
        pipeline_result = await run_full_pipeline(
            post_image_bytes=post_bytes,
            lat=lat,
            lng=lng,
            radius_km=radius_km,
            pre_image_bytes=pre_bytes,
            demo_mode=False,
        )

        if pipeline_result.error:
            raise HTTPException(status_code=500, detail=pipeline_result.error)

        # Assemble COP
        from core.cop_builder import build_cop

        model_confidences = {
            "damage": {
                "score": pipeline_result.damage.confidence,
                "score_type": "model_confidence",
                "last_updated": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
            },
            "flood": {
                "score": pipeline_result.flood.confidence,
                "score_type": "model_confidence",
                "last_updated": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
            },
            "landslide": {
                "score": pipeline_result.landslide.confidence,
                "score_type": "model_confidence",
                "last_updated": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
            },
        }

        cop = build_cop(
            damage_features=pipeline_result.damage.features,
            flood_features=pipeline_result.flood.features,
            landslide_features=pipeline_result.landslide.features,
            building_damage_features=pipeline_result.building_damage_features,
            model_confidences=model_confidences,
            region_key=region,
            damage_weight=damage_weight,
            flood_weight=flood_weight,
            landslide_weight=landslide_weight,
            duration_ms=pipeline_result.duration_ms,
            demo_mode=False,
        )

        from core.analysis_state import set_last_cop
        set_last_cop(cop)
        
        # Inject the annotated image directly into the final API payload
        if hasattr(pipeline_result, "annotated_image_base64"):
            cop["annotated_image_base64"] = pipeline_result.annotated_image_base64

        # Trigger background relocation refresh
        import asyncio
        asyncio.create_task(_refresh_relocation_plan(region))

        return JSONResponse(content=cop)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[/analyze] Pipeline error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")


@router.get("/demo")
async def analyze_demo():
    """
    GET shortcut — returns the pre-cached demo COP instantly.
    Use this for quick dashboard testing without uploading images.
    """
    from core.cop_builder import build_cop_from_demo
    return JSONResponse(content=build_cop_from_demo())


@router.post("/video")
async def analyze_video(
    post_video: UploadFile = File(...),
    lat: float = Form(...),
    lng: float = Form(...),
    radius_km: float = Form(default=2.0),
    region: str = Form(default="assam"),
    damage_weight: float = Form(default=0.5),
    flood_weight: float = Form(default=0.25),
    landslide_weight: float = Form(default=0.25),
):
    """
    Video processing endpoint. Streams progress via Server-Sent Events (SSE).
    Extracts frames, runs flood and landslide models on each frame,
    aggregates masks, and returns the final COP.
    """
    video_bytes = await post_video.read()

    async def event_generator():
        yield f"data: {json.dumps({'status': 'extracting'})}\n\n"
        
        from core.video_processor import extract_frames
        # We block the thread here but for demo it's acceptable.
        # Alternatively we could run in executor, but this is simpler.
        frames = extract_frames(video_bytes, sample_every_n_seconds=2.0)
        
        total = len(frames)
        yield f"data: {json.dumps({'status': 'extracted', 'frames_total': total})}\n\n"
        
        if total == 0:
            yield f"data: {json.dumps({'status': 'error', 'error': 'No frames extracted'})}\n\n"
            return
            
        from core.pipeline import _lat_lng_to_bbox, _run_flood, _run_landslide
        from core.mask_aggregator import aggregate_masks
        
        bbox = _lat_lng_to_bbox(lat, lng, radius_km)
        
        flood_masks = []
        flood_confs = []
        landslide_masks = []
        landslide_confs = []
        
        import time
        t_start = time.monotonic()
        
        for i, frame in enumerate(frames):
            yield f"data: {json.dumps({'status': 'processing', 'frame': i+1, 'of': total})}\n\n"
            
            f_res = await _run_flood(frame, bbox)
            l_res = await _run_landslide(frame, bbox)
            
            flood_masks.append(f_res.mask)
            flood_confs.append(f_res.confidence)
            landslide_masks.append(l_res.mask)
            landslide_confs.append(l_res.confidence)
            
        # Aggregate
        f_merged_mask, f_conf = aggregate_masks(flood_masks, flood_confs)
        l_merged_mask, l_conf = aggregate_masks(landslide_masks, landslide_confs)
        
        # Convert to features
        from core.mask_to_geojson import flood_mask_to_features, landslide_mask_to_features
        f_features = flood_mask_to_features(f_merged_mask, bbox, f_conf) if f_merged_mask is not None else []
        l_features = landslide_mask_to_features(l_merged_mask, bbox, l_conf) if l_merged_mask is not None else []
        
        model_confidences = {
            "damage": {"score": 0.0, "score_type": "model_confidence"},
            "flood": {"score": f_conf, "score_type": "model_confidence"},
            "landslide": {"score": l_conf, "score_type": "model_confidence"}
        }
        
        from core.cop_builder import build_cop
        cop = build_cop(
            damage_features=[],
            flood_features=f_features,
            landslide_features=l_features,
            building_damage_features=[],
            model_confidences=model_confidences,
            region_key=region,
            damage_weight=damage_weight,
            flood_weight=flood_weight,
            landslide_weight=landslide_weight,
            duration_ms=round((time.monotonic() - t_start) * 1000, 1),
            demo_mode=False
        )
        
        from core.analysis_state import set_last_cop
        set_last_cop(cop)
        
        import asyncio
        asyncio.create_task(_refresh_relocation_plan(region))
        
        yield f"data: {json.dumps({'status': 'complete', 'cop': cop})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")



async def _refresh_relocation_plan(region: str):
    """Background task to re-run the relocation optimizer with fresh red zones."""
    try:
        from api.relocation import get_relocation_plan
        # get_relocation_plan handles reading the fresh red zones and re-running optimization
        plan_dict = get_relocation_plan(region=region)
        logger.info(f"[/analyze] Background relocation refresh complete for region={region}")
    except Exception as e:
        logger.error(f"[/analyze] Background relocation refresh failed: {e}")

