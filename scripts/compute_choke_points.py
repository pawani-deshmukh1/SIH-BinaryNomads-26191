import geopandas as gpd
import os

def compute_choke_points():
    print("Loading GIS layers...")
    
    # Paths
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    drains_path = os.path.join(base_dir, "dashboard", "data", "guwahati", "guwahati_drains.geojson")
    slopes_path = os.path.join(base_dir, "dashboard", "data", "guwahati", "earth_cutting_slopes.geojson")
    output_path = os.path.join(base_dir, "dashboard", "data", "guwahati", "drainage_choke_points.geojson")
    
    if not os.path.exists(drains_path) or not os.path.exists(slopes_path):
        print(f"Error: Missing input files.\nDrains: {os.path.exists(drains_path)}\nSlopes: {os.path.exists(slopes_path)}")
        return
        
    try:
        import json
        from shapely.geometry import shape, mapping
        
        # Helper to read geojson without fiona
        def load_gdf(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            features = data.get('features', [])
            geoms = [shape(f['geometry']) for f in features if f.get('geometry')]
            props = [f.get('properties', {}) for f in features if f.get('geometry')]
            return gpd.GeoDataFrame(props, geometry=geoms, crs="EPSG:4326")
            
        # Load GeoJSONs
        drains_gdf = load_gdf(drains_path)
        slopes_gdf = load_gdf(slopes_path)
        
        print(f"Loaded {len(drains_gdf)} drain segments and {len(slopes_gdf)} slope polygons.")
            
        # Project to local metric CRS (EPSG:32646 for Guwahati, UTM Zone 46N)
        print("Projecting to UTM Zone 46N for metric spatial math...")
        drains_utm = drains_gdf.to_crs(epsg=32646)
        slopes_utm = slopes_gdf.to_crs(epsg=32646)
        
        # Buffer drains by 400 meters to catch adjacent sediment runoff from hills
        print("Buffering drainage network by 400 meters...")
        drains_buffered = drains_utm.copy()
        drains_buffered.geometry = drains_utm.geometry.buffer(400)
        
        # Perform spatial intersection
        print("Computing intersection between buffered drains and steep slopes...")
        intersections = gpd.overlay(drains_buffered, slopes_utm, how='intersection')
        
        print(f"Found {len(intersections)} raw intersection segments.")
        
        if intersections.empty:
            print("No intersections found. Output will be empty.")
        else:
            # Calculate overlapping area (sediment volume proxy)
            intersections['overlap_area_sqm'] = intersections.geometry.area
            
            # Filter out tiny overlaps (< 100 sq meters)
            choke_points = intersections[intersections['overlap_area_sqm'] > 100].copy()
            
            print(f"Filtered down to {len(choke_points)} significant choke points (>100 sqm).")
            
            # Rank/Categorize the risk
            def rank_risk(area):
                if area > 2000:
                    return 'CRITICAL'
                elif area > 500:
                    return 'HIGH'
                else:
                    return 'MODERATE'
                    
            choke_points['sediment_choke_risk'] = choke_points['overlap_area_sqm'].apply(rank_risk)
            
            # Convert back to EPSG:4326 for web mapping
            choke_points_wgs = choke_points.to_crs(epsg=4326)
            
            # Helper to write geojson without fiona
            out_features = []
            for _, row in choke_points_wgs.iterrows():
                geom_dict = mapping(row.geometry)
                prop_dict = {k: v for k, v in row.items() if k != 'geometry'}
                # convert numpy types to native for json serializing
                prop_dict = {k: float(v) if 'float' in str(type(v)) else str(v) for k, v in prop_dict.items()}
                out_features.append({
                    "type": "Feature",
                    "geometry": geom_dict,
                    "properties": prop_dict
                })
            
            out_json = {"type": "FeatureCollection", "features": out_features}
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(out_json, f)
                
            print(f"SUCCESS! Exported {len(choke_points_wgs)} Choke Point Vulnerabilities to: {output_path}")
            
    except Exception as e:
        print(f"Error during spatial computation: {e}")

if __name__ == "__main__":
    compute_choke_points()
