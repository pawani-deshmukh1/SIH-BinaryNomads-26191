import json
from shapely.geometry import shape

bboxes = {
    "GHY_BHARALU_CORE": (91.71, 26.13, 91.78, 26.20),
    "GHY_DEEPOR_BEEL": (91.62, 26.10, 91.68, 26.15),
    "GHY_SILSAKO_BEEL": (91.78, 26.15, 91.82, 26.20)
}

path = "dashboard/data/guwahati/guwahati_buildings.geojson"
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)

count = 0
for feat in data.get('features', []):
    try:
        geom = shape(feat['geometry'])
        centroid = geom.centroid
        x, y = centroid.x, centroid.y
        assigned_basin = "NONE"
        for basin, bbox in bboxes.items():
            if bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]:
                assigned_basin = basin
                count += 1
                break
        feat['properties']['basin_id'] = assigned_basin
    except Exception as e:
        feat['properties']['basin_id'] = "NONE"

with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f)
    
print(f"Tagged {count} buildings with basin IDs.")
