from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Optional
from core.strategic_monitor import get_watchlist, get_trend_detail
from core.urban_flood_model import process_basins, run_backtest_validation
from core.dynamic_flood_risk import calculate_dynamic_risk
import subprocess
import os

router = APIRouter(prefix="/strategic", tags=["Strategic Monitoring (Layer 2)"])

@router.get("/watchlist")
def api_get_watchlist(threshold_months: int = 48):
    """Returns the ranked watchlist of habitations facing long-term structural threats."""
    return {"status": "success", "watchlist": get_watchlist(threshold_months)}

@router.get("/urban/guwahati")
def api_get_urban_guwahati():
    """Returns the detailed urban basin data for Guwahati with UFRI scores."""
    return {"status": "success", "basins": process_basins()}

@router.get("/urban/guwahati/dynamic-risk")
def api_get_dynamic_risk(rainfall_mm_hr: float = 0.0, river_level_m: float = 48.0):
    """Returns dynamic capacity deficit using Rational Method and Manning's."""
    results = calculate_dynamic_risk(rainfall_mm_hr, river_level_m)
    return {"status": "success", "scenarios": results}

@router.get("/urban/guwahati/backtest")
def api_get_urban_guwahati_backtest():
    """Returns the backtest validation hit-rate against historical events."""
    return {"status": "success", "backtest": run_backtest_validation()}

@router.get("/{hab_id}/detail")
def api_get_trend_detail(hab_id: str):
    """Returns the full 24-month time-series detail for a habitation."""
    detail = get_trend_detail(hab_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Habitation not found in strategic tracker")
    return {"status": "success", "detail": detail}

@router.get("/{hab_id}/evidence-summary")
def api_get_evidence_summary(hab_id: str):
    """Returns a summarized evidence block (Disaster History) for COP integration."""
    detail = get_trend_detail(hab_id)
    if not detail:
        return {
            "status": "success",
            "evidence": {
                "has_history": False,
                "known_event": "No major event on record — proactive monitoring active.",
                "trend_summary": "Stable",
                "monitor_type": None
            }
        }
    
    known_event = detail.get("known_event", "No specific historical event logged, but deterioration detected.")
    
    runway = detail.get("estimated_runway_months", [99])
    runway_val = runway[0] if isinstance(runway, list) else runway
    trend_summary = f"Critical ({runway_val} mos runway)" if runway_val <= 36 else "Worsening"

    return {
        "status": "success",
        "evidence": {
            "has_history": True,
            "known_event": known_event,
            "trend_summary": trend_summary,
            "monitor_type": detail.get("monitor_type"),
            "risk_class": detail.get("risk_class")
        }
    }

# Simple in-memory lock
JOB_STATE = {
    "status": "idle",
    "job_id": None
}

def run_extraction_script():
    global JOB_STATE
    try:
        # Path to the script relative to this file
        # backend/api/strategic.py -> backend/api -> backend -> root -> ml/coastal/generate_kerala_trends.py
        this_dir = os.path.dirname(__file__)
        script_path = os.path.join(this_dir, "..", "..", "ml", "coastal", "generate_kerala_trends.py")
        
        print("Starting background extraction script...")
        subprocess.run(["python", script_path], check=True)
        print("Background extraction complete.")
        JOB_STATE["status"] = "completed"
    except subprocess.CalledProcessError as e:
        print(f"Extraction failed: {e}")
        JOB_STATE["status"] = "error"
    except Exception as e:
        print(f"Unexpected error: {e}")
        JOB_STATE["status"] = "error"

@router.post("/run-analysis")
def run_analysis(background_tasks: BackgroundTasks):
    """
    Trigger the async CVI extraction process via Sentinel-2 GEE.
    Simulates the background job by calling the coastal extraction script.
    """
    global JOB_STATE
    if JOB_STATE["status"] == "running":
        return {"status": "running", "job_id": JOB_STATE["job_id"], "message": "Job already in progress."}

    JOB_STATE["status"] = "running"
    JOB_STATE["job_id"] = "latest"

    background_tasks.add_task(run_extraction_script)
    
    return {"status": "running", "job_id": JOB_STATE["job_id"]}

@router.get("/job-status")
def job_status():
    """
    Poll this endpoint to check the status of the extraction job.
    Returns: idle | running | completed | error
    """
    global JOB_STATE
    return {"status": JOB_STATE["status"]}

@router.post("/reset-job-status")
def reset_job_status():
    """
    Reset job status back to idle (useful after a completed job is acknowledged by UI).
    """
    global JOB_STATE
    JOB_STATE["status"] = "idle"
    return {"status": "idle"}

@router.get("/{hab_id}/timelapse")
def get_timelapse(hab_id: str):
    """
    Return the mock GeoJSON temporal analysis if available (e.g., for Kanjikuzhy)
    """
    if hab_id == "KERALA_COASTAL_005":
        this_dir = os.path.dirname(__file__)
        fixture_path = os.path.join(this_dir, "..", "fixtures", "coastal_timelapse_kanjikuzhy.json")
        if os.path.exists(fixture_path):
            import json
            with open(fixture_path, "r") as f:
                return json.load(f)
    return {"error": "No timelapse data available for this sector."}
