import rasterio
import numpy as np
import geopandas as gpd
from rasterio.features import shapes
from shapely.geometry import shape
import warnings
warnings.filterwarnings('ignore')

print("Extracting steep slopes from DEM...")
try:
    with rasterio.open('dashboard/data/guwahati/download.slope.tif') as src:
        image = src.read(1)
        
        print(f"Max value: {np.max(image)}, Min value: {np.min(image)}")
        
        # Depending on what the TIFF represents (could be binary 1/0 or actual slope degrees)
        # We will extract values > 0 or > 15
        threshold = 0 if np.max(image) <= 1 else 15
        
        mask = (image > threshold) & (~np.isnan(image))
        
        results = (
            {'properties': {'steep': 1}, 'geometry': s}
            for i, (s, v) in enumerate(shapes(image, mask=mask, transform=src.transform))
            if v == 1
        )
        
        gdf = gpd.GeoDataFrame.from_features(list(results), crs=src.crs)
        
        if not gdf.empty:
            gdf = gdf.dissolve()
            gdf.to_file('dashboard/data/guwahati/earth_cutting_slopes.geojson', driver='GeoJSON')
            print("Successfully created earth_cutting_slopes.geojson")
        else:
            print("No steep areas found.")
except Exception as e:
    print(f"Error: {e}")
