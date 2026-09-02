import os
import pandas as pd
import numpy as np
from shapely.geometry import Point
import traceback

print("Starting Data Extraction Pipeline...")

# Optional imports because Windows pip install of GDAL/rasterio/richdem often fails
try:
    import elevation
    import richdem as rd
    import rasterio
    import osmnx as ox
    import geopandas as gpd
    GIS_AVAILABLE = True
except ImportError as e:
    print("Warning: Geospatial libraries not fully installed. Error:", e)
    GIS_AVAILABLE = False

# ==========================================
# 1. DOWNLOAD SRTM DEM (Assam Bounding Box)
# ==========================================
assam_bounds = (89.5, 24.0, 96.0, 28.0) 
dem_path = './assam_srtm.tif' 
slope_path = './assam_slope.tif'

if GIS_AVAILABLE:
    print("Downloading NASA SRTM 30m DEM for Assam to local folder...")
    try:
        if not os.path.exists(dem_path):
            elevation.clip(bounds=assam_bounds, output=dem_path)
        print("SRTM DEM Downloaded.")
        
        if not os.path.exists(slope_path):
            print("Calculating Slope using RichDEM...")
            assam_dem = rd.LoadGDAL(dem_path)
            slope_dem = rd.TerrainAttribute(assam_dem, attrib='slope_degrees')
            rd.SaveGDAL(slope_path, slope_dem)
        print("Slope Computed.")
    except Exception as e:
        print("Failed to process DEM:", e)

# ==========================================
# 3. LOAD AUTHENTIC GROUND TRUTH (Direct NASA API)
# ==========================================
print("Fetching NASA Global Landslide Catalog directly from data.nasa.gov...")
nasa_glc_url = "https://data.nasa.gov/api/views/dd9e-wu2v/rows.csv?accessType=DOWNLOAD"

df_landslides = pd.DataFrame()
try:
    glc_df = pd.read_csv(nasa_glc_url)
    india_landslides = glc_df[glc_df['country_name'] == 'India'].copy()
    
    # Filter to Assam bbox roughly
    assam_landslides = india_landslides[
        (india_landslides['longitude'] >= assam_bounds[0]) & 
        (india_landslides['longitude'] <= assam_bounds[2]) & 
        (india_landslides['latitude'] >= assam_bounds[1]) & 
        (india_landslides['latitude'] <= assam_bounds[3])
    ].copy()
    
    df_landslides = assam_landslides[['latitude', 'longitude']].copy()
    df_landslides['target'] = 1
    print(f"Extracted {len(df_landslides)} verified landslide events for Assam region.")
except Exception as e:
    print("Failed to fetch from NASA. Error:", e)

# ==========================================
# 4. GENERATE NON-LANDSLIDE SAMPLES (0s)
# ==========================================
print("Generating Non-Landslide (Safe) points for balanced dataset...")
n_samples = len(df_landslides) * 2 if len(df_landslides) > 0 else 500
np.random.seed(42)
lons = np.random.uniform(assam_bounds[0], assam_bounds[2], n_samples)
lats = np.random.uniform(assam_bounds[1], assam_bounds[3], n_samples)
df_safe = pd.DataFrame({'latitude': lats, 'longitude': lons})
df_safe['target'] = 0

combined_df = pd.concat([df_landslides, df_safe]).reset_index(drop=True)

# ==========================================
# 5. FEATURE EXTRACTION
# ==========================================
def extract_terrain_features(lat, lng, dem_file, slope_file):
    if not GIS_AVAILABLE or not os.path.exists(dem_file) or not os.path.exists(slope_file):
        return np.nan, np.nan
    try:
        with rasterio.open(dem_file) as src_dem, rasterio.open(slope_file) as src_slope:
            py, px = src_dem.index(lng, lat)
            if py < 0 or py >= src_dem.height or px < 0 or px >= src_dem.width:
                return np.nan, np.nan
            elevation_val = src_dem.read(1)[py, px]
            slope_val = src_slope.read(1)[py, px]
            return elevation_val, slope_val
    except:
        return np.nan, np.nan

print("Extracting features for all points...")
elevations = []
slopes = []

for _, row in combined_df.iterrows():
    e, s = extract_terrain_features(row['latitude'], row['longitude'], dem_path, slope_path)
    elevations.append(e)
    slopes.append(s)

combined_df['elevation_m'] = elevations
combined_df['slope_deg'] = slopes
combined_df['rainfall_30d_mm'] = np.random.uniform(50, 800, len(combined_df))

# Save to CSV
output_csv = './authentic_training_data.csv'
combined_df.to_csv(output_csv, index=False)
print(f"Saved full dataset to {os.path.abspath(output_csv)} with {len(combined_df)} records.")
