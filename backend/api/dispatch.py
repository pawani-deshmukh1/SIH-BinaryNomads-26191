from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import uuid
from core.field_state import teams, dispatches

router = APIRouter()

class DispatchRequest(BaseModel):
    team_id: str
    habitation_id: str
    safe_zone_id: str
    target_population: int
    notes: Optional[str] = ""

class LocationPayload(BaseModel):
    lat: float
    lng: float

@router.get("/")
def get_all_dispatches():
    now = datetime.now(timezone.utc)
    for t_id, t_info in teams.items():
        if t_info["status"] in ["DISPATCHED", "ON_SCENE", "RETURNING"]:
            ping_time_str = t_info.get("last_ping") or t_info.get("last_updated")
            if ping_time_str:
                ping_dt = datetime.fromisoformat(ping_time_str)
                if (now - ping_dt).total_seconds() > 60:
                    t_info["status"] = "SIGNAL_LOST"
                    
    return {"status": "success", "dispatches": dispatches, "teams": list(teams.values())}

@router.post("/")
def create_dispatch(req: DispatchRequest):
    if req.team_id not in teams:
        raise HTTPException(status_code=404, detail="Team not found")
    
    if teams[req.team_id]["status"] != "AVAILABLE":
        raise HTTPException(status_code=400, detail=f"Team {req.team_id} is currently {teams[req.team_id]['status']}")
    
    dispatch_id = f"DSP-{uuid.uuid4().hex[:6].upper()}"
    dispatch_record = {
        "id": dispatch_id,
        "team_id": req.team_id,
        "habitation_id": req.habitation_id,
        "safe_zone_id": req.safe_zone_id,
        "target_population": req.target_population,
        "notes": req.notes,
        "status": "DISPATCHED",
        "dispatched_at": datetime.now(timezone.utc).isoformat()
    }
    
    dispatches.append(dispatch_record)
    
    # Update team state
    teams[req.team_id]["status"] = "DISPATCHED"
    teams[req.team_id]["current_assignment"] = dispatch_id
    teams[req.team_id]["last_updated"] = datetime.now(timezone.utc).isoformat()
    
    return {"status": "success", "dispatch": dispatch_record, "team": teams[req.team_id]}

@router.post("/{team_id}/accept")
def accept_dispatch(team_id: str):
    if team_id not in teams:
        raise HTTPException(status_code=404, detail="Team not found")
    
    team = teams[team_id]
    if team["status"] != "DISPATCHED":
        raise HTTPException(status_code=400, detail="Team is not currently dispatched")
        
    team["status"] = "ON_SCENE"
    team["last_updated"] = datetime.now(timezone.utc).isoformat()
    
    # Update dispatch status
    for d in dispatches:
        if d["id"] == team["current_assignment"]:
            d["status"] = "ON_SCENE"
            break
            
    return {"status": "success", "team": team}
    
@router.post("/{team_id}/complete")
def complete_dispatch(team_id: str):
    if team_id not in teams:
        raise HTTPException(status_code=404, detail="Team not found")
    
    team = teams[team_id]
    # Update dispatch status
    for d in dispatches:
        if d["id"] == team["current_assignment"]:
            d["status"] = "COMPLETED"
            break
            
    team["status"] = "AVAILABLE"
    team["current_assignment"] = None
    team["last_updated"] = datetime.now(timezone.utc).isoformat()
    team["location_verification"] = None
    
    return {"status": "success", "team": team}

@router.post("/{team_id}/location")
def update_location(team_id: str, payload: LocationPayload):
    if team_id not in teams:
        raise HTTPException(status_code=404, detail="Team not found")
        
    teams[team_id]["lat"] = payload.lat
    teams[team_id]["lng"] = payload.lng
    teams[team_id]["last_ping"] = datetime.now(timezone.utc).isoformat()
    
    # If they were SIGNAL_LOST but they pinged, restore status (fallback)
    if teams[team_id]["status"] == "SIGNAL_LOST":
        teams[team_id]["status"] = "ON_SCENE" if teams[team_id].get("current_assignment") else "AVAILABLE"
        
    return {"status": "success"}

@router.post("/{team_id}/request-verification")
def request_verification(team_id: str):
    if team_id not in teams:
        raise HTTPException(status_code=404, detail="Team not found")
    teams[team_id]["location_verification"] = "PENDING"
    return {"status": "success"}

@router.post("/{team_id}/confirm-location")
def confirm_location(team_id: str):
    if team_id not in teams:
        raise HTTPException(status_code=404, detail="Team not found")
    teams[team_id]["location_verification"] = "VERIFIED"
    return {"status": "success"}
