"""
gee_erosion_extractor.py — Phase 1: Kerala Coastal Erosion (Layer 2)
=====================================================================
Uses authenticated Google Earth Engine to:
  1. Pull Sentinel-2 imagery over Kerala coastal districts (2019 vs 2024).
  2. Apply NDWI to isolate the land-water boundary.
  3. Calculate inland shoreline retreat in metres/year per sample point.
  4. Output: coastal_erosion_kerala.csv [lat, lon, district, erosion_velocity_m_yr]

RUN PREREQUISITES:
  pip install earthengine-api
  earthengine authenticate
  Then set GEE_PROJECT below.
"""

import ee
import math
import csv
import os

# ===========================================================================
# CONFIG — set your GEE project ID here
# ===========================================================================
GEE_PROJECT = "storage-object-admin-490315"   # <--- CHANGE THIS

OUTPUT_CSV = os.path.join(os.path.dirname(__file__), "coastal_erosion_kerala.csv")

# NDWI threshold: pixels >= threshold are water
NDWI_THRESHOLD = 0.0

# Baseline and current year median composites
BASELINE_START = "2019-01-01"
BASELINE_END   = "2019-12-31"
CURRENT_START  = "2024-01-01"
CURRENT_END    = "2024-12-31"

# Kerala coastal sample transect points (lat, lon, district)
# Chosen from NCSCM (National Centre for Sustainable Coastal Management) at-risk zones
KERALA_TRANSECTS = [
    # Alappuzha — highest erosion district in Kerala (NCSCM 2022)
    {"lat": 9.490, "lon": 76.330, "district": "Alappuzha",  "village": "Arookutty"},
    {"lat": 9.520, "lon": 76.325, "district": "Alappuzha",  "village": "Kanjikuzhy"},
    {"lat": 9.380, "lon": 76.345, "district": "Alappuzha",  "village": "Mararikulam"},
    {"lat": 9.290, "lon": 76.380, "district": "Alappuzha",  "village": "Arthunkal"},

    # Ernakulam — Cherai & Munambam critical zones
    {"lat": 10.145, "lon": 76.180, "district": "Ernakulam", "village": "Cherai Beach North"},
    {"lat": 10.172, "lon": 76.175, "district": "Ernakulam", "village": "Munambam"},

    # Thrissur — Chavakkad & Ponnani boundary
    {"lat": 10.600, "lon": 75.990, "district": "Thrissur",  "village": "Chavakkad"},
    {"lat": 10.640, "lon": 75.970, "district": "Thrissur",  "village": "Kadappuram"},

    # Kollam — high erosion southern stretch
    {"lat": 8.900, "lon": 76.560, "district": "Kollam",     "village": "Neendakara"},
    {"lat": 8.840, "lon": 76.570, "district": "Kollam",     "village": "Alappad"},

    # Thiruvananthapuram — Valiathura critical zone
    {"lat": 8.520, "lon": 76.940, "district": "Thiruvananthapuram", "village": "Valiathura"},
    {"lat": 8.488, "lon": 76.960, "district": "Thiruvananthapuram", "village": "Shankumugham"},
]

# Search radius around each transect point (metres)
SAMPLE_RADIUS_M = 2000


# ===========================================================================
# HELPERS
# ===========================================================================

def get_ndwi_composite(start_date: str, end_date: str) -> ee.Image:
    """Return a median NDWI composite from Sentinel-2 SR over the date range."""
    s2 = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
        .select(["B3", "B8"])  # Green, NIR for NDWI
    )
    median = s2.median()
    ndwi = median.normalizedDifference(["B3", "B8"]).rename("NDWI")
    return ndwi


