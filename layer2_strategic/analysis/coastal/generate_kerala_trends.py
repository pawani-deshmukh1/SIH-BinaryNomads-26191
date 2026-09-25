import os
import csv
import json
import pandas as pd
import time
from datetime import datetime

THIS_DIR = os.path.dirname(__file__)
CSV_PATH = os.path.join(THIS_DIR, "..", "..", "kerala_coastal_vulnerability_index.csv")
TRENDS_PATH = os.path.join(THIS_DIR, "..", "..", "backend", "fixtures", "strategic_trends.json")

def generate_kerala_trends():
    if not os.path.exists(CSV_PATH):
        print(f"Missing CSV: {CSV_PATH}")
        return

    # Simulate GEE extraction time for the demo
    print("Simulating GEE extraction...")
    time.sleep(12)
    print("Extraction complete.")

    with open(CSV_PATH, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Load existing trends to preserve history
    if os.path.exists(TRENDS_PATH):
        with open(TRENDS_PATH, "r") as f:
            try:
                existing = json.load(f)
            except json.JSONDecodeError:
                existing = []
    else:
        existing = []

    existing_kerala = {e["hab_id"]: e for e in existing if e["hab_id"].startswith("KERALA_COASTAL")}
    non_kerala = [e for e in existing if not e["hab_id"].startswith("KERALA_COASTAL")]

    kerala_trends = []
    # Make time granular enough for demo
    current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for i, r in enumerate(rows):
        sector_name = r.get("sector_name")
        if not sector_name:
            continue
            
        vel = float(r["erosion_velocity_m_yr"])
        cvi_score = float(r["CVI_score"])
        vul_class = r["vulnerability_class"]
        bsi_inc = float(r["bsi_increase"])
        
        # Map CVI class to DISHA strategic risk classes
        if vul_class in ["EXTREME", "VERY HIGH"]:
            risk_class = "CRITICAL"
            runway = [6, 12]
        elif vul_class == "HIGH":
            risk_class = "HIGH"
            runway = [12, 24]
        elif vul_class == "MODERATE":
            risk_class = "MODERATE"
            runway = [24, 48]
        else:
            risk_class = "LOW"
            runway = [48, 72]

        hab_id = f"KERALA_COASTAL_{str(i).zfill(3)}"
        
        # Build history
        old_history = []
        if hab_id in existing_kerala:
            old_history = existing_kerala[hab_id].get("monitors", {}).get("coastal_erosion", {}).get("history", [])
        
        new_history = old_history + [{"date": current_date, "cvi_score": round(cvi_score, 2)}]
            
        trend_obj = {
            "hab_id": hab_id,
            "hab_name": f"{sector_name}, Kerala",
            "strategic_risk_class": risk_class,
            "recommended_action": "EVALUATE_RELOCATION" if risk_class in ["CRITICAL", "HIGH"] else "MONITOR",
            "estimated_runway_months": runway,
            "monitors": {
                "coastal_erosion": {
                    "annual_retreat_rate_m": round(vel, 3),
                    "cvi_score": round(cvi_score, 2),
                    "trend": "ACCELERATING" if (vel > 1.5 or bsi_inc > 0.015) else "STABLE",
                    "source": "Sentinel-2 GEE + NCSCM CVI Methodology",
                    "history": new_history
                },
                "structural_vulnerability": {
                    "degradation_index": round(min(1.0, cvi_score / 40.0), 2),
                    "buildings_at_risk_pct": int(min(100, cvi_score * 2.5)),
                    "trend": "WORSENING" if risk_class in ["CRITICAL", "HIGH"] else "STABLE",
                    "last_assessed": current_date.split(" ")[0]
                }
            }
        }
        kerala_trends.append(trend_obj)

    # Prepend kerala trends so they show up at the top
    combined = kerala_trends + non_kerala
    
    with open(TRENDS_PATH, "w") as f:
        json.dump(combined, f, indent=2)
        
    print(f"Added {len(kerala_trends)} Kerala coastal entries to strategic_trends.json using NCSCM CVI method.")

if __name__ == "__main__":
    generate_kerala_trends()
