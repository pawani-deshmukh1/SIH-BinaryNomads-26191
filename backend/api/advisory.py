"""
advisory.py — GET /advisory/{habitation_id}

Generates a structured relocation advisory for an at-risk habitation.
1. Loads the habitation from fixtures.
2. Loads available safe zones from fixtures.
3. Evaluates all safe zones against the habitation's population and location.
4. Generates a Sphere-standard resource plan.
"""
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
import json
from pathlib import Path # Trigger hot reload
from core.carrying_capacity import evaluate_safe_zones, calculate_resources, find_host_community_habitations
from core.hazard_trigger import get_live_weather_trigger
from core.proactive_engine import proactive_engine
from api.routes import get_reachable_route, get_safe_route, ReachableRouteRequest, SafeZoneCandidate
from core.flood_inundation import compute_inundation_scenarios

from functools import lru_cache

router = APIRouter(prefix="/advisory", tags=["Relocation Advisory"])

# Removed lru_cache to ensure fresh data loads and trigger uvicorn hot reload
def load_json_fixture(filename: str):
    path = Path(__file__).resolve().parent.parent / "fixtures" / filename
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@router.get("/safe-zones")
async def get_all_safe_zones(region: str = Query(default="assam")):
    """Return all safe zones in the region as a GeoJSON FeatureCollection."""
    safe_zones = load_json_fixture(f"safe_zones_{region}.json")
    
    features = []
    for sz in safe_zones:
        # Calculate new relaxed capacity based on SPHERE_M2_PER_PERSON = 3.5
        capacity = int(sz.get("site_area_sqm", 0) / 3.5)
        
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [sz.get("lng", 0), sz.get("lat", 0)]
            },
            "properties": {
                "id": sz.get("id", ""),
                "name": sz.get("name", "Unknown Safe Zone"),
                "capacity": capacity,
                "district": sz.get("district", ""),
                "type": sz.get("type", "safe_zone")
            }
        })
        
    return JSONResponse(content={
        "type": "FeatureCollection",
        "features": features,
        "metadata": {"total": len(features)}
    })

