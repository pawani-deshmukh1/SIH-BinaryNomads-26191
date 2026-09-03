from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime

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
