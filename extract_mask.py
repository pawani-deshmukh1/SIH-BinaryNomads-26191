import rasterio
import numpy as np
import geopandas as gpd
from rasterio.features import shapes
from shapely.geometry import shape
import warnings
warnings.filterwarnings('ignore')

print("Extracting danger mask (< 49.68m) from DEM...")
try:
    with rasterio.open('dashboard/data/guwahati/download.elevation.tif') as src:
        image = src.read(1)
        # Danger level is 49.68m
        mask = (image <= 49.68) & (image > 0)
        
        # Extract shapes
        results = (
            {'properties': {'danger': 1}, 'geometry': s}
            for i, (s, v) in enumerate(shapes(image, mask=mask, transform=src.transform))
            if v == 1
        )
        
        # Convert to GeoDataFrame
        gdf = gpd.GeoDataFrame.from_features(list(results), crs=src.crs)
        
        if not gdf.empty:
            gdf = gdf.dissolve() # Merge into one multipolygon
            gdf.to_file('dashboard/data/guwahati/danger_mask.geojson', driver='GeoJSON')
            print("Successfully created danger_mask.geojson")
        else:
            print("No areas found below 49.68m")
except Exception as e:
    print(f"Error: {e}")
