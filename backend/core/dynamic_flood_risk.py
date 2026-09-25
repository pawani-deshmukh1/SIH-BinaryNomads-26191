import json
import os
import math
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
GUWAHATI_FILE = FIXTURES_DIR / "urban_guwahati.json"

# Basin-specific Manning's assumptions
BASIN_PARAMS = {
    "GHY_BHARALU_CORE": {
        "n_roughness": 0.015,  # Concrete urban drain but debris-heavy
        "channel_width_m": 15.0,  # Narrowed to realistic choked width
        "channel_depth_m": 2.5,
        "channel_slope": 0.001,   # 0.1% slope (flat floodplain)
    },
    "GHY_DEEPOR_BEEL": {
        "n_roughness": 0.035,  # Earthen/Natural wetland outfall
        "channel_width_m": 60.0,
        "channel_depth_m": 3.0,
        "channel_slope": 0.001,
    },
    "GHY_SILSAKO_BEEL": {
        "n_roughness": 0.025,  # Mixed natural/encroached
        "channel_width_m": 30.0,
        "channel_depth_m": 2.5,
        "channel_slope": 0.001,
    }
}

# Runoff Coefficients (C)
C_BUILT = 0.85
C_WETLAND = 0.15
C_OTHER = 0.35

BRAHMAPUTRA_DANGER_LEVEL = 49.68
OUTFALL_ELEVATION = 47.0

def calculate_dynamic_risk(rainfall_mm_hr: float, river_level_m: float, dam_level_pct: float = 80.0):
    """
    Computes capacity deficit for Guwahati basins using:
    1. Rational Method (Q = CiA) for Runoff (with rough attenuation for large basins)
    2. Manning's Equation for Channel Capacity
    3. Backwater Effect from Brahmaputra River Level
    """
    if not GUWAHATI_FILE.exists():
        return []
        
    with open(GUWAHATI_FILE, 'r') as f:
        basins = json.load(f)
        
    results = []
    
    for basin in basins:
        bid = basin["basin_id"]
        if bid not in BASIN_PARAMS:
            continue
            
        params = BASIN_PARAMS[bid]
        geo = basin.get("basin_geometrics", {})
        
        # 1. Calculate Catchment Area (A) in square meters
        area_ha = geo.get("total_area_ha", 1000)
        area_m2 = area_ha * 10000.0
        
        # Apply a time-of-concentration storage attenuation factor (larger basins don't peak instantly)
        attenuation_factor = 1.0 if area_ha < 500 else 0.6
        
        # 2. Calculate Composite Runoff Coefficient (C)
        trend = basin.get("trend_series", [])
        if trend:
            latest = trend[-1]
            built_ha = latest.get("built_ha", 0)
            wetland_ha = latest.get("wetland_ha", 0)
        else:
            built_ha = 0
            wetland_ha = 0
            
        other_ha = max(0, area_ha - built_ha - wetland_ha)
        
        c_composite = ((built_ha * C_BUILT) + (wetland_ha * C_WETLAND) + (other_ha * C_OTHER)) / max(1, area_ha)
        
        # 3. Calculate Runoff Q (Rational Method)
        i_ms = rainfall_mm_hr / 3600000.0
        q_runoff = c_composite * i_ms * area_m2 * attenuation_factor
        
        # DAM RELEASE PENALTY: If Umiam is > 90%, massive external volume enters the system
        if dam_level_pct > 90.0:
            q_runoff *= 1.6
        
        # 4. Calculate Drain Capacity Q (Manning's)
        width = params["channel_width_m"]
        depth = params["channel_depth_m"]
        n = params["n_roughness"]
        
        a_cross = width * depth
        p_wetted = width + (2 * depth)
        r_hydraulic = a_cross / p_wetted
        
        # USE CHANNEL SLOPE, NOT TERRAIN SLOPE
        # Previously we used the steep mountain slopes (mean_slope_deg) which made drainage infinite
        slope_m_per_m = params["channel_slope"]
        
        # BACKWATER CORRECTION: Only choke the flow when river exceeds the outfall elevation (47.0m)
        if river_level_m <= OUTFALL_ELEVATION:
            gravity_ratio = 1.0
        else:
            # Drops from 1.0 to 0.0 as river rises from 47.0 to 49.68
            gravity_ratio = max(0.0, 1.0 - ((river_level_m - OUTFALL_ELEVATION) / (BRAHMAPUTRA_DANGER_LEVEL - OUTFALL_ELEVATION)))
            
        effective_slope = slope_m_per_m * (gravity_ratio ** 2) 
        
        q_capacity = (1.0 / n) * a_cross * (r_hydraulic ** (2/3)) * (effective_slope ** 0.5)
        
        # 5. Capacity Deficit %
        if q_capacity <= 0.1:
            deficit_pct = q_runoff * 100 # effectively infinite if river is at danger level
        else:
            deficit_pct = max(0.0, (q_runoff - q_capacity) / q_capacity * 100.0)
            
        # 6. Risk Level
        if deficit_pct == 0:
            risk_level = "LOW"
        elif deficit_pct < 50:
            risk_level = "MODERATE"
        elif deficit_pct < 150:
            risk_level = "HIGH"
        else:
            risk_level = "CRITICAL"
            
        results.append({
            "basin_id": bid,
            "name": basin["name"],
            "q_runoff_m3s": round(q_runoff, 2),
            "q_capacity_m3s": round(q_capacity, 2),
            "capacity_deficit_pct": round(deficit_pct, 1),
            "risk_level": risk_level,
            "c_composite": round(c_composite, 3),
            "effective_slope": round(effective_slope, 5)
        })
        
    return results
