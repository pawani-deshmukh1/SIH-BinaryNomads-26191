from fastapi.testclient import TestClient
from backend.main import app
import json
import base64

client = TestClient(app)

def test_layer_3():
    print("--- Testing Layer 3 (Post-Disaster & Calibration) ---")
    
    # 1. Test Field Reports (Mobile App)
    print("1. Testing /field-reports/")
    dummy_image = base64.b64encode(b"dummy_image_data").decode('utf-8')
    payload = {
        "team_id": "TEAM-A1",
        "rescued_count": 15,
        "notes": "Severe inundation, evacuation routes blocked.",
        "photo_url": "dummy_base64_url"
    }
    
    resp = client.post("/field-reports/", json=payload)
    if resp.status_code in [200, 201]:
        data = resp.json()
        print(f"[PASS] Field report submitted. Status: {data.get('status')}")
    else:
        print(f"[FAIL] Field report submission: {resp.status_code} {resp.text}")

    # 2. Test Calibration (IoU Calculation)
    print("2. Testing /feedback/calibrate")
    cal_payload = {
        "hab_id": "HAB_MORIGAON_CHAR_001",
        "actual_geojson": {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[0,0], [0,1], [1,1], [1,0], [0,0]]]}}]},
        "predicted_geojson": {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[0,0], [0,1], [1,1], [0.5,0], [0,0]]]}}]}
    }
    resp = client.post("/feedback/calibrate", json=cal_payload)
    if resp.status_code == 200:
        data = resp.json()
        print(f"[PASS] Calibration completed.")
        print(f"   IoU Score: {data.get('accuracy_pct', 'N/A')}%")
        print(f"   Missed Area: {data.get('missed_area_m2', 'N/A')} m2")
    else:
        print(f"[FAIL] Calibration: {resp.status_code} {resp.text}")

    print("\n[PASS] Layer 3 endpoints checked.")

if __name__ == "__main__":
    test_layer_3()
