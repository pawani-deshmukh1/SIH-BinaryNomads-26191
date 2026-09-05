from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import uuid
from core.field_state import teams, reports, safe_zone_inventory

router = APIRouter()

class FieldReportRequest(BaseModel):
    team_id: str
    dispatch_id: Optional[str] = None
    rescued_count: int
    notes: Optional[str] = ""
    photo_url: Optional[str] = None

@router.get("/")
def get_all_reports():
    return {"status": "success", "reports": reports}

@router.post("/")
def submit_report(req: FieldReportRequest):
    if req.team_id not in teams:
        raise HTTPException(status_code=404, detail="Team not found")
        
    report_id = f"REP-{uuid.uuid4().hex[:6].upper()}"
    report_record = {
        "id": report_id,
        "team_id": req.team_id,
        "dispatch_id": req.dispatch_id or teams[req.team_id].get("current_assignment"),
        "rescued_count": req.rescued_count,
        "notes": req.notes,
        "photo_url": req.photo_url,
        "submitted_at": datetime.now(timezone.utc).isoformat()
    }
    
    reports.insert(0, report_record) # Insert at beginning for newest-first
    
    # Update safe zone state if this team is assigned to a dispatch
    from core.field_state import dispatches
    dispatch = next((d for d in dispatches if d["id"] == report_record["dispatch_id"]), None)
    
    if dispatch:
        sz_id = dispatch["safe_zone_id"]
        if sz_id not in safe_zone_inventory:
            safe_zone_inventory[sz_id] = {"current_population": 0, "resources_used": {}}
        
        safe_zone_inventory[sz_id]["current_population"] += req.rescued_count
        
    return {"status": "success", "report": report_record}
