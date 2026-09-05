from datetime import datetime, timezone

# Teams: Status can be "AVAILABLE", "DISPATCHED", "ON_SCENE", "RETURNING"
teams = {
    "TEAM-A1": {"id": "TEAM-A1", "status": "AVAILABLE", "current_assignment": None, "last_updated": datetime.now(timezone.utc).isoformat(), "lat": None, "lng": None, "last_ping": None, "location_verification": None},
    "TEAM-B2": {"id": "TEAM-B2", "status": "AVAILABLE", "current_assignment": None, "last_updated": datetime.now(timezone.utc).isoformat(), "lat": None, "lng": None, "last_ping": None, "location_verification": None},
    "TEAM-C3": {"id": "TEAM-C3", "status": "AVAILABLE", "current_assignment": None, "last_updated": datetime.now(timezone.utc).isoformat(), "lat": None, "lng": None, "last_ping": None, "location_verification": None},
    "TEAM-D4": {"id": "TEAM-D4", "status": "AVAILABLE", "current_assignment": None, "last_updated": datetime.now(timezone.utc).isoformat(), "lat": None, "lng": None, "last_ping": None, "location_verification": None},
}

# Dispatches: Record of commands sent to teams
dispatches = []

# Field Reports: Updates from the teams on the ground
reports = []

# Safe Zone State: Live resource tracking
# Keyed by safe zone ID (e.g., "SZ001")
safe_zone_inventory = {}
