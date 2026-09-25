from fastapi.testclient import TestClient
from backend.main import app
import json

client = TestClient(app)

def test_layer_0_and_1():
    print("--- Testing Layer 0 (Risk & Triggers) ---")
    
    # 1. Live Risk (Triggers)
    print("1. Testing /live-risk/")
    resp = client.get("/live-risk/?lat=26.35&lng=92.68&habitation_id=ASSAM_RIVER_001")
    if resp.status_code == 200:
        data = resp.json()
        print(f"[PASS] fusion zone: {data.get('fusion', {}).get('final_zone')}")
    else:
        print(f"[FAIL] {resp.status_code} {resp.text}")
        return

    # 2. Red Zones
    print("2. Testing /red-zones/")
    resp = client.get("/red-zones/")
    hab_id = "HAB_MORIGAON_CHAR_001"
    if resp.status_code == 200:
        data = resp.json()
        features = data.get("features", [])
        print(f"[PASS] Found {len(features)} red zones.")
    else:
        print(f"[FAIL] {resp.status_code} {resp.text}")
        return

    print("\n--- Testing Layer 1 (Advisory & Relocation) ---")
    
    # 3. Advisory
    print(f"3. Testing /advisory/{hab_id}")
    resp = client.get(f"/advisory/{hab_id}")
    if resp.status_code == 200:
        data = resp.json()
        status = data.get("status")
        if status == "success":
            adv = data.get("advisory", {})
            lt = adv.get("estimated_lead_time_hrs")
            plan = adv.get("relocation_plan", {})
            print(f"[PASS] Advisory generated.")
            print(f"   Lead Time: {lt} hours")
            print(f"   Recommended Site: {plan.get('recommended_site', {}).get('name')}")
        else:
            print(f"[FAIL] Advisory returned logic error: {data.get('message')}")
    else:
        print(f"[FAIL] {resp.status_code} {resp.text}")
        return

    print("\n[PASS] All Layer 0 & 1 core endpoints completed successfully.")

if __name__ == "__main__":
    test_layer_0_and_1()
