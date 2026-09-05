from fastapi import APIRouter
from core.field_state import safe_zone_inventory

router = APIRouter()

@router.get("/")
def get_all_safe_zone_states():
    return {"status": "success", "safe_zones": safe_zone_inventory}

@router.get("/{safe_zone_id}")
def get_safe_zone_state(safe_zone_id: str):
    state = safe_zone_inventory.get(safe_zone_id, {"current_population": 0, "resources_used": {}})
    return {"status": "success", "safe_zone_id": safe_zone_id, "state": state}

@router.post("/demo-seed")
def seed_demo_data():
    from core.field_state import teams, reports, dispatches
    from datetime import datetime, timezone, timedelta
    import uuid
    
    # 1. Set Lahorighat School (sz_01) to 847 persons
    # For demo we don't have the exact ID here, usually it's "sz-1" or similar. Let's just set "sz-1".
    safe_zone_inventory["sz-1"] = {"current_population": 847, "resources_used": {}}
    
    # 2. Add some past field reports
    now = datetime.now(timezone.utc)
    reports.clear()
    reports.extend([
        {
            "id": f"REP-{uuid.uuid4().hex[:6].upper()}",
            "team_id": "TEAM-C3",
            "dispatch_id": "DSP-101",
            "rescued_count": 178,
            "notes": "Wave 3 completed. Evacuees settled.",
            "photo_url": None,
            "submitted_at": (now - timedelta(minutes=15)).isoformat()
        },
        {
            "id": f"REP-{uuid.uuid4().hex[:6].upper()}",
            "team_id": "TEAM-B2",
            "dispatch_id": "DSP-102",
            "rescued_count": 357,
            "notes": "Wave 2. Heavy rain slowing transport.",
            "photo_url": None,
            "submitted_at": (now - timedelta(minutes=120)).isoformat()
        },
        {
            "id": f"REP-{uuid.uuid4().hex[:6].upper()}",
            "team_id": "TEAM-A1",
            "dispatch_id": "DSP-103",
            "rescued_count": 312,
            "notes": "Wave 1 successful. Road clear.",
            "photo_url": None,
            "submitted_at": (now - timedelta(minutes=340)).isoformat()
        }
    ])
    
    # 3. Create active dispatches
    dispatches.clear()
    dsp_a1 = f"DSP-{uuid.uuid4().hex[:6].upper()}"
    dispatches.append({
        "id": dsp_a1,
        "team_id": "TEAM-A1",
        "habitation_id": "hab-01", # Borigaon
        "safe_zone_id": "sz-1",
        "target_population": 1240,
        "notes": "Urgent evacuation requested.",
        "status": "ON_SCENE",
        "dispatched_at": (now - timedelta(minutes=10)).isoformat()
    })
    
    teams["TEAM-A1"]["status"] = "ON_SCENE"
    teams["TEAM-A1"]["current_assignment"] = dsp_a1
    
    dsp_b2 = f"DSP-{uuid.uuid4().hex[:6].upper()}"
    dispatches.append({
        "id": dsp_b2,
        "team_id": "TEAM-B2",
        "habitation_id": "hab-02",
        "safe_zone_id": "sz-2",
        "target_population": 800,
        "notes": "Returning to base",
        "status": "COMPLETED",
        "dispatched_at": (now - timedelta(hours=3)).isoformat()
    })
    
    teams["TEAM-B2"]["status"] = "RETURNING"
    teams["TEAM-B2"]["current_assignment"] = None

    return {"status": "success", "message": "Demo data seeded!"}
