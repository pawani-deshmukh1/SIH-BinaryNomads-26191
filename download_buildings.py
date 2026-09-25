import osmnx as ox
import geopandas as gpd

print("Downloading OSM building footprints for Guwahati...")
try:
    # Use a specific bounding box or place name
    tags = {'building': True}
    gdf = ox.features_from_place('Guwahati, Assam, India', tags=tags)
    
    # Process attributes (OSM can have complex lists/dicts in columns)
    # We only need the geometry and maybe height if present
    columns_to_keep = ['geometry']
    if 'height' in gdf.columns:
        columns_to_keep.append('height')
    if 'building:levels' in gdf.columns:
        columns_to_keep.append('building:levels')
        
    gdf = gdf[columns_to_keep]
    
    # Calculate render height
    # If height exists, use it. If levels exist, multiply by 3m. Else default to random between 5 and 15m
    import numpy as np
    
    def get_height(row):
        try:
            if 'height' in row and not pd.isna(row['height']):
                h = str(row['height']).replace('m', '').strip()
                return float(h)
        except: pass
        try:
            if 'building:levels' in row and not pd.isna(row['building:levels']):
                return float(row['building:levels']) * 3.0
        except: pass
        return np.random.uniform(5.0, 15.0)
        
    import pandas as pd
    gdf['render_height'] = gdf.apply(get_height, axis=1)
    gdf['render_min_height'] = 0.0
    
    # Convert polygons/multipolygons only
    gdf = gdf[gdf.geometry.type.isin(['Polygon', 'MultiPolygon'])]
    
    print(f"Downloaded {len(gdf)} buildings. Saving to GeoJSON...")
    gdf.to_file('dashboard/data/guwahati/guwahati_buildings.geojson', driver='GeoJSON')
    print("Done! Saved to guwahati_buildings.geojson")
except Exception as e:
    print(f"Error: {e}")
