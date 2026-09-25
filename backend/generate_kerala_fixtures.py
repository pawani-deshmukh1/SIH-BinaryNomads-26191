import json
import random

MIN_LAT, MAX_LAT = 8.2, 12.9
MIN_LON, MAX_LON = 74.8, 77.4

# Target Coastal Kerala (Ernakulam/Alappuzha stretch)
COASTAL_LAT_MIN, COASTAL_LAT_MAX = 9.3, 10.2
COASTAL_LON_MIN, COASTAL_LON_MAX = 76.1, 76.5

def generate_habitations(n=120):
    features = []
    # Generate 40% along the coast, 60% inland
    for i in range(1, n + 1):
        if i <= n * 0.4:
            lat = random.uniform(COASTAL_LAT_MIN, COASTAL_LAT_MAX)
            lon = random.uniform(COASTAL_LON_MIN, COASTAL_LON_MAX)
            h_type = "char" # Riverbank/Coastal
            elev = random.uniform(1, 10)
        else:
            lat = random.uniform(MIN_LAT, MAX_LAT)
            lon = random.uniform(MIN_LON, MAX_LON)
            h_type = random.choice(["urban", "tribal", "tea_garden"])
            elev = random.uniform(20, 500)
            
        pop = random.randint(300, 5000)
        
        feature = {
            "type": "Feature",
            "properties": {
                "id": f"KER_{h_type.upper()}_{i:03d}",
                "name": f"Village {i} (Kerala Demo)",
                "population": pop,
                "households": pop // 4,
                "elevation_m": round(elev, 1),
                "slope_deg": round(random.uniform(2.0, 15.0), 1),
                "dist_to_river_m": random.randint(50, 5000),
                "sc_st_percent": random.randint(5, 40),
                "landless_households_pct": random.randint(10, 50),
                "literacy_rate_pct": random.randint(85, 99),
                "women_percent": random.randint(48, 52),
                "children_percent": random.randint(20, 30),
                "elderly_percent": random.randint(10, 20),
                "nearest_hospital_km": random.randint(2, 30)
            },
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat]
            }
        }
        features.append(feature)
        
    return features

def generate_safe_zones(n=15):
    features = []
    for i in range(1, n + 1):
        lat = random.uniform(MIN_LAT, MAX_LAT)
        lon = random.uniform(MIN_LON, MAX_LON)
        area = random.randint(5000, 20000)
        cap = int(area * 0.5)
        
        feature = {
            "type": "Feature",
            "properties": {
                "id": f"KER_SZ_{i:03d}",
                "name": f"Relocation Camp {i} (Kerala)",
                "area_sqm": area,
                "capacity_persons": cap,
                "elevation_m": round(random.uniform(50, 200), 1),
                "suitability_score": round(random.uniform(0.7, 0.99), 2)
            },
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat]
            }
        }
        features.append(feature)
        
    return {
        "type": "FeatureCollection",
        "features": features
    }

if __name__ == '__main__':
    habs = generate_habitations(120)
    with open('fixtures/habitations_kerala.json', 'w') as f:
        json.dump(habs, f, indent=2)
        
    sz = generate_safe_zones(15)
    with open('fixtures/safe_zones_kerala.json', 'w') as f:
        json.dump(sz, f, indent=2)
        
    print("Generated realistic Kerala data successfully.")
