from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
import json
from shapely.geometry import shape
from shapely.ops import unary_union

router = APIRouter(prefix="/feedback", tags=["Intelligence"])

class FeedbackRequest(BaseModel):
    endpoint: str
    verdict: str
    timestamp: str

@router.post("/")
def submit_feedback(req: FeedbackRequest):
    """
    Accepts feedback (correct/incorrect) on model outputs or risk fusion scores.
    """
    try:
        import sqlite3
        import os
        
        db_path = os.path.join(os.path.dirname(__file__), "..", "db", "feedback.db")
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Connect and ensure table exists
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS operator_feedback (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type     TEXT NOT NULL,
                entity_id       TEXT NOT NULL,
                feedback_type   TEXT NOT NULL,
                corrected_value TEXT,
                operator_id     TEXT DEFAULT 'operator',
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert feedback
        cursor.execute('''
            INSERT INTO operator_feedback (entity_type, entity_id, feedback_type, corrected_value, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', ("endpoint", req.endpoint, req.verdict, "N/A", req.timestamp))
        
        conn.commit()
        conn.close()
        
        print(f"[Feedback] {req.endpoint} marked {req.verdict} at {req.timestamp} (Saved to SQLite)")
        return {"status": "success", "message": "Feedback recorded in database."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class CalibrateRequest(BaseModel):
    hab_id: str
    actual_geojson: dict
    predicted_geojson: dict

@router.post("/calibrate")
def run_calibration(req: CalibrateRequest):
    """
    Layer 3: Self-Healing AI Calibration.
    Compares the predicted advisory polygon with the actual damage polygon
    derived from drone/satellite imagery after the event.
    Returns the Jaccard Index (IoU) and stores the delta.
    """
    try:
        if not req.actual_geojson.get('features') or not req.predicted_geojson.get('features'):
            return {"status": "success", "accuracy_pct": 0, "missed_area_m2": 0}

        actual = unary_union([shape(f['geometry']) for f in req.actual_geojson.get('features', []) if f.get('geometry')])
        predicted = unary_union([shape(f['geometry']) for f in req.predicted_geojson.get('features', []) if f.get('geometry')])
        
        iou = 0.0
        union_area = actual.union(predicted).area
        if union_area > 0:
            iou = actual.intersection(predicted).area / union_area
            
        delta = actual.difference(predicted)  # Area flooded that we failed to predict
        
        log_entry = {
            "hab_id": req.hab_id,
            "accuracy_pct": round(iou * 100, 1),
            "missed_area_m2": delta.area * 1e10,
            "timestamp": datetime.now().isoformat()
        }
        
        import os
        log_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "calibration_log.json")
        logs = []
        if os.path.exists(log_path):
            with open(log_path, "r") as f:
                logs = json.load(f)
        logs.append(log_entry)
        
        with open(log_path, "w") as f:
            json.dump(logs, f, indent=2)
            
        return {"status": "success", "accuracy_pct": round(iou * 100, 1), "missed_area_m2": delta.area * 1e10}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

