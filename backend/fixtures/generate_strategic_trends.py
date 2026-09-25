import json
import os
import random
from datetime import datetime, timezone

FIXTURES_DIR = os.path.join(os.path.dirname(__file__))
HABITATIONS_FILE = os.path.join(FIXTURES_DIR, "habitations_assam.json")
OUTPUT_FILE = os.path.join(FIXTURES_DIR, "strategic_trends.json")

# Real-world literature data for Assam riverbank erosion (Brahmaputra)
# Source: Borgohain et al., 2023 (NDWI time-series analysis)
MORIGAON_ANNUAL_RETREAT_M = 85.0
BARPETA_ANNUAL_RETREAT_M = 45.0
DEFAULT_ANNUAL_RETREAT_M = 15.0

def generate_trends():
    with open(HABITATIONS_FILE, 'r') as f:
        habitations = json.load(f)

    trends = []
    
    for hab in habitations:
        district = hab.get("district", "Unknown")
        hab_type = hab.get("type", "unknown")
        
        # 1. Riverbank Erosion (Mainly for Chars / Riverbank communities)
        if hab_type == "char" or "river" in hab_type.lower():
            if district == "Morigaon":
                retreat_rate = MORIGAON_ANNUAL_RETREAT_M + random.uniform(-5.0, 5.0)
            elif district == "Barpeta":
                retreat_rate = BARPETA_ANNUAL_RETREAT_M + random.uniform(-3.0, 3.0)
            else:
                retreat_rate = DEFAULT_ANNUAL_RETREAT_M + random.uniform(-2.0, 2.0)
                
            total_loss_24mo = retreat_rate * 2
            
            # Distance to river in meters (simulate distance shrinking)
            # If distance is small, runway is short.
            current_distance = hab.get("dist_to_river_m", 500) 
            
            # Runway: how many months until the river consumes the habitation?
            months_left_linear = int((current_distance / retreat_rate) * 12)
            months_left_accelerating = int(months_left_linear * 0.7) # 30% faster if accelerating
            
            if months_left_linear < 24:
                risk_class = "CRITICAL"
                action = "PLANNED_RELOCATION"
            elif months_left_linear < 60:
                risk_class = "HIGH"
                action = "EVALUATE_RELOCATION"
            else:
                risk_class = "MODERATE"
                action = "MONITOR"
                
            trend_data = {
                "hab_id": hab["id"],
                "hab_name": hab["name"],
                "strategic_risk_class": risk_class,
                "recommended_action": action,
                "estimated_runway_months": [months_left_accelerating, months_left_linear],
                "monitors": {
                    "riverbank_erosion": {
                        "annual_retreat_rate_m": round(retreat_rate, 1),
                        "total_loss_m_24mo": round(total_loss_24mo, 1),
                        "trend": "ACCELERATING",
                        "source": "Borgohain et al., 2023 (NDWI time-series)",
                        "monthly_series": [round((retreat_rate/12) * (1 + random.uniform(-0.2, 0.2)), 2) for _ in range(24)]
                    },
                    "structural_vulnerability": {
                        "degradation_index": round(random.uniform(0.4, 0.8), 2),
                        "buildings_at_risk_pct": random.randint(20, 60),
                        "trend": "WORSENING",
                        "last_assessed": "2026-01"
                    }
                }
            }
        else:
            # For hill/urban communities, focus on structural / scar growth
            # We use a synthetic degradation for now, as literature data is specific to riverbank
            trend_data = {
                "hab_id": hab["id"],
                "hab_name": hab["name"],
                "strategic_risk_class": "MODERATE",
                "recommended_action": "MONITOR",
                "estimated_runway_months": [48, 72],
                "monitors": {
                    "cumulative_scar_growth": {
                        "scar_pct_increase_12mo": round(random.uniform(2.0, 8.0), 1),
                        "trend": "STABLE",
                        "monthly_series": [round(random.uniform(0.1, 0.5), 2) for _ in range(24)]
                    },
                    "structural_vulnerability": {
                        "degradation_index": round(random.uniform(0.2, 0.5), 2),
                        "buildings_at_risk_pct": random.randint(5, 25),
                        "trend": "STABLE",
                        "last_assessed": "2026-01"
                    }
                }
            }
            
        trends.append(trend_data)
        
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(trends, f, indent=2)
        
    print(f"Generated {len(trends)} strategic trends in {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_trends()
