import json
import random

# Read the habitations (which are actual real-world coordinates spread across Assam)
with open('fixtures/demo_result.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

features_list = data.get('features', [])
print(f"Loaded {len(features_list)} actual habitation locations.")

features = []
operators = ['Jio', 'Airtel', 'Vi', 'BSNL']
random.seed(42)

# Select a subset of habitations to place towers near
sampled_habs = random.sample(features_list, min(150, len(features_list)))

for idx, hab in enumerate(sampled_habs):
    coords = hab.get('geometry', {}).get('coordinates', [])
    if not coords: continue
    
    if isinstance(coords[0], list):
        if isinstance(coords[0][0], list):
            lon, lat = coords[0][0][0], coords[0][0][1]
        else:
            lon, lat = coords[0][0], coords[0][1]
    else:
        lon, lat = coords[0], coords[1]
    
    # Add a slight random offset (approx 0.5km to 2km away from the village center)
    offset_lat = random.uniform(-0.02, 0.02)
    offset_lon = random.uniform(-0.02, 0.02)
    
    tower_lat = lat + offset_lat
    tower_lon = lon + offset_lon
    
    op = random.choice(operators)
    
    feat = {
        'type': 'Feature',
        'geometry': {'type': 'Point', 'coordinates': [tower_lon, tower_lat]},
        'properties': {
            'id': f'TWR_ASSAM_SYNTH_{idx}',
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

print(f"Successfully generated {len(features)} perfectly spread towers based on actual population distribution!")
