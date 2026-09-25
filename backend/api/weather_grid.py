"""
weather_grid.py — GET /weather-grid/ endpoint

Provides a 0.5° × 0.5° grid of weather alerts for TV-style map overlays.
Fetches data concurrently from Open-Meteo for Assam or Kerala.
"""
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
import asyncio
import httpx
from datetime import datetime
import time

router = APIRouter(prefix="/weather-grid", tags=["Visual Overlays"])

# Simple in-memory cache to avoid hammering Open-Meteo
# Format: { "region": {"timestamp": 123456, "data": {...}} }
_CACHE = {}
CACHE_TTL_SECONDS = 900  # 15 minutes

def generate_grid(region: str) -> list[tuple[float, float]]:
    """Generate (lat, lng) pairs specifically for the habitations in the given region."""
    from pathlib import Path
    import json
    
    habs_path = Path(__file__).resolve().parent.parent / "fixtures" / f"habitations_{region}.json"
    if not habs_path.exists():
        return []
        
    try:
        with open(habs_path, "r", encoding="utf-8") as f:
            habs = json.load(f)
            
        # Keep habitation name with coordinates
        coords = {}
        for hab in habs:
            lat = round(float(hab.get("lat", 0)), 4)
            lng = round(float(hab.get("lng", 0)), 4)
            name = hab.get("name", "Unknown Area")
            if lat != 0 and lng != 0:
                coords[(lat, lng)] = name
        return list(coords.items())
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to load habitation coordinates for weather grid: {e}")
        return []

async def fetch_cell_weather(client: httpx.AsyncClient, lat: float, lng: float) -> dict:
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lng}"
        f"&daily=precipitation_sum,precipitation_probability_max,wind_speed_10m_max"
        f"&timezone=auto"
    )
    try:
        resp = await client.get(url, timeout=10.0)
        if resp.status_code == 200:
            data = resp.json()
            daily = data.get("daily", {})
            rain_24h = float(daily.get("precipitation_sum", [0])[0] or 0)
            precip_prob = float(daily.get("precipitation_probability_max", [0])[0] or 0)
            wind_max = float(daily.get("wind_speed_10m_max", [0])[0] or 0)
            
            alert = "clear"
            if rain_24h > 50.0:
                # If there's enough rain, run the XGBoost Heavy Rain onset model to check for cloudburst
                try:
                    from core.heavy_rain import evaluate_heavy_rain_onset
                    import asyncio
                    res = await asyncio.to_thread(evaluate_heavy_rain_onset, lat, lng)
                    if res.get("is_imminent"):
                        alert = "cloudburst"
                    elif res.get("risk_percentile", 0) > 85.0 or rain_24h > 100.0:
                        alert = "cloudburst"
                    else:
                        alert = "heavy_rain"
                except Exception as e:
                    # Fallback to simple rules if ML fails
                    if rain_24h > 100.0:
                        alert = "cloudburst"
                    else:
                        alert = "heavy_rain"
            elif precip_prob > 85.0 and wind_max > 50.0:
                alert = "cyclonic"
                
            return {
                "lat": lat,
                "lng": lng,
                "rain_24h": rain_24h,
                "precip_prob": precip_prob,
                "wind_max": wind_max,
                "alert": alert
            }
    except Exception:
        pass
    return {
        "lat": lat,
        "lng": lng,
        "alert": "clear",
        "rain_24h": 0,
        "precip_prob": 0,
        "wind_max": 0
    }

@router.get("/")
async def get_weather_grid(region: str = Query(default="assam", description="Region to fetch grid for")):
    region = region.lower()
    
    # Check cache
    now = time.time()
    if region in _CACHE:
        cached = _CACHE[region]
        if now - cached["timestamp"] < CACHE_TTL_SECONDS:
            return JSONResponse(content=cached["data"])
            
    grid_points = generate_grid(region)
    if not grid_points:
        raise HTTPException(status_code=400, detail="Invalid region. Use 'assam' or 'kerala'.")
        
    async with httpx.AsyncClient() as client:
        # grid_points is a list of ((lat, lng), name)
        tasks = [fetch_cell_weather(client, lat, lng) for (lat, lng), name in grid_points]
        results = await asyncio.gather(*tasks)
        
    features = []
    for ((lat, lng), name), r in zip(grid_points, results):
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [r["lng"], r["lat"]]
            },
            "properties": {
                "name": name,
                "alert_level": r["alert"],
                "rain_24h_mm": r["rain_24h"],
                "precipitation_probability": r["precip_prob"],
                "wind_speed_kmh": r["wind_max"],
                "source": "Open-Meteo Grid"
            }
        })
            
    feature_collection = {
        "type": "FeatureCollection",
        "region": region,
        "features": features,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Update cache
    _CACHE[region] = {
        "timestamp": now,
        "data": feature_collection
    }
    
    return JSONResponse(content=feature_collection)
