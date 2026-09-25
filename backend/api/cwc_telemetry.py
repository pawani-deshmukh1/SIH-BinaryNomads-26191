import os
import json
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/cwc", tags=["CWC Telemetry"])
CACHE_FILE = os.path.join(os.path.dirname(__file__), '..', 'fixtures', 'cwc_live_cache.json')

@router.get("/guwahati")
async def get_guwahati_telemetry():
    """
    Fetches the latest CWC flood telemetry for the Guwahati (Brahmaputra) gauge.
    Data is populated by the background Playwright scraper cron job.
    """
    if not os.path.exists(CACHE_FILE):
        # Return fallback if cache doesn't exist yet
        return {
            "station": "Guwahati (Brahmaputra)",
            "timestamp": "N/A",
            "water_level_m": 47.65,
            "danger_level_m": 49.68,
            "status": "AWAITING SCRAPE"
        }
        
    try:
        with open(CACHE_FILE, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read cache: {e}")
