import httpx
from datetime import datetime, timedelta

async def get_live_weather_trigger(lat: float, lng: float) -> dict:
    """
    Fetches real-time and 72-hour forecast rainfall data from Open-Meteo API.
    This acts as the 'Dynamic Risk Trigger' (Layer B) that sits on top of the
    static ISRO/NASA susceptibility models (Layer A).
    """
    # Open-Meteo provides WMO-standard gridded data (DWD, NOAA, ECMWF)
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&current=precipitation&hourly=precipitation&forecast_days=3"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            
            # Current rainfall (mm)
            current_rain = data.get('current', {}).get('precipitation', 0.0)
            
            # Forecasted total rain for next 72 hours
            hourly_rain = data.get('hourly', {}).get('precipitation', [])
            forecast_72h_total = sum(hourly_rain) if hourly_rain else 0.0
            
            # --- Dynamic Trigger Logic ---
            # If current rain > 15mm/hr OR 72h forecast > 150mm -> CRITICAL TRIGGER
            trigger_status = "STABLE"
            risk_multiplier = 1.0
            
            if current_rain > 15.0 or forecast_72h_total > 150.0:
                trigger_status = "CRITICAL"
                risk_multiplier = 2.5 # Drastically increases the base ML risk score
            elif current_rain > 5.0 or forecast_72h_total > 50.0:
                trigger_status = "ESCALATING"
                risk_multiplier = 1.5
                
            return {
                "status": "success",
                "current_rain_mm_hr": current_rain,
                "forecast_72h_mm": forecast_72h_total,
                "trigger_status": trigger_status,
                "risk_multiplier": risk_multiplier,
                "source": "Open-Meteo / WMO Standard"
            }
            
    except Exception as e:
        # Fallback if API fails
        return {
            "status": "error",
            "message": str(e),
            "current_rain_mm_hr": 0.0,
            "forecast_72h_mm": 0.0,
            "trigger_status": "UNKNOWN",
            "risk_multiplier": 1.0
        }
