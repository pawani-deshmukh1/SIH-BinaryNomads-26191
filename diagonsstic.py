import pandas as pd
import numpy as np

# --- 1. CONFIGURATION ---
# Swap this to your Kaggle path if running in the cloud
FILE_PATH = r"C:\Users\Ashutosh\Downloads\rainfall_tel_hr_karnataka_ka_2021_2025.csv"
TARGET_STATION = "Varthur_1"

# Varthur / KC Valley Catchment Physics Parameters
CATCHMENT_AREA_KM2 = 255.0  # Approx KC Valley catchment feeding Bellandur/Varthur
RUNOFF_COEFF = 0.85         # Highly impervious urban area (concrete/asphalt)
DRAINAGE_CAPACITY_CUMECS = 350.0  # Estimated safe carrying capacity before overflow

def compute_ufri(rainfall_mm_hr, area, c, capacity):
    """
    Computes Urban Flood Risk Index (UFRI) based on the Rational Method.
    Returns Peak Discharge (Q) and a 0-10 Risk Index.
    """
    # Q = (C * I * A) / 3.6 for cubic meters per second
    q_peak = (c * rainfall_mm_hr * area) / 3.6
    
    # Normalize against drainage capacity for a 0-10 index
    # If Q exceeds capacity, UFRI hits 10 (critical flood state)
    ufri = np.minimum(10.0, (q_peak / capacity) * 10.0)
    return q_peak, ufri

try:
    print(f"--- 1. Loading Rainfall Telemetry for Physics Engine ---")
    df = pd.read_csv(FILE_PATH, low_memory=False)
    df.columns = [c.strip() for c in df.columns]

    val_col = next((c for c in df.columns if 'rainfall' in c.lower()), None)
    time_col = next((c for c in df.columns if 'acquisition' in c.lower()), None)

    if not val_col or not time_col:
        print("[ERROR] Could not find time or value columns.")
    else:
        # --- 2. ISOLATE VARTHUR DATA ---
        varthur_df = df[df['Station'] == TARGET_STATION].copy()
        print(f"[SUCCESS] Isolated {len(varthur_df)} records for {TARGET_STATION}.")

        varthur_df['datetime'] = pd.to_datetime(varthur_df[time_col], dayfirst=True, errors='coerce')
        varthur_df[val_col] = pd.to_numeric(varthur_df[val_col], errors='coerce')
        
        # Drop NaNs and sort chronologically
        varthur_df = varthur_df.dropna(subset=['datetime', val_col]).sort_values('datetime')

        # --- 3. RUN THE PHYSICS ENGINE ---
        print("\n--- 2. Executing Rational Method & UFRI Calculation ---")
        varthur_df['peak_discharge_cumecs'], varthur_df['ufri_score'] = compute_ufri(
            varthur_df[val_col], 
            CATCHMENT_AREA_KM2, 
            RUNOFF_COEFF, 
            DRAINAGE_CAPACITY_CUMECS
        )

        # Flag critical flood events (UFRI > 7.5)
        flood_events = varthur_df[varthur_df['ufri_score'] > 7.5].copy()
        
        print(f"\n[RESULTS] Identified {len(flood_events)} critical flood-risk hours out of {len(varthur_df)} total recorded hours.")
        
        if not flood_events.empty:
            print("\nTop 5 Highest Risk Flood Events at Varthur based on real telemetry:")
            top_events = flood_events.sort_values('ufri_score', ascending=False).head(5)
            print(top_events[['datetime', val_col, 'peak_discharge_cumecs', 'ufri_score']].to_string(index=False))

except FileNotFoundError:
    print(f"[FATAL] Could not find file at {FILE_PATH}")