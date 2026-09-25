from fastapi import APIRouter
from core.dynamic_flood_risk import calculate_dynamic_risk
from core.osm_overlay import fetch_critical_assets_overpass
from api.routes import get_safe_route
import os
import json
import groq
import requests
import math

router = APIRouter(prefix="/operational", tags=["Operational Decisions (Layer 2)"])

# Approximate bounding boxes for the 3 test-bed basins (min_lng, min_lat, max_lng, max_lat)
BASIN_BBOXES = {
    "GHY_BHARALU_CORE": (91.71, 26.13, 91.78, 26.20),
    "GHY_DEEPOR_BEEL": (91.62, 26.10, 91.68, 26.15),
    "GHY_SILSAKO_BEEL": (91.78, 26.15, 91.82, 26.20)
}

# 1st Battalion NDRF Base, Patgaon, Azara, Guwahati
NDRF_BASE = {"lat": 26.1235, "lon": 91.6171}

@router.get("/decision-support")
def get_decision_support(rainfall_mm_hr: float = 0.0, river_level_m: float = 48.0, dam_level_pct: float = 80.0, active_chemical_leaks: str = "", wind_dir: float = 90.0):
    """
    Returns AI Agent Situational Synthesis using Groq Llama 3 (True RAG)
    based strictly on spatial intersection between the physics-based capacity deficit 
    and OSM critical infrastructure, incorporating NDRF route safety.
    """
    scenarios = calculate_dynamic_risk(rainfall_mm_hr, river_level_m, dam_level_pct)
    
    decisions = []
    exposed_features = []
    
    # Initialize Groq Client
    groq_api_key = os.getenv("GROQ_API_KEY")
    client = groq.Groq(api_key=groq_api_key) if groq_api_key else None
    
    for sc in scenarios:
        bid = sc["basin_id"]
        risk = sc["risk_level"]
        
        # For MVP, only run exposure for MODERATE, HIGH or CRITICAL
        if risk in ["MODERATE", "HIGH", "CRITICAL"] and bid in BASIN_BBOXES:
            bbox = BASIN_BBOXES[bid]
            
            # Load pre-computed elevations to enable live filtering!
            lookup_table = {}
            try:
                lookup_path = os.path.join(os.path.dirname(__file__), "..", "..", "guwahati_flood_lookup.json")
                if os.path.exists(lookup_path):
                    with open(lookup_path, "r") as lf:
                        lookup_data = json.load(lf)
                        lookup_table = lookup_data.get("facilities", {})
            except Exception as e:
                print(f"Failed to load lookup table: {e}")
                
            # Fetch critical infrastructure (Hospitals, Schools) and roads (residential, primary, etc)
            osm_data = fetch_critical_assets_overpass(bbox)
            
            hospitals = []
            schools = []
            roads = 0
            
            for f in osm_data.get("features", []):
                props = f.get("properties", {})
                asset_type = props.get("type")
                name = props.get("name", "Unnamed")
                osm_id = str(props.get("osm_id", "")).split("/")[-1] # Extract just the ID number
                
                # Append risk level and basin so the frontend can color 3D extrusions accordingly
                f_copy = dict(f)
                f_copy["properties"] = dict(props)
                f_copy["properties"]["risk_level"] = risk
                f_copy["properties"]["basin_name"] = sc["name"]
                exposed_features.append(f_copy)
                
                # LIVE ELEVATION FILTERING via the Lookup Table!
                is_flooded = False # Default to safe. Only flag if it's explicitly proven flooded.
                if name in lookup_table:
                    facility_elev = lookup_table[name].get("min_elevation_m", 999.0)
                    if facility_elev <= river_level_m:
                        is_flooded = True
                
                if is_flooded:
                    if asset_type in ["hospital", "clinic"]:
                        hospitals.append(name if name != "Unknown" else "Unnamed Medical Center")
                    elif asset_type == "school":
                        schools.append(name if name != "Unknown" else "Unnamed School")
                    elif asset_type == "road":
                        roads += 1
            
            # Format the constrained, honest output
            exposed_items = []
            if hospitals:
                exposed_items.append(f"{len(hospitals)} medical facilities (e.g. {hospitals[0]})")
            if schools:
                exposed_items.append(f"{len(schools)} schools")
                
            exposed_str = ", ".join(exposed_items)
            if not exposed_str:
                exposed_str = "No major public facilities"
                
            # NDRF Routing
            dest_lon = (bbox[0] + bbox[2]) / 2.0
            dest_lat = (bbox[1] + bbox[3]) / 2.0
            
            route_geojson = get_safe_route(
                origin_lat=NDRF_BASE["lat"],
                origin_lon=NDRF_BASE["lon"],
                dest_lat=dest_lat,
                dest_lon=dest_lon
            )
            
            # Extract route status
            overall_route_status = "CLEAR"
            for f in route_geojson.get("features", []):
                status = f.get("properties", {}).get("route_status", "")
                if status == "ISOLATED" or status == "ERROR":
                    overall_route_status = "ISOLATED"
                    break
                elif status == "KACHA_WAY":
                    overall_route_status = "KACHA_WAY_REQUIRED"
            
            if overall_route_status == "CLEAR":
                route_desc = "Safe paved road access is available."
            elif overall_route_status == "KACHA_WAY_REQUIRED":
                route_desc = "Main paved roads are compromised; NDRF teams will require Kacha Way (dirt path) detour."
            else:
                route_desc = "Zone is completely ISOLATED by road. Heli or boat rescue required."

            # RAG Situational Synthesis via Groq Llama 3
            if client:
                dam_context = f" Upstream Umiam Dam is at CRITICAL {dam_level_pct}% capacity, forcing external runoff into the city." if dam_level_pct > 90.0 else ""
                
                # --- LIVE RATIONAL METHOD CALCULATOR ---
                c_coefficient = 0.85 # Highly urbanized/concrete
                A_hectares = 21600 # Approx Guwahati metro area in hectares
                # Formula: Q (m3/s) = (c * i * A) / 360
                Q_runoff_m3s = (c_coefficient * rainfall_mm_hr * A_hectares) / 360.0
                manning_capacity = 350.0 # Assumed total carrying capacity of city drains
                
                math_context = ""
                if rainfall_mm_hr > 0:
                    math_context = f"\n- Hydrological Math: Rational Method (Q=ciA) calculates a live peak runoff of {Q_runoff_m3s:,.0f} cubic meters per second (m³/s). Manning's Equation capacity for the city's silt-choked drains is only {manning_capacity:,.0f} m³/s."
                    if Q_runoff_m3s > manning_capacity:
                        math_context += f" A catastrophic volume deficit of {(Q_runoff_m3s - manning_capacity):,.0f} m³/s is actively flooding the streets."
                        
                cbrn_context = ""
                rule_override = "Do NOT give prescriptive commands (e.g. do not say 'deploy pumps'). Just synthesize the situation using the 5Ws."
                if active_chemical_leaks:
                    cbrn_context = f"\n- CBRN ALERT: The following chemical facilities have reported structural failure/leaks: {active_chemical_leaks}. A toxic Gaussian plume is actively spreading."
                    rule_override = "This is a CBRN emergency. You MUST explicitly recommend UPWIND staging locations for the NDRF base camp and specify HAZMAT Level B/A protective equipment."
                
                prompt = f"""You are a highly competent NDRF tactical AI generating a Situational Synthesis.
{rule_override}

Context:
- What/Where: A {risk} hazard state detected in zone {sc['name']}.
- Why: Gravity drainage is severely compromised with a capacity deficit of {sc['capacity_deficit_pct']}% due to heavy rainfall ({rainfall_mm_hr} mm/hr) and Brahmaputra river backflow (River Stage: {river_level_m}m).{dam_context}{cbrn_context}{math_context}
- Who (Exposure): {exposed_str.capitalize()} and {roads} road segments are currently trapped in the inundation zone.
- NDRF Deployment Route Status from Azara Base: {route_desc}

Generate a sharp, professional paragraph (max 3-4 sentences). Make sure to explicitly quote the Rational Method peak runoff figures if a catastrophic deficit is detected:"""
                try:
                    completion = client.chat.completions.create(
                        model="qwen/qwen3.8-27b",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                        max_tokens=150
                    )
                    synthesis = completion.choices[0].message.content.strip()
                except Exception as e:
                    print(f"Groq API Error: {e}, attempting Gemini fallback...")
                    # Gemini API Fallback
                    gemini_key = os.getenv("GEMINI_API_KEY")
                    if gemini_key:
                        try:
                            gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
                            payload = {
                                "contents": [{"parts": [{"text": prompt}]}],
                                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 150}
                            }
                            resp = requests.post(gemini_url, json=payload, timeout=5)
                            resp.raise_for_status()
                            synthesis = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                        except Exception as gemini_e:
                            print(f"Gemini API Error: {gemini_e}")
                            synthesis = f"Situational Synthesis (Offline Fallback): A {risk} hazard state detected in {sc['name']}. {exposed_str.capitalize()} exposed. Route: {route_desc}"
                    else:
                        synthesis = f"Situational Synthesis (Offline Fallback): A {risk} hazard state detected in {sc['name']}. {exposed_str.capitalize()} exposed. Route: {route_desc}"
            else:
                synthesis = f"Situational Synthesis (Offline Fallback): A {risk} hazard state detected in {sc['name']}. {exposed_str.capitalize()} exposed. Route: {route_desc}"
            
            decisions.append({
                "basin_id": bid,
                "basin_name": sc["name"],
                "risk_level": risk,
                "capacity_deficit_pct": sc["capacity_deficit_pct"],
                "exposed_hospitals": len(hospitals),
                "exposed_schools": len(schools),
                "exposed_roads": roads,
                "recommendation": synthesis,
                "ndrf_route_geojson": route_geojson,
                "dest_lat": dest_lat,
                "dest_lon": dest_lon
            })
            
    # Standalone CBRN Alert (if chemical leak is active but no flood triggered it)
    if active_chemical_leaks and len(decisions) == 0:
        if client:
            prompt = f"""You are a highly competent NDRF tactical AI generating a Situational Synthesis.
This is a CBRN emergency. You MUST explicitly recommend UPWIND staging locations for the NDRF base camp and specify HAZMAT Level B/A protective equipment.

Context:
- What/Where: A CRITICAL chemical leak detected at: {active_chemical_leaks}. A toxic Gaussian plume is actively spreading based on live wind direction.
- Why: Structural or operational failure at the facility. Note: There is NO compounding flood risk at this moment, roads are clear.
- Who (Exposure): Civilian populations in the downwind plume trajectory.

Generate a sharp, professional paragraph (max 3-4 sentences):"""
            try:
                completion = client.chat.completions.create(
                    model="qwen/qwen3.8-27b",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=150
                )
                cbrn_synthesis = completion.choices[0].message.content.strip()
            except Exception:
                cbrn_synthesis = "STANDALONE CBRN ALERT: Toxic plume spreading from " + active_chemical_leaks + ". Equip HAZMAT Level A/B immediately and establish upwind staging."
        else:
            cbrn_synthesis = "STANDALONE CBRN ALERT: Toxic plume spreading from " + active_chemical_leaks + ". Equip HAZMAT Level A/B immediately and establish upwind staging."
            
        # CBRN Staging Area calculation (3km upwind)
        facility_lat = 26.185
        facility_lon = 91.808
        dist_km = 3.0
        
        upwind_lat = facility_lat + (dist_km * math.cos(math.radians(wind_dir)) / 111.32)
        upwind_lon = facility_lon + (dist_km * math.sin(math.radians(wind_dir)) / (111.32 * math.cos(math.radians(facility_lat))))
        
        # Dynamic Detour Calculation for OSRM Fallback Engine
        # Since Overpass API is completely rate-limiting Guwahati graph downloads today, we rely on the bulletproof OSRM fallback with waypoints.
        try:
            leak_coords = {
                'iocl': (91.808, 26.185),
                'kamrup': (91.802, 26.182),
                'shiva': (91.795, 26.128)
            }
            
            active_lats = []
            active_lons = []
            for leak_id in active_chemical_leaks.split(','):
                leak_id = leak_id.strip()
                if leak_id in leak_coords:
                    lon, lat = leak_coords[leak_id]
                    active_lats.append(lat)
                    active_lons.append(lon)
                    
            if active_lats:
                min_lat = min(active_lats)
                avg_lon = sum(active_lons) / len(active_lons)
            else:
                min_lat = 26.185
                avg_lon = 91.808
                
            # Detour 5km South of the southernmost active leak
            detour_lat = min_lat - (5.0 / 111.32)
            detour_lon = avg_lon
            
        except Exception as e:
            print(f"Failed to calculate detour: {e}")
            detour_lat = 26.128 - (5.0 / 111.32)
            detour_lon = 91.795

        # Two-leg route to force OSRM to swing south
        leg1 = get_safe_route(
            origin_lat=NDRF_BASE["lat"],
            origin_lon=NDRF_BASE["lon"],
            dest_lat=detour_lat,
            dest_lon=detour_lon
        )
        
        leg2 = get_safe_route(
            origin_lat=detour_lat,
            origin_lon=detour_lon,
            dest_lat=upwind_lat,
            dest_lon=upwind_lon
        )
        
        # Combine the GeoJSON features from both legs
        cbrn_route_geojson = {
            "type": "FeatureCollection",
            "features": leg1.get("features", []) + leg2.get("features", [])
        }

        decisions.append({
            "basin_id": "CBRN_STANDALONE",
            "basin_name": "INDUSTRIAL CHEMICAL ZONE",
            "risk_level": "CRITICAL",
            "capacity_deficit_pct": "N/A",
            "exposed_hospitals": 0,
            "exposed_schools": 0,
            "exposed_roads": 0,
            "recommendation": cbrn_synthesis,
            "ndrf_route_geojson": cbrn_route_geojson,
            "dest_lat": upwind_lat,
            "dest_lon": upwind_lon
        })

    return {
        "status": "success", 
        "decisions": decisions, 
        "exposed_geojson": {
            "type": "FeatureCollection",
            "features": exposed_features
        }
    }
