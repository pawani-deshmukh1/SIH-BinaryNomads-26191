import urllib.request
import json
import random

overpass_url = 'http://overpass-api.de/api/interpreter'
# Fetch all towers in Assam, without limit, but only the coordinates to save memory
overpass_query = """
[out:json][timeout:25];
(
  node["man_made"="mast"]["communication"="mobile_phone"](25.5, 90.0, 27.5, 94.0);
  node["telecom"="antenna"](25.5, 90.0, 27.5, 94.0);
  node["man_made"="communications_tower"](25.5, 90.0, 27.5, 94.0);
);
out body;
"""

print("Fetching real towers from OpenStreetMap (no limit)...")
req = urllib.request.Request(overpass_url, data=overpass_query.encode('utf-8'))
req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')

try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode('utf-8'))
        
    elements = data.get('elements', [])
    print(f"Found {len(elements)} total towers in OSM.")
    
    # Shuffle and pick a reasonable sample (e.g. 150) so they don't cluster
    random.seed(42)
    random.shuffle(elements)
    
    # Actually, to prevent clustering, let's enforce a minimum distance between them
    # Simple grid-based downsampling
    grid = {}
    for node in elements:
        lat = node.get('lat')
        lon = node.get('lon')
        if not lat or not lon: continue
        
        # Round to 1 decimal place (roughly 11km x 11km grid)
        grid_key = (round(lat, 1), round(lon, 1))
        if grid_key not in grid:
            grid[grid_key] = []
        grid[grid_key].append(node)
        
    sampled_nodes = []
    # Take up to 2 towers from each grid cell
    for k, nodes in grid.items():
        sampled_nodes.extend(nodes[:2])
        
    print(f"Sampled down to {len(sampled_nodes)} spread-out towers.")
    
    features = []
    operators = ['Jio', 'Airtel', 'Vi', 'BSNL']
    
    for idx, node in enumerate(sampled_nodes):
        lat = node.get('lat')
        lon = node.get('lon')
        
        op = node.get('tags', {}).get('operator', random.choice(operators))
        
        feat = {
            'type': 'Feature',
            'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
            'properties': {
                'id': f'TWR_ASSAM_{idx}',
                'operator': op,
                'cell_id': random.randint(100000, 999999),
                'layer_type': 'tower',
                'status': 'operational'
            }
        }
        features.append(feat)
        
    fc = {'type': 'FeatureCollection', 'features': features}
    
    filepath = 'C:/Users/Ashutosh/Desktop/DISHA/backend/fixtures/cell_towers_assam.json'
    with open(filepath, 'w') as f:
        json.dump(fc, f, indent=2)
    
    print(f'Successfully saved {len(features)} spread out towers to {filepath}')
except Exception as e:
    print('Error fetching real towers:', e)
