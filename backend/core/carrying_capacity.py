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
from core.settings import get_settings

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
    return int(site_area_sqm / get_settings().sphere_standards.m2_per_person)

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
    settings = get_settings()
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
        if terrain.get("slope", 0) > settings.sphere_standards.max_slope_deg:
            reasons.append(f"Terrain too steep for camp (Slope: {terrain['slope']}° > {settings.sphere_standards.max_slope_deg}°)")
        if distance_km > settings.sphere_standards.max_distance_km:
            reasons.append(f"Too far from habitation ({distance_km:.1f}km > {settings.sphere_standards.max_distance_km}km)")
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
        prox_score = max(0.0, 1.0 - (distance_km / settings.sphere_standards.max_distance_km))
        
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
    settings = get_settings()
    return {
        "tents_50_person": math.ceil(population / 50.0),
        "water_litres_per_day": population * settings.sphere_standards.water_litres_per_person,
        "total_water_litres": population * settings.sphere_standards.water_litres_per_person * days,
        "food_rations_daily": population,
        "duration_days": days
    }


def find_host_community_habitations(
    habitations: List[Dict[str, Any]],
    displaced_hab_id: str,
    displaced_population: int,
    hab_lat: float,
    hab_lng: float,
    formal_camp_distance_km: float,
    max_radius_km: float = 15.0,
    min_spare_capacity_pct: float = 0.30,
) -> List[Dict[str, Any]]:
    """
    Finds nearby GREEN/YELLOW zone habitations that can act as host communities.

    A habitation qualifies as a host if:
      1. It is NOT the displaced habitation itself.
      2. It is CLOSER than the nearest formal relief camp.
         (No benefit in showing it if the formal camp is already nearer.)
      3. It scores GREEN or YELLOW via the XGBoost models.
      4. It has >= 30% spare hosting headroom above its own population.

    Structural capacity estimate (conservative Sphere-aligned):
      Each household can reasonably host ~4 extra displaced people in an emergency.
      host_capacity = households * 4
    """
    host_candidates = []

    for hab in habitations:
        if str(hab.get("id", "")) == str(displaced_hab_id):
            continue

        dist_km = haversine(hab_lat, hab_lng, float(hab.get("lat", 0)), float(hab.get("lng", 0)))
        if dist_km > max_radius_km:
            continue
        if dist_km >= formal_camp_distance_km:
            continue  # Formal camp is already closer, no benefit

        terrain = {
            "elevation":        hab.get("elevation_m", 80.0),
            "slope":            hab.get("slope_deg", 8.0),
            "aspect":           hab.get("aspect_deg", 180.0),
            "tri":              hab.get("tri", 4.0),
            "twi":              hab.get("twi", 7.0),
            "dist_to_river_m":  hab.get("dist_to_river_m", 3000.0),
            "precip_annual_mm": hab.get("precip_annual_mm", 1800.0),
            "precip_daily_mm":  hab.get("precip_daily_mm", 12.0),
            "vegetation_proxy": hab.get("vegetation_proxy", 0.6),
            "hand_proxy_m":     hab.get("hand_proxy_m", 8.0),
        }
        score = proactive_engine.score(terrain)
        if score["zone_class"] not in ("GREEN", "YELLOW"):
            continue

        households = int(hab.get("households", 0))
        own_population = int(hab.get("population", 0))
        host_capacity = households * 4
        spare_pct = host_capacity / max(1, own_population)

        if spare_pct < min_spare_capacity_pct:
            continue

        can_host_all = host_capacity >= displaced_population

        host_candidates.append({
            "id":                 hab.get("id", ""),
            "name":               hab.get("name", "Unknown"),
            "type":               hab.get("type", ""),
            "type_label":         hab.get("type_label", ""),
            "district":           hab.get("district", ""),
            "lat":                hab.get("lat", 0),
            "lng":                hab.get("lng", 0),
            "own_population":     own_population,
            "households":         households,
            "host_capacity":      host_capacity,
            "can_host_all":       can_host_all,
            "spare_capacity_pct": round(spare_pct * 100, 1),
            "distance_km":        round(dist_km, 2),
            "distance_saving_km": round(formal_camp_distance_km - dist_km, 2),
            "zone_class":         score["zone_class"],
            "flood_score":        round(score["flood_score"], 4),
            "landslide_score":    round(score["landslide_score"], 4),
            "road_accessible":    hab.get("road_accessible", True),
            "nearest_road_km":    hab.get("nearest_road_km", 0),
            "shelter_type":       "host_community",
            "note": (
                f"Can host all {displaced_population} displaced people." if can_host_all
                else f"Can host {host_capacity} of {displaced_population} (partial shelter)."
            )
        })

    host_candidates.sort(key=lambda x: x["distance_km"])
    return host_candidates
