import json
import random

def generate_towers(region, num_towers, lat_range, lng_range):
    operators = ["BSNL", "Airtel", "Jio", "Vi"]
    towers = []
    
    for i in range(num_towers):
        lat = random.uniform(lat_range[0], lat_range[1])
        lng = random.uniform(lng_range[0], lng_range[1])
        op = random.choice(operators)
        cell_id = random.randint(100000, 999999)
        
        towers.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lng, lat]
            },
            "properties": {
                "id": f"TWR_{region.upper()}_{i}",
                "operator": op,
                "cell_id": cell_id,
                "layer_type": "tower",
                "status": "operational" # Default, updated by cop_builder
            }
        })
        
    return {
        "type": "FeatureCollection",
        "features": towers
    }

assam_towers = generate_towers("assam", 150, (26.0, 27.5), (91.0, 95.0))
kerala_towers = generate_towers("kerala", 150, (8.5, 11.5), (76.0, 77.0))

with open("../backend/fixtures/cell_towers_assam.json", "w") as f:
    json.dump(assam_towers, f, indent=2)
    
with open("../backend/fixtures/cell_towers_kerala.json", "w") as f:
    json.dump(kerala_towers, f, indent=2)

print("Generated tower fixtures successfully.")
