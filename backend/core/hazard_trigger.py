"""
hazard_trigger.py — Live Weather Trigger Engine (Layer B)
=========================================================
Fetches real-time and 72-hour forecast rainfall from Open-Meteo (WMO-standard).
Computes a CONTINUOUS risk_multiplier instead of a discrete lookup table.

Science basis:
  - Zhu et al. 2023 (Landslides, Springer): 72h cumulative forecast is the
    dominant landslide/flood trigger for NE India. Weighted at 0.50.
  - Current intensity (mm/hr) is secondary trigger. Weighted at 0.30.
  - Antecedent 30-day soil saturation proxy. Weighted at 0.20.

Multiplier range: [1.0, 3.0]
  1.0 = STABLE (no trigger)
  ~1.8 = ESCALATING (watch)
  >=2.5 = CRITICAL (evacuate)
"""
import asyncio
import httpx
from datetime import datetime, timedelta

# Saturation thresholds (calibrated for Brahmaputra basin)
INTENSITY_SATURATE_MM_HR   = 30.0   # 30mm/hr = cloudburst level
FORECAST_SATURATE_MM_72H   = 200.0  # 200mm/72h = extreme monsoon event
ANTECEDENT_SATURATE_MM_30D = 300.0  # 300mm/30d = near-saturated soil


def _compute_continuous_multiplier(
    current_rain_mm_hr: float,
    forecast_72h_mm: float,
    antecedent_30d_mm: float = 150.0,
) -> tuple:
    """
    Continuous risk multiplier based on 3 weighted components.
    Returns (multiplier: float, status: str).

    Zhu et al. 2023: cumulative 72h is the dominant trigger (0.50 weight).
    """
    intensity_score  = min(1.0, current_rain_mm_hr / INTENSITY_SATURATE_MM_HR)
    forecast_score   = min(1.0, forecast_72h_mm    / FORECAST_SATURATE_MM_72H)
    saturation_score = min(1.0, antecedent_30d_mm  / ANTECEDENT_SATURATE_MM_30D)

    # Weighted composite [0, 1]
    composite = (
        0.30 * intensity_score    # current rainfall intensity
      + 0.50 * forecast_score     # 72h forecast (dominant — Zhu 2023)
      + 0.20 * saturation_score   # antecedent soil saturation proxy
    )

    # Map composite [0,1] -> multiplier [1.0, 3.0]
    multiplier = round(1.0 + composite * 2.0, 2)

    # Human-readable status bands
    if composite >= 0.65:
        status = "CRITICAL"
    elif composite >= 0.35:
        status = "ESCALATING"
    else:
        status = "STABLE"

    # Flash Flood 3-hour short-window check (Layer 1 Bonus)
    # If intensity is extremely high in the immediate 3 hours, override to flash flood.
    # Note: We need the hourly data to do this properly, so we will do it outside this function.

    return multiplier, status


async def get_live_weather_trigger(lat: float, lng: float) -> dict:
    """
    Fetches real-time and 72-hour forecast rainfall from Open-Meteo.
    Also fetches last-30-day accumulated rainfall as antecedent saturation proxy.

    This is the 'Dynamic Risk Trigger' (Layer B) that sits on top of the
    static ML susceptibility models (Layer A).
    """
    forecast_url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lng}"
        f"&current=precipitation"
        f"&hourly=precipitation,cape"
        f"&forecast_days=3"
    )

    past_end   = datetime.utcnow().strftime("%Y-%m-%d")
    past_start = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
    archive_url = (
        f"https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lat}&longitude={lng}"
        f"&start_date={past_start}&end_date={past_end}"
        f"&daily=precipitation_sum"
    )

    try:
        async with httpx.AsyncClient() as client:
            forecast_resp, archive_resp = await asyncio.gather(
                client.get(forecast_url, timeout=8.0),
                client.get(archive_url,  timeout=8.0),
            )

            forecast_data = forecast_resp.json() if forecast_resp.status_code == 200 else {}
            archive_data  = archive_resp.json()  if archive_resp.status_code  == 200 else {}

            current_rain   = float(forecast_data.get("current", {}).get("precipitation", 0.0))
            hourly_rain    = forecast_data.get("hourly", {}).get("precipitation", [])
            hourly_cape    = forecast_data.get("hourly", {}).get("cape", [])
            forecast_72h   = float(sum(r for r in hourly_rain[:72] if r is not None) if hourly_rain else 0.0)
            short_window_3h = float(sum(r for r in hourly_rain[:3] if r is not None) if hourly_rain else 0.0)
            current_cape   = float(hourly_cape[0]) if hourly_cape and hourly_cape[0] is not None else 0.0
            
            daily_precip   = archive_data.get("daily", {}).get("precipitation_sum", [])
            antecedent_30d = float(sum(v for v in daily_precip if v is not None))

            multiplier, status = _compute_continuous_multiplier(
                current_rain, forecast_72h, antecedent_30d
            )
            
            # --- LAYER 1: Flash Flood Override ---
            if short_window_3h >= 25.0:  # 25mm in 3 hours is a flash flood threat for steep catchments
                status = "FLASH_FLOOD_WARNING"
                multiplier = max(multiplier, 2.8)
                
            # --- LAYER 0: Atmospheric Nowcasting (Cloudburst Risk) ---
            if current_cape > 1500:
                atmospheric_instability = "CRITICAL_CLOUDBURST_RISK"
            elif current_cape > 1000:
                atmospheric_instability = "ELEVATED"
            else:
                atmospheric_instability = "STABLE"

            return {
                "status":              "success",
                "current_rain_mm_hr":  round(current_rain,   2),
                "forecast_72h_mm":     round(forecast_72h,   1),
                "short_window_3h_mm":  round(short_window_3h, 1),
                "antecedent_30d_mm":   round(antecedent_30d, 1),
                "trigger_status":      status,
                "risk_multiplier":     multiplier,
                "current_cape_j_kg":   round(current_cape, 1),
                "atmospheric_instability": atmospheric_instability,
                "multiplier_method":   "continuous_weighted_composite",
                "source":              "Open-Meteo / WMO Standard",
            }

    except Exception as e:
        return {
            "status":              "error",
            "message":             str(e),
            "current_rain_mm_hr":  0.0,
            "forecast_72h_mm":     0.0,
            "short_window_3h_mm":  0.0,
            "antecedent_30d_mm":   0.0,
            "trigger_status":      "UNKNOWN",
            "risk_multiplier":     1.0,
            "current_cape_j_kg":   0.0,
            "atmospheric_instability": "UNKNOWN",
            "multiplier_method":   "fallback",
        }
