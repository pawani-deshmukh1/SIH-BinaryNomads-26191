"""
live_risk.py — GET /live-risk/

Fuses Layer A (static susceptibility) + Layer B (dynamic weather trigger)
into a single imminent risk assessment for a habitation coordinate.

This is the core pre-disaster alert engine:
  1. Layer A (proactive_engine): XGBoost terrain score → base risk
  2. Layer B (hazard_trigger): Live Open-Meteo 72h forecast → multiplier
  3. Combined: final zone_class that can ESCALATE from static Yellow → Critical Red

Demo case for judges:
  A habitation that is statically YELLOW (moderate terrain risk) can become
  RED in real-time when rainfall forecast crosses the critical threshold.
  This proves the two layers are independent and can disagree.
"""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from core.hazard_trigger import get_live_weather_trigger
import logging
import json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/live-risk", tags=["Layer B — Dynamic Risk Trigger"])


@router.get("/")
async def check_live_risk(
    lat: float = Query(..., description="Latitude of the habitation"),
    lng: float = Query(..., description="Longitude of the habitation"),
    habitation_id: str = Query(default=None, description="Habitation ID (to fetch advisory if RED)"),
    # Optional terrain overrides — if not provided, uses region defaults
    elevation: float = Query(default=80.0),
    slope: float = Query(default=10.0),
    aspect: float = Query(default=180.0),
    tri: float = Query(default=4.0),
    twi: float = Query(default=7.0),
    dist_to_river_m: float = Query(default=3000.0),
    precip_annual_mm: float = Query(default=1800.0),
    vegetation_proxy: float = Query(default=0.6),
    hand_proxy_m: float = Query(default=8.0),
):
    """
    Fused Layer A + Layer B imminent risk check.
    
    Returns:
      - layer_a: static susceptibility score (terrain-based, slow-changing)
      - layer_b: dynamic trigger (live weather, updated hourly)
      - final_zone: escalated zone (can be HIGHER than static zone if rain is critical)
      - advisory: human-readable alert message for dashboard
    """
    logger.info(f"[/live-risk] Fused risk check for {lat}, {lng}")

    # ── Layer A: Static Susceptibility ────────────────────────────────────────
    from core.proactive_engine import proactive_engine
    
    terrain_features = {}
    if habitation_id:
        import json
        from pathlib import Path
        hab_path = Path(__file__).resolve().parent.parent / "fixtures" / "habitations_assam.json"
        if hab_path.exists():
            with open(hab_path, "r", encoding="utf-8") as f:
                habs = json.load(f)
                hab = next((h for h in habs if h.get("id") == habitation_id), None)
                if hab:
                    terrain_features = {
                        "elevation": hab.get("elevation_m", elevation),
                        "slope": hab.get("slope_deg", slope),
                        "aspect": hab.get("aspect_deg", aspect),
                        "tri": hab.get("tri", tri),
                        "twi": hab.get("twi", twi),
                        "dist_to_river_m": hab.get("dist_to_river_m", dist_to_river_m),
                        "precip_annual_mm": hab.get("precip_annual_mm", precip_annual_mm),
                        "precip_daily_mm": 10.0,
                        "vegetation_proxy": hab.get("vegetation_proxy", vegetation_proxy),
                        "hand_proxy_m": hab.get("hand_proxy_m", hand_proxy_m),
                    }
                    
    if not terrain_features:
        terrain_features = {
            "elevation": elevation, "slope": slope, "aspect": aspect,
            "tri": tri, "twi": twi,
            "dist_to_river_m": dist_to_river_m,
            "precip_annual_mm": precip_annual_mm,
            "precip_daily_mm": 10.0,       # static baseline — Layer B provides the live value
            "vegetation_proxy": vegetation_proxy,
            "hand_proxy_m": hand_proxy_m,
        }
        
    layer_a = proactive_engine.score(terrain_features)

    # ── Layer B: Dynamic Weather Trigger ──────────────────────────────────────
    layer_b = await get_live_weather_trigger(lat, lng)

    # ── Fusion Logic: Escalate zone based on rainfall ─────────────────────────
    static_zone   = layer_a["zone_class"]
    trigger_status = layer_b.get("trigger_status", "STABLE")
    multiplier     = layer_b.get("risk_multiplier", 1.0)

    # Apply multiplier to combined score, re-classify
    base_score    = layer_a["combined_score"]
    dynamic_score = min(base_score * multiplier, 1.0)

    THRESHOLDS = {"RED": 0.70, "ORANGE": 0.45, "YELLOW": 0.25}
    if dynamic_score >= THRESHOLDS["RED"]:
        final_zone = "RED"
    elif dynamic_score >= THRESHOLDS["ORANGE"]:
        final_zone = "ORANGE"
    elif dynamic_score >= THRESHOLDS["YELLOW"]:
        final_zone = "YELLOW"
    else:
        final_zone = "GREEN"

    escalated = final_zone != static_zone and (
        ["GREEN", "YELLOW", "ORANGE", "RED"].index(final_zone) >
        ["GREEN", "YELLOW", "ORANGE", "RED"].index(static_zone)
    )

    # ── Advisory Generation ───────────────────────────────────────────────────
    rain_72h  = layer_b.get("rain_forecast_72h_mm", 0)
    rain_now  = layer_b.get("current_rain_mmhr", 0)

    if final_zone == "RED":
        advisory = (
            f"IMMINENT RISK: {rain_72h:.0f}mm forecast over 72h. "
            f"Terrain susceptibility {base_score:.0%}. "
            f"Recommend immediate pre-emptive relocation advisory."
        )
    elif final_zone == "ORANGE":
        advisory = (
            f"ELEVATED RISK: {rain_72h:.0f}mm forecast. "
            f"Monitor every 6 hours. Prepare relocation logistics."
        )
    elif final_zone == "YELLOW":
        advisory = f"WATCH: Moderate terrain risk. Current rainfall {rain_now:.1f}mm/hr. Continue monitoring."
    else:
        advisory = "STABLE: No imminent risk detected. Continue routine monitoring."

    # ── Auto-Attach Relocation Plan if high risk ──────────────────────────────
    relocation_plan = None
    if final_zone in ["RED", "ORANGE"] and habitation_id:
        from api.advisory import generate_advisory
        try:
            adv_resp = await generate_advisory(habitation_id)
            if adv_resp.status_code == 200:
                relocation_plan = json.loads(adv_resp.body.decode())["advisory"]
        except Exception as e:
            logger.error(f"Failed to auto-generate advisory for {habitation_id}: {e}")

    return JSONResponse(content={
        "status": "success",
        "coordinates": {"lat": lat, "lng": lng},
        "layer_a": {
            "static_zone": static_zone,
            "landslide_score": layer_a["landslide_score"],
            "flood_score": layer_a["flood_score"],
            "combined_score": base_score,
            "top_factors": layer_a["top_landslide_factors"],
            "model": layer_a["model_used"],
        },
        "layer_b": {
            "trigger_status": trigger_status,
            "risk_multiplier": multiplier,
            "rain_forecast_72h_mm": rain_72h,
            "current_rain_mmhr": rain_now,
            "raw": layer_b,
        },
        "fusion": {
            "dynamic_score": round(dynamic_score, 4),
            "final_zone": final_zone,
            "escalated_from_static": escalated,
            "advisory_text": advisory,
            "relocation_plan": relocation_plan
        }
    })