def water_area_at_point(ndwi_img: ee.Image, lat: float, lon: float) -> float:
    """
    Returns the fraction of water pixels within SAMPLE_RADIUS_M of the point.
    NDWI >= NDWI_THRESHOLD = water.
    """
    point = ee.Geometry.Point([lon, lat])
    circle = point.buffer(SAMPLE_RADIUS_M)

    water_mask = ndwi_img.gte(NDWI_THRESHOLD)

    # Pixel area in m^2 (Sentinel-2 is 10m resolution = 100 m^2/pixel)
    water_stats = water_mask.multiply(ee.Image.pixelArea()).reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=circle,
        scale=10,
        maxPixels=1e9,
    )
    total_stats = ee.Image.pixelArea().reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=circle,
        scale=10,
        maxPixels=1e9,
    )

    water_area = water_stats.get("NDWI").getInfo() or 0.0
    total_area = total_stats.get("area").getInfo() or 1.0
    return float(water_area), float(total_area)


def water_fraction_to_retreat_m(baseline_water_m2: float, current_water_m2: float, radius_m: float) -> float:
    """
    Converts water area gain (m²) into an equivalent coastal retreat distance (m).
    Assumes the erosion front is approximately linear across the sample circle diameter.
    retreat_m = delta_area / (2 * radius)  [width of strip that was lost]
    """
    delta_area = current_water_m2 - baseline_water_m2
    if delta_area <= 0:
        return 0.0  # accretion or stable — no erosion
    # 2 * radius is the approximate "width" of the coastal strip being evaluated
    retreat_m = delta_area / (2.0 * radius_m)
    return round(retreat_m, 2)


# ===========================================================================
# MAIN
# ===========================================================================

def run():
    print("Initialising Google Earth Engine...")
    ee.Initialize(project=GEE_PROJECT)
    print("GEE authenticated OK")

    print("Building NDWI composites (this may take 30–90 seconds per image)...")
    ndwi_baseline = get_ndwi_composite(BASELINE_START, BASELINE_END)
    ndwi_current  = get_ndwi_composite(CURRENT_START,  CURRENT_END)
    print("Composites built OK")

    years = 2024 - 2019  # = 5

    results = []
    for t in KERALA_TRANSECTS:
        lat, lon = t["lat"], t["lon"]
        print(f"  Processing {t['village']} ({lat}, {lon})...")

        try:
            base_water, total_area  = water_area_at_point(ndwi_baseline, lat, lon)
            curr_water, _           = water_area_at_point(ndwi_current,  lat, lon)

            total_retreat_m       = water_fraction_to_retreat_m(base_water, curr_water, SAMPLE_RADIUS_M)
            erosion_velocity_m_yr = round(total_retreat_m / years, 3)

            results.append({
                "lat":                   lat,
                "lon":                   lon,
                "district":              t["district"],
                "village":               t["village"],
                "baseline_water_m2":     round(base_water, 1),
                "current_water_m2":      round(curr_water, 1),
                "total_retreat_m":       total_retreat_m,
                "erosion_velocity_m_yr": erosion_velocity_m_yr,
            })
            print(f"    -> Erosion velocity: {erosion_velocity_m_yr} m/yr")

        except Exception as e:
            print(f"    FAIL for {t['village']}: {e}")
            results.append({
                "lat": lat, "lon": lon,
                "district": t["district"], "village": t["village"],
                "baseline_water_m2": None, "current_water_m2": None,
                "total_retreat_m": None, "erosion_velocity_m_yr": None,
            })

    # Write CSV
    fieldnames = ["lat", "lon", "district", "village",
                  "baseline_water_m2", "current_water_m2",
                  "total_retreat_m", "erosion_velocity_m_yr"]
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nOK Done! Erosion data written to: {OUTPUT_CSV}")
    print(f"  Total points processed: {len(results)}")
    valid = [r for r in results if r["erosion_velocity_m_yr"] is not None]
    if valid:
        avg = sum(r["erosion_velocity_m_yr"] for r in valid) / len(valid)
        print(f"  Average erosion velocity: {avg:.2f} m/yr across Kerala sample")


if __name__ == "__main__":
    run()