@router.get("/{habitation_id}")
async def generate_advisory(habitation_id: str, region: str = Query(default="assam")):
    """
    Generate a full relocation advisory for a specific habitation.
    Finds the best safe zone that passes all hard filters (capacity, distance, hazard).
    """
    # 1. Load data
    habitations = load_json_fixture(f"habitations_{region}.json")
    safe_zones = load_json_fixture(f"safe_zones_{region}.json")
    
    hab = next((h for h in habitations if h["id"] == habitation_id), None)
    if not hab:
        raise HTTPException(status_code=404, detail="Habitation not found")
        
    pop = hab.get("population", 0)
    if pop == 0:
        raise HTTPException(status_code=400, detail="Habitation has no population data")
        
    # 2. Get live weather trigger for context
    live_trigger = await get_live_weather_trigger(hab["lat"], hab["lng"])
    
    # 3. Run proactive engine for SHAP risk explanation
    risk_score_result = proactive_engine.score({
        "lat": hab["lat"], "lng": hab["lng"],
        "elevation":       hab.get("elevation_m", 100.0),
        "slope":           hab.get("slope_deg", 10.0),
        "aspect":          hab.get("aspect_deg", 180.0),
        "tri":             hab.get("tri", 5.0),
        "twi":             hab.get("twi", 6.0),
        "dist_to_river_m": hab.get("dist_to_river_m", 500.0),
        "precip_annual_mm":hab.get("precip_annual_mm", 1800.0),
        "precip_daily_mm": live_trigger.get("current_rain_mm_hr", 10.0),
        "vegetation_proxy":hab.get("vegetation_proxy", 0.5),
        "hand_proxy_m":    hab.get("hand_proxy_m", 5.0),
    })

    # 4. Evaluate Safe Zones (Check Dynamic Relocation Plan first)
    from core.analysis_state import get_last_relocation
    last_plan = get_last_relocation()
    
    hab_assignments = []
    if last_plan:
        hab_assignments = [a for a in last_plan.get("assignments", []) if str(a["habitation_id"]) == str(habitation_id)]
        
    if hab_assignments:
        # Use dynamic assignments
        primary = hab_assignments[0]
        site_id = primary["site_id"]
        sz_match = next((sz for sz in safe_zones if sz.get("id") == site_id), {})
        
        best_site = {
            "id": site_id,
            "name": primary["site_name"],
            "distance_km": primary["distance_km"],
            "access_mode": "ROAD", # Simplification
            "hazard_safety_score": primary["recommendation_score"],
            "capacity": primary["population"], # Actually assigned population
            "is_overflow": primary.get("is_overflow", False),
            "lat": sz_match.get("lat", primary.get("site_lat", 0)),
            "lng": sz_match.get("lng", primary.get("site_lng", 0))
        }
        
        overflow_sites = []
        for overflow in hab_assignments[1:]:
            overflow_sites.append({
                "id": overflow["site_id"],
                "name": overflow["site_name"],
                "distance_km": overflow["distance_km"],
                "assigned_population": overflow["population"],
                "is_overflow": overflow.get("is_overflow", True)
            })
            
        valid_candidates = [best_site] + overflow_sites
        rejected_sites = []
    else:
        # Fallback to static evaluation if optimizer hasn't run
        evaluation = evaluate_safe_zones(
            safe_zones=safe_zones,
            displaced_population=pop,
            hab_lat=hab["lat"],
            hab_lng=hab["lng"]
        )
        valid_candidates = evaluation["valid_candidates"]
        rejected_sites = evaluation["rejected_sites"]
        
        if not valid_candidates:
            return JSONResponse(status_code=404, content={
                "status": "error",
                "message": "NO VALID SAFE ZONES FOUND. All candidates failed hard filters.",
                "rejected_sites": rejected_sites
            })
        
        # Check routing reachability
        # Skip dynamic DEM flood simulation here to prevent massive loading delays
        flood_geojson = None
            
        candidates_list = []
        for c in valid_candidates:
            candidates_list.append(SafeZoneCandidate(
                id=c["id"], name=c["name"], lat=c["lat"], lng=c["lng"], access_mode=c.get("access_mode", "road")
            ))
            
        routing_req = ReachableRouteRequest(
            origin_lat=hab["lat"],
            origin_lng=hab["lng"],
            candidates=candidates_list,
            flood_geojson=flood_geojson
        )
        
        routing_decision = get_reachable_route(routing_req)
        
        if routing_decision["routing_decision"] == "ISOLATED_ALL":
             return JSONResponse(status_code=404, content={
                "status": "error",
                "message": "NO VALID SAFE ZONES REACHABLE BY ANY MEANS.",
                "rejected_sites": rejected_sites + routing_decision.get("rejected_zones", [])
            })
            
        selected_id = routing_decision["selected_zone_id"]
        best_site = next((c for c in valid_candidates if c["id"] == selected_id), valid_candidates[0])
        overflow_sites = []
        rejected_sites.extend(routing_decision.get("rejected_zones", []))
        
        verified_route = routing_decision.get("route_geojson")
        evac_mode = routing_decision.get("evacuation_mode", "road")
        route_status = routing_decision.get("route_status", "CLEAR")
    
    # 5. Calculate Resource Needs
    resources = calculate_resources(pop)

    # 6. Find nearby safe habitations as host community alternatives
    #    Only shown if they are closer than the formal relief camp.
    #    Search radius scales with how far the formal camp is:
    #    up to half the camp's distance, capped at 60km.
    formal_camp_dist = best_site.get("distance_km", 9999.0)
    dynamic_radius = min(formal_camp_dist * 0.55, 60.0)  # search 55% of camp distance, max 60km
    host_options = find_host_community_habitations(
        habitations=habitations,
        displaced_hab_id=habitation_id,
        displaced_population=pop,
        hab_lat=hab["lat"],
        hab_lng=hab["lng"],
        formal_camp_distance_km=formal_camp_dist,
        max_radius_km=dynamic_radius,
    )

    # 7. Pre-compute road routes for host community options
    #    Uses the same file-backed route_cache.json as formal camps.
    #    First call downloads OSMnx/OSRM (slow, one-time). Subsequent calls are instant.
    #    People split equally among available host communities for resource distribution.
    num_hosts = len(host_options)
    pop_per_host = (pop // num_hosts) if num_hosts > 0 else 0
    pop_remainder = pop - (pop_per_host * num_hosts)  # first host gets any remainder

    enriched_host_options = []
    for i, h in enumerate(host_options):
        try:
            route = get_safe_route(
                origin_lat=hab["lat"],
                origin_lon=hab["lng"],
                dest_lat=h["lat"],
                dest_lon=h["lng"],
                flood_geojson=None,  # no flood overlay for host routes
            )
        except Exception:
            route = None

        # Population split: divide evenly, first host gets remainder people
        assigned_pop = pop_per_host + (pop_remainder if i == 0 else 0)
        h_enriched = dict(h)
        h_enriched["route_geojson"] = route
        h_enriched["assigned_population"] = assigned_pop
        h_enriched["note"] = (
            f"Hosts {assigned_pop} of {pop} displaced people ({round(assigned_pop/pop*100)}%). "
            + ("Full capacity available." if h["can_host_all"] else f"Partial shelter — max {h['host_capacity']} pax.")
        )
        enriched_host_options.append(h_enriched)

    host_options = enriched_host_options
    
    # Calculate Lead Time
    combined_score = risk_score_result.get("combined_score", 0.8)
    lead_time_hrs = max(6, round((1.0 - combined_score) * 72))
    
    # 6. Generate structured advisory
    advisory = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "urgency": "CRITICAL",
        "estimated_lead_time_hrs": lead_time_hrs,
        "habitation": {
            "id": hab["id"],
            "name": hab["name"],
            "type": hab.get("type"),
            "population": pop,
            "households": hab.get("households", 0),
            "vulnerability_sc_st_pct": hab.get("sc_st_percent", 0),
            "women_percent": hab.get("women_percent", 49),
            "children_percent": hab.get("children_percent", 29),
            "elderly_percent": hab.get("elderly_percent", 8)
        },
        "trigger": {
            "reason": "Risk threshold exceeded",
            "live_weather": live_trigger
        },
        "risk_explanation": {
            "flood":     risk_score_result.get("flood_explanation", {}),
            "landslide": risk_score_result.get("landslide_explanation", {}),
            "zone_class": risk_score_result.get("zone_class", "RED"),
            "combined_score": risk_score_result.get("combined_score", 0.0),
        },
        "relocation_plan": {
            "recommended_site": best_site,
            "routing_decision": routing_decision.get("routing_decision", "REACHABLE") if 'routing_decision' in locals() else "REACHABLE",
            "evacuation_mode": evac_mode if 'evac_mode' in locals() else best_site.get("access_mode", "road"),
            "verified_route": verified_route if 'verified_route' in locals() else None,
            "route_status": route_status if 'route_status' in locals() else "CLEAR",
            "routing_rejected_zones": routing_decision.get("rejected_zones", []) if 'routing_decision' in locals() else [],
            "overflow_sites": overflow_sites, # Newly added for capacity load balancing
            "alternative_sites": valid_candidates[1:3] if not overflow_sites else [],
            "logistics": {
                "evacuation_mode": evac_mode if 'evac_mode' in locals() else best_site.get("access_mode", "ROAD"),
                "distance_km": best_site.get("distance_km", 0),
            },
            "resources_required": resources
        },
        "host_community_options": host_options,
        "rejected_sites_log": rejected_sites
    }
    
    return JSONResponse(content={"status": "success", "advisory": advisory})
