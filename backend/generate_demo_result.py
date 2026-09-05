import json
import math
import random
from datetime import datetime, timezone

# Load existing demo result to append to
with open('fixtures/demo_result.json', 'r') as f:
    demo_result = json.load(f)

# Keep existing evac sites, towers, evac_routes, and even the original red zones if we want (let's remove the old red/flood/landslide/building_damage ones and replace them state-wide)
existing_features = []
for f in demo_result.get('features', []):
    lt = f['properties'].get('layer_type')
    if lt in ['evac_site', 'tower', 'evac_route']:
        existing_features.append(f)

# Load habitations
with open('fixtures/habitations_assam.json', 'r') as f:
    habs = json.load(f)

features = existing_features
now = datetime.now(timezone.utc).isoformat()

def make_polygon(center_lng, center_lat, radius_deg, num_points=6, offset_angle=0):
    coords = []
    for i in range(num_points):
        angle = offset_angle + (i * 2 * math.pi / num_points)
        lng = center_lng + radius_deg * math.cos(angle)
        lat = center_lat + radius_deg * math.sin(angle)
        coords.append([round(lng, 4), round(lat, 4)])
    coords.append(coords[0]) # close loop
    return {"type": "Polygon", "coordinates": [coords]}

random.seed(42)

for hab in habs:
    if hab.get('zone_class', '') == 'GREEN': continue
    lng = hab['lng']
    lat = hab['lat']
    
    # We want to show vulnerable spots around almost all habitations to make the map look busy and impressive!
    is_landslide = hab.get('elevation_m', 0) > 100 # Higher elevation -> landslide risk
    
    # Red Zone (Overall risk bounding box/polygon)
    red_zone_radius = random.uniform(0.015, 0.035)
    red_zone = {
        "type": "Feature",
        "properties": {
            "layer_type": "red_zone",
            "primary_hazard": "landslide" if is_landslide else "flood",
            "risk_score": round(random.uniform(0.65, 0.98), 2),
            "color_tier": "red" if random.random() > 0.3 else "orange",
            "contributing_factors": {
                "damage": {"weight": 0.5, "value": random.uniform(0.2, 0.9)},
                "flood": {"weight": 0.25, "value": random.uniform(0.0, 0.9) if not is_landslide else 0.0},
                "landslide": {"weight": 0.25, "value": random.uniform(0.0, 0.9) if is_landslide else 0.0}
            },
            "last_updated": now
        },
        "geometry": make_polygon(lng, lat, red_zone_radius, num_points=random.randint(5,7))
    }
    features.append(red_zone)
    
    # Specific Hazard Zone inside the red zone
    hazard_radius = red_zone_radius * 0.7
    hazard_zone = {
        "type": "Feature",
        "properties": {
            "layer_type": "landslide_zone" if is_landslide else "flood_zone",
            "label": "landslide_hazard" if is_landslide else "flooded",
            "confidence": round(random.uniform(0.75, 0.98), 2),
            "last_updated": now
        },
        "geometry": make_polygon(lng, lat, hazard_radius, num_points=6 if not is_landslide else 4, offset_angle=0.5)
    }
    features.append(hazard_zone)
    
    # Add a few mock building damages inside
    for i in range(random.randint(2, 4)):
        bldg_lng = lng + random.uniform(-hazard_radius*0.5, hazard_radius*0.5)
        bldg_lat = lat + random.uniform(-hazard_radius*0.5, hazard_radius*0.5)
        bldg = {
            "type": "Feature",
            "properties": {
                "layer_type": "building_damage",
                "osm_id": f"way/mock_{random.randint(100000,999999)}",
                "damage_level": random.choice(["minor_damage", "destroyed"]),
                "confidence": round(random.uniform(0.6, 0.95), 2),
                "building_type": random.choice(["residential", "shop", "school"]),
                "last_updated": now
            },
            "geometry": make_polygon(bldg_lng, bldg_lat, 0.0008, num_points=4)
        }
        features.append(bldg)

demo_result = {
    "type": "FeatureCollection",
    "summary": {
        "red_zones_count": sum(1 for f in features if f["properties"]["layer_type"] == "red_zone"),
        "buildings_destroyed": sum(1 for f in features if f["properties"].get("damage_level") == "destroyed"),
        "buildings_minor_damage": sum(1 for f in features if f["properties"].get("damage_level") == "minor_damage"),
        "demo_mode": True,
        "last_updated": now
    },
    "features": features
}

with open('fixtures/demo_result.json', 'w') as f:
    json.dump(demo_result, f, indent=2)

print(f"Generated {len(features)} total features (merged with existing base features)")
