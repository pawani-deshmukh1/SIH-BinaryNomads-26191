import json
import random

try:
    with open('towers_raw.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    elements = data.get('elements', [])
    print(f"Found {len(elements)} total towers in OSM.")
    
    random.seed(42)
    random.shuffle(elements)
    
    grid = {}
    for node in elements:
        lat = node.get('lat')
        lon = node.get('lon')
        if not lat or not lon: continue
        
        # 0.2 degrees is roughly 22km x 22km. Take up to 2 towers per cell
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
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(fc, f, indent=2)
    
    print(f'Successfully saved {len(features)} spread out towers to {filepath}')
except Exception as e:
    print('Error processing real towers:', e)
