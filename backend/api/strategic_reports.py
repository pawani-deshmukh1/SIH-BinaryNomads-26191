from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
import json
from datetime import datetime, timezone
import uuid

router = APIRouter()
REPORTS_FILE = os.path.join(os.path.dirname(__file__), "..", "fixtures", "strategic_reports.json")

class StrategicReport(BaseModel):
    lat: float
    lng: float
    report_type: str  # "construction" | "waterlogging"
    description: str

def load_reports():
    if not os.path.exists(REPORTS_FILE):
        return []
    with open(REPORTS_FILE, "r") as f:
        return json.load(f)

def save_reports(reports):
    with open(REPORTS_FILE, "w") as f:
        json.dump(reports, f, indent=2)

@router.post("/")
def submit_strategic_report(req: StrategicReport):
    if req.report_type not in ["construction", "waterlogging"]:
        raise HTTPException(status_code=422, detail="Invalid report_type. Must be 'construction' or 'waterlogging'.")
    
    if not req.description or len(req.description.strip()) == 0:
        raise HTTPException(status_code=422, detail="Description is required.")
        
    reports = load_reports()
    report_id = f"S-REP-{uuid.uuid4().hex[:6].upper()}"
    
    new_report = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [req.lng, req.lat]
        },
        "properties": {
            "id": report_id,
            "report_type": req.report_type,
            "description": req.description,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "pending_verification",
            "mock": False
        }
    }
    
    reports.append(new_report)
    save_reports(reports)
    
    return {"status": "success", "report_id": report_id, "data": new_report}

@router.get("/")
def get_strategic_reports():
    return {
        "type": "FeatureCollection",
        "features": load_reports()
    }
