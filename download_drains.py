import osmnx as ox
import geopandas as gpd

print("Downloading OSM drainage network for Guwahati...")
try:
    tags = {'waterway': ['drain', 'river', 'canal', 'ditch', 'stream']}
    gdf = ox.features_from_place('Guwahati, Assam, India', tags=tags)
    
    columns_to_keep = ['geometry', 'name', 'waterway']
    available_cols = [c for c in columns_to_keep if c in gdf.columns]
    gdf = gdf[available_cols]
    
    # We only want LineStrings
    gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])]
    
    print(f"Downloaded {len(gdf)} drainage segments. Saving to GeoJSON...")
    gdf.to_file('dashboard/data/guwahati/guwahati_drains.geojson', driver='GeoJSON')
    print("Done! Saved to guwahati_drains.geojson")
except Exception as e:
    print(f"Error: {e}")
