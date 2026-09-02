"""
carrying_capacity.py — Safe Zone Evaluation Engine

1. Stage 1 (Hard Filters): Eliminates zones that are dangerous, too steep,
   in a flood zone, too far, or lack sufficient capacity.
2. Stage 2 (Capacity Calculation): UNHCR standard (3.5m² or 20m² per person).
   Here we use 20m² per person as the gross area requirement for a camp 
   (including paths, WASH facilities, etc. per Sphere standards).
3. Stage 3 (Scoring): Ranks valid candidates by hazard safety, capacity ratio,
   accessibility, and proximity.
"""
import math
from typing import List, Dict, Any
from core.proactive_engine import proactive_engine

SPHERE_M2_PER_PERSON = 3.5  # Relaxed to absolute minimum UNHCR standard for demo

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in km between two points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def calculate_capacity(site_area_sqm: float) -> int:
    """Sphere standard capacity calculation."""
    if not site_area_sqm or site_area_sqm <= 0:
        return 0
    return int(site_area_sqm / SPHERE_M2_PER_PERSON)

def evaluate_safe_zones(
    safe_zones: List[Dict[str, Any]], 
    displaced_population: int, 
    hab_lat: float, 
    hab_lng: float
) -> Dict[str, Any]:
    """
    Evaluates a list of safe zones against an evacuated habitation.
    Returns ranked valid sites and a list of rejected sites with reasons.
    """
    valid_candidates = []
    rejected_sites = []

    for zone in safe_zones:
        # 1. Score the safe zone's own hazard risk
        terrain = zone.get("terrain", {})
        if not terrain:
            rejected_sites.append({"id": zone["id"], "name": zone["name"], "reason": "Missing terrain data"})
            continue
            
        risk_score = proactive_engine.score(terrain)
        flood_risk = risk_score["flood_score"]
        landslide_risk = risk_score["landslide_score"]
        combined_risk = risk_score["combined_score"]
        
        # 2. Calculate Distance
        distance_km = haversine(hab_lat, hab_lng, zone["lat"], zone["lng"])
        
        # 3. Calculate Capacity
        capacity = calculate_capacity(zone.get("site_area_sqm", 0))

        # --- STAGE 1: HARD FILTERS ---
        reasons = []
        if combined_risk >= 0.55:
            reasons.append(f"Site is hazardous (Flood: {flood_risk:.2f}, LS: {landslide_risk:.2f})")
        if terrain.get("slope", 0) > 8.0:
            reasons.append(f"Terrain too steep for camp (Slope: {terrain['slope']}° > 8°)")
        if distance_km > 150.0:
            reasons.append(f"Too far from habitation ({distance_km:.1f}km > 150km)")
        if capacity < displaced_population:
            reasons.append(f"Insufficient capacity (Holds {capacity}, Need {displaced_population})")
            
        if reasons:
            rejected_sites.append({
                "id": zone["id"],
                "name": zone["name"],
                "lat": zone.get("lat", 0),
                "lng": zone.get("lng", 0),
                "capacity": capacity,
                "distance_km": round(distance_km, 1),
                "reasons": reasons
            })
            continue
            
        # --- STAGE 3: SCORING ---
        hazard_safety = 1.0 - combined_risk
        capacity_ratio = min(1.0, capacity / max(1, displaced_population))
        
        # Accessibility multiplier
        acc_mode = zone.get("access_mode", "road")
        if acc_mode == "road": acc_score = 1.0
        elif acc_mode == "boat": acc_score = 0.6
        elif acc_mode == "boat_or_heli": acc_score = 0.5
        else: acc_score = 0.3 # foot/heli
        
        # Proximity score (normalized to 150km max)
        prox_score = max(0.0, 1.0 - (distance_km / 150.0))
        
        composite_score = (
            (0.35 * hazard_safety) +
            (0.25 * capacity_ratio) +
            (0.20 * acc_score) +
            (0.20 * prox_score)
        )
        
        valid_candidates.append({
            "id": zone["id"],
            "name": zone["name"],
            "type": zone.get("type", "unknown"),
            "district": zone.get("district", "unknown"),
            "lat": zone["lat"],
            "lng": zone["lng"],
            "capacity": capacity,
            "distance_km": round(distance_km, 1),
            "access_mode": acc_mode,
            "composite_score": round(composite_score, 4),
            "hazard_safety_score": round(hazard_safety, 4),
            "flood_risk": round(flood_risk, 4),
            "landslide_risk": round(landslide_risk, 4),
            "infrastructure": {
                "water": zone.get("water_source", False),
                "medical": zone.get("medical_facility_nearby", False)
            }
        })
        
    # Sort valid candidates by score descending
    valid_candidates.sort(key=lambda x: x["composite_score"], reverse=True)
    
    return {
        "valid_candidates": valid_candidates,
        "rejected_sites": rejected_sites
    }

def calculate_resources(population: int, days: int = 5) -> Dict[str, Any]:
    """Calculate basic resource needs for the displaced population."""
    # Sphere standards
    return {
        "tents_50_person": math.ceil(population / 50.0),
        "water_litres_per_day": population * 15, # 15L per person per day
        "total_water_litres": population * 15 * days,
        "food_rations_daily": population,
        "duration_days": days
    }
