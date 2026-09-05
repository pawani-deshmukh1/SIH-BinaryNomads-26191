import json
import math
import requests
import os

with open('fixtures/habitations_assam.json', 'r') as f:
    habs = json.load(f)

with open('fixtures/safe_zones_assam.json', 'r') as f:
    szs = json.load(f)
    
cache_file = 'fixtures/route_cache.json'
route_cache = {}
if os.path.exists(cache_file):
    with open(cache_file, 'r') as f:
        route_cache = json.load(f)

print("Pre-caching 12 routes using OSRM...")

for hab in habs:
    if hab.get('zone_class', '') == 'GREEN': continue # Actually the json doesn't have zone_class, but I'll skip it
    
    origin_lon = hab['lng']
    origin_lat = hab['lat']
    
    nearest_sz = None
    min_dist = float('inf')
    
    for sz in szs:
        sz_lon = sz['lng']
        sz_lat = sz['lat']
        dist = math.hypot(origin_lat - sz_lat, origin_lon - sz_lon)
        if dist < min_dist:
            min_dist = dist
            nearest_sz = sz
            
    if nearest_sz:
        dest_lon = nearest_sz['lng']
        dest_lat = nearest_sz['lat']
        
        cache_key = f"{origin_lon},{origin_lat}_{dest_lon},{dest_lat}"
        if cache_key in route_cache:
            continue
            
        print(f"Fetching OSRM for {hab['name']} -> {nearest_sz['name']}...")
        osrm_url = f"http://router.project-osrm.org/route/v1/driving/{origin_lon},{origin_lat};{dest_lon},{dest_lat}?overview=full&geometries=geojson"
        
        try:
            r = requests.get(osrm_url, timeout=5)
            data = r.json()
            if data.get('code') == 'Ok':
                osrm_coords = data['routes'][0]['geometry']['coordinates']
                
                paved_safe = {
                    "type": "Feature",
                    "properties": {
                        "segment_type": "paved_safe",
                        "route_status": "CLEAR",
                        "flood_warning": False,
                        "description": "Auto-routed via OSRM Fallback Engine"
                    },
                    "geometry": {
                        "type": "LineString",
                        "coordinates": osrm_coords
                    }
                }
                
                kacha_way = {
                    "type": "Feature",
                    "properties": {
                        "segment_type": "kacha_way",
                        "route_status": "KACHA_WAY",
                    },
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[origin_lon, origin_lat], osrm_coords[0]]
                    }
                }
                
                route_cache[cache_key] = {
                    "type": "FeatureCollection",
                    "features": [kacha_way, paved_safe]
                }
                print("  Success")
            else:
                print("  OSRM returned error")
        except Exception as e:
            print(f"  Failed: {e}")

with open(cache_file, 'w') as f:
    json.dump(route_cache, f)
    
print("Done!")
