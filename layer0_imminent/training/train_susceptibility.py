import os
import joblib
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

def generate_flood_data(n_samples=5000):
    """
    Generate synthetic, scientifically plausible data for Flood Susceptibility.
    Features: elevation_m, distance_to_river_m, slope_deg, rainfall_30d_mm, land_use_class
    Target: flood_susceptible (1) or not (0)
    """
    np.random.seed(42)
    elevation = np.random.uniform(5, 500, n_samples)
    dist_river = np.random.uniform(10, 5000, n_samples)
    slope = np.random.uniform(0, 30, n_samples)
    rain = np.random.uniform(50, 800, n_samples)
    land_use = np.random.randint(1, 6, n_samples) # 1:water, 2:urban, 3:forest, 4:crop, 5:bare
    
    # Mathematical proxy for flood likelihood (low elevation, close to river, flat slope, high rain)
    risk_score = (
        (500 - elevation) / 500 * 0.35 + 
        (5000 - dist_river) / 5000 * 0.40 + 
        (30 - slope) / 30 * 0.15 + 
        (rain / 800) * 0.10
    )
    
    # Add noise
    risk_score += np.random.normal(0, 0.1, n_samples)
    
    # Top 30% are marked as susceptible
    threshold = np.percentile(risk_score, 70)
    target = (risk_score >= threshold).astype(int)
    
    return pd.DataFrame({
        'elevation_m': elevation,
        'distance_to_river_m': dist_river,
        'slope_deg': slope,
        'rainfall_30d_mm': rain,
        'land_use_class': land_use,
        'flood_susceptible': target
    })

def generate_landslide_data(n_samples=5000):
    """
    Generate synthetic data for Landslide Susceptibility.
    Features: slope_deg, elevation_m, distance_to_road_m, soil_type, rainfall_30d_mm
    Target: landslide_susceptible (1) or not (0)
    """
    np.random.seed(43)
    slope = np.random.uniform(5, 60, n_samples)
    elevation = np.random.uniform(100, 3000, n_samples)
    dist_road = np.random.uniform(10, 2000, n_samples)
    soil = np.random.randint(1, 4, n_samples) # 1:rock, 2:clay, 3:loose_soil
    rain = np.random.uniform(50, 800, n_samples)
    
    # Mathematical proxy for landslide likelihood (steep slope, loose soil, close to road cuts, high rain)
    risk_score = (
        (slope / 60) * 0.45 + 
        (soil == 3).astype(int) * 0.20 + 
        (2000 - dist_road) / 2000 * 0.15 + 
        (rain / 800) * 0.20
    )
    
    risk_score += np.random.normal(0, 0.1, n_samples)
    
    threshold = np.percentile(risk_score, 75)
    target = (risk_score >= threshold).astype(int)
    
    return pd.DataFrame({
        'slope_deg': slope,
        'elevation_m': elevation,
        'distance_to_road_m': dist_road,
        'soil_type': soil,
        'rainfall_30d_mm': rain,
        'landslide_susceptible': target
    })

def train_and_export(df, target_col, model_path):
    X = df.drop(columns=[target_col])
    y = df[target_col]
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Train Random Forest
    rf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
    rf.fit(X_train, y_train)
    
    # Print metrics
    preds = rf.predict(X_test)
    print(f"--- Metrics for {model_path} ---")
    print(classification_report(y_test, preds))
    
    # Save model
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    joblib.dump(rf, model_path)
    print(f"Saved to {model_path}\n")

if __name__ == "__main__":
    print("Generating Synthetic Tabular Dataset...")
    flood_df = generate_flood_data()
    landslide_df = generate_landslide_data()
    
    # Paths in backend
    base_dir = os.path.join(os.path.dirname(__file__), '..', 'backend', 'models')
    flood_model_path = os.path.join(base_dir, 'flood_rf.joblib')
    landslide_model_path = os.path.join(base_dir, 'landslide_rf.joblib')
    
    print("Training Flood Susceptibility Model...")
    train_and_export(flood_df, 'flood_susceptible', flood_model_path)
    
    print("Training Landslide Susceptibility Model...")
    train_and_export(landslide_df, 'landslide_susceptible', landslide_model_path)
    
    print("DONE! You can replace the synthetic generation functions with real Kaggle/ISRO CSV loaders later.")
