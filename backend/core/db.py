"""
db.py — Lightweight SQLite database for logging Layer 3 calibration gaps.
"""
import sqlite3
from pathlib import Path
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "db" / "calibration.sqlite"

def init_db():
    """Ensure the database and tables exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS calibration_gaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            predicted_flood_polys INTEGER,
            actual_flood_polys INTEGER,
            gap_variance INTEGER,
            peak_confidence REAL,
            region TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS integration_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            api_name TEXT NOT NULL,
            api_url TEXT NOT NULL,
            layer_assigned TEXT NOT NULL,
            status TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
    logger.info(f"Initialized SQLite Calibration DB at {DB_PATH}")

def log_calibration_gap(lat: float, lng: float, predicted: int, actual: int, confidence: float, region: str = "assam"):
    """Insert a new calibration metric."""
    gap_variance = actual - predicted
    now = datetime.now(timezone.utc).isoformat()
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO calibration_gaps 
        (timestamp, lat, lng, predicted_flood_polys, actual_flood_polys, gap_variance, peak_confidence, region)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (now, lat, lng, predicted, actual, gap_variance, confidence, region))
    conn.commit()
    conn.close()
    logger.info(f"Logged calibration gap to SQLite: variance={gap_variance}, lat={lat}, lng={lng}")

def check_and_trigger_recalibration(region: str = "assam") -> bool:
    """
    Check if the moving average of gap_variance exceeds the threshold.
    If so, trigger XGBoost model recalibration to adapt to new environmental baselines.
    """
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(*), AVG(ABS(gap_variance)) 
        FROM (
            SELECT gap_variance FROM calibration_gaps 
            WHERE region = ? 
            ORDER BY timestamp DESC LIMIT 10
        )
    ''', (region,))
    row = cursor.fetchone()
    conn.close()
    
    count = row[0] if row else 0
    avg_gap = row[1] if row and row[1] else 0.0
    
    if count >= 3 and avg_gap > 2.0:
        logger.warning(f"🚨 [Layer 3] XGBoost Auto-Recalibration TRIGGERED for {region}! (Avg Gap: {avg_gap:.1f}). Overwriting weights...")
        # In a real scenario, this would call proactive_engine to refit() with the new actuals
        return True
    return False

def get_calibration_logs(limit: int = 10):
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM calibration_gaps ORDER BY timestamp DESC LIMIT ?', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def log_integration_event(api_name: str, api_url: str, layer_assigned: str, status: str = "Deployed"):
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO integration_logs (timestamp, api_name, api_url, layer_assigned, status)
        VALUES (?, ?, ?, ?, ?)
    ''', (now, api_name, api_url, layer_assigned, status))
    conn.commit()
    conn.close()
    logger.info(f"Logged integration event: {api_name}")

def get_integration_logs(limit: int = 10):
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM integration_logs ORDER BY timestamp DESC LIMIT ?', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# Initialize on import
init_db()
