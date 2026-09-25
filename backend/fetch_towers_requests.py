import requests
import json
import random
import sys

overpass_url = 'http://overpass-api.de/api/interpreter'
overpass_query = """
[out:json][timeout:50];
(
  node["man_made"="mast"]["communication"="mobile_phone"](25.5, 90.0, 27.5, 94.0);
  node["telecom"="antenna"](25.5, 90.0, 27.5, 94.0);
  node["man_made"="communications_tower"](25.5, 90.0, 27.5, 94.0);
);
out body;
"""

print("Fetching real towers from OpenStreetMap using requests...")
try:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json'
    }
    response = requests.post(overpass_url, data={'data': overpass_query}, headers=headers, timeout=60)
    response.raise_for_status()
    data = response.json()
    
    elements = data.get('elements', [])
    print(f"Found {len(elements)} total towers in OSM.")
    
    if len(elements) == 0:
        print("No towers found.")
        sys.exit(1)
        
    random.seed(42)
    random.shuffle(elements)
    
    # Grid-based downsampling (Assam bounds: roughly 25 to 28 Lat, 90 to 96 Lon)
    # 0.2 degrees is roughly 22km x 22km. Let's take up to 2 towers per 22km block.
    grid = {}
    for node in elements:
        lat = node.get('lat')
        lon = node.get('lon')
        if not lat or not lon: continue
        
        grid_key = (round(lat * 5) / 5, round(lon * 5) / 5)
        if grid_key not in grid:
            grid[grid_key] = []
        grid[grid_key].append(node)
        
    sampled_nodes = []
    for k, nodes in grid.items():
        sampled_nodes.extend(nodes[:2])
        
    print(f"Sampled down to {len(sampled_nodes)} evenly spread-out towers.")
    
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
