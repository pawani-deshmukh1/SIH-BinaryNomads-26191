import json
import random

# Rough bounding box for Nagaon/Lakhimpur region in Assam
# Approx bounds: 26.2 to 26.5 N, 92.5 to 92.8 E
MIN_LAT, MAX_LAT = 26.25, 26.45
MIN_LON, MAX_LON = 92.55, 92.75

def generate_habitations(n=15):
    features = []
    for i in range(1, n + 1):
        lat = random.uniform(MIN_LAT, MAX_LAT)
        lon = random.uniform(MIN_LON, MAX_LON)
        pop = random.randint(200, 2000)
        vul_score = round(random.uniform(0.3, 0.9), 2)
        
        feature = {
            "type": "Feature",
            "properties": {
                "id": i,
                "name": f"Habitation {i} (Assam Demo)",
                "population": pop,
                "vulnerability_score": vul_score
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

def generate_relocation_sites(n=6):
    features = []
    for i in range(1, n + 1):
        lat = random.uniform(MIN_LAT, MAX_LAT)
        lon = random.uniform(MIN_LON, MAX_LON)
        area = random.randint(2000, 10000)
        cap = int(area * 0.5) # approx 2 sqm per person
        elev = random.uniform(50, 150)
        
        # Make it a small polygon around the point
        d = 0.001
        poly = [
            [lon-d, lat-d],
            [lon+d, lat-d],
            [lon+d, lat+d],
            [lon-d, lat+d],
            [lon-d, lat-d]
        ]
        
        feature = {
            "type": "Feature",
            "properties": {
                "id": i,
                "name": f"Relocation Site {i} (Safe Zone)",
                "area_sqm": area,
                "capacity_persons": cap,
                "elevation_m": round(elev, 1),
                "suitability_score": round(random.uniform(0.6, 0.95), 2)
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [poly]
            }
        }
        features.append(feature)
        
    return {
        "type": "FeatureCollection",
        "features": features
    }

def generate_opencellid_csv(n=25):
    import csv
    with open('data/opencellid_assam_sample.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['radio', 'mcc', 'net', 'area', 'cell', 'unit', 'lon', 'lat', 'range', 'samples', 'changeable', 'created', 'updated', 'averageSignal'])
        for i in range(n):
            lat = random.uniform(MIN_LAT, MAX_LAT)
            lon = random.uniform(MIN_LON, MAX_LON)
            tech = random.choice(['LTE', 'UMTS', 'GSM'])
            writer.writerow([tech, 404, random.choice([45, 10, 20]), random.randint(100, 999), random.randint(1000, 9999), 0, lon, lat, 1000, 50, 1, 1500000000, 1600000000, 0])

if __name__ == '__main__':
    with open('data/habitations_sample.geojson', 'w') as f:
        json.dump(generate_habitations(), f, indent=2)
        
    with open('data/relocation_sites_sample.geojson', 'w') as f:
        json.dump(generate_relocation_sites(), f, indent=2)
        
    generate_opencellid_csv()
    
    # Touch empty pbf file so docker volume doesn't crash
    with open('data/region_nagaon_assam.osm.pbf', 'wb') as f:
        f.write(b'mock_osm_pbf_data')
    
    print("Demo data generated successfully.")
