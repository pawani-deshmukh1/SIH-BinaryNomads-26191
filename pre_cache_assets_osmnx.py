import osmnx as ox
import hashlib
import json
from pathlib import Path
from shapely.geometry import box
import warnings
import pandas as pd

warnings.filterwarnings("ignore")

CACHE_DIR = Path('backend/fixtures/osm_cache')
CACHE_DIR.mkdir(parents=True, exist_ok=True)

bboxes = {
    "GHY_BHARALU_CORE": (91.71, 26.13, 91.78, 26.20),
    "GHY_DEEPOR_BEEL": (91.62, 26.10, 91.68, 26.15),
    "GHY_SILSAKO_BEEL": (91.78, 26.15, 91.82, 26.20)
}

ox.settings.use_cache = True
ox.settings.log_console = True

def format_geom(geom):
    if geom.geom_type == 'Point':
        return {"type": "Point", "coordinates": [geom.x, geom.y]}
    elif geom.geom_type == 'LineString':
        return {"type": "LineString", "coordinates": list(geom.coords)}
    elif geom.geom_type == 'Polygon':
        return {"type": "Polygon", "coordinates": [list(geom.exterior.coords)]}
    elif geom.geom_type == 'MultiPolygon':
        return {"type": "Polygon", "coordinates": [list(geom.geoms[0].exterior.coords)]}
    return None

for name, bbox in bboxes.items():
    min_lng, min_lat, max_lng, max_lat = bbox
    key = f"{bbox[0]:.4f}_{bbox[1]:.4f}_{bbox[2]:.4f}_{bbox[3]:.4f}"
    h = hashlib.md5(key.encode()).hexdigest()[:12]
    path = CACHE_DIR / f"critical_assets_{h}.geojson"
    
    print(f"Fetching {name} via OSMnx...")
    
    tags = {
        'amenity': ['hospital', 'clinic', 'school'],
        'highway': ['primary', 'secondary', 'trunk', 'residential', 'unclassified']
    }
    
    polygon = box(min_lng, min_lat, max_lng, max_lat)
    
    try:
        gdf = ox.features_from_polygon(polygon, tags=tags)
    except Exception as e:
        print(f"Failed to fetch {name}: {e}")
        continue
        
    features = []
    for idx, row in gdf.iterrows():
        geom = format_geom(row.geometry)
        if not geom:
            continue
            
        feature_type = 'unknown'
        if 'highway' in row and pd.notna(row['highway']):
            feature_type = 'road'
        elif 'amenity' in row and pd.notna(row['amenity']):
            feature_type = str(row['amenity'])
            
        name_val = str(row['name']) if 'name' in row and pd.notna(row['name']) else 'Unknown'
        
        osm_id = str(idx)
        
        features.append({
            "type": "Feature",
            "properties": {
                "osm_id": osm_id,
                "name": name_val,
                "type": feature_type,
                "layer_type": "critical_asset"
            },
            "geometry": geom
        })
        
    res = {"type": "FeatureCollection", "features": features}
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(res, f)
        
    print(f"Wrote {len(features)} assets to {path}")
