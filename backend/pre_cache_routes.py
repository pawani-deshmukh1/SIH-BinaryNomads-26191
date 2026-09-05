import json
import urllib.request
import time
import math

# Load habitations and safe zones
with open('fixtures/habitations_assam.json', 'r') as f:
    habs = json.load(f)

with open('fixtures/safe_zones_assam.json', 'r') as f:
    szs = json.load(f)

# The proactive engine adds zone_class dynamically, but let's just get the nearest safe zone for ALL habitations
for hab in habs:
    origin_lon = hab['lon']
    origin_lat = hab['lat']
    
    nearest_sz = None
    min_dist = float('inf')
    
    for sz in szs:
        dist = math.hypot(origin_lat - sz['lat'], origin_lon - sz['lon'])
        if dist < min_dist:
            min_dist = dist
            nearest_sz = sz
            
    if nearest_sz:
        dest_lon = nearest_sz['lon']
        dest_lat = nearest_sz['lat']
        
        url = f"http://127.0.0.1:8000/route/?origin_lat={origin_lat}&origin_lon={origin_lon}&dest_lat={dest_lat}&dest_lon={dest_lon}"
        print(f"Fetching route for {hab['name']} -> {nearest_sz['name']}...")
        try:
            req = urllib.request.Request(url, method="POST", data=b'{}')
            urllib.request.urlopen(req, timeout=10)
            print("  Success")
        except Exception as e:
            print(f"  Failed: {e}")
            
        time.sleep(1) # Prevent Overpass API from getting too angry
        
print("Done pre-caching routes!")
