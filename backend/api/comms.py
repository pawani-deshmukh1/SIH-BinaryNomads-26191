"""
comms.py — Communications and SMS Alerting (Layer 1/2)

Integrates with Textbee.dev to turn a spare Android phone into an SMS gateway.
Used to send automated offline-prep alerts to field officers entering dead zones.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
import os
import httpx
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/comms", tags=["Communications"])

# In production, these come from .env
TEXTBEE_API_KEY = os.environ.get("TEXTBEE_API_KEY", "")
TEXTBEE_DEVICE_ID = os.environ.get("TEXTBEE_DEVICE_ID", "")

class SMSRequest(BaseModel):
    phone_number: str
    message: str

async def _send_textbee_sms(phone_number: str, message: str):
    """Async background task to send SMS via Textbee gateway."""
    if not TEXTBEE_API_KEY or not TEXTBEE_DEVICE_ID:
        logger.warning(f"[COMMS] No Textbee API key found. Mocking SMS to {phone_number}: '{message}'")
        return
        
    url = f"https://api.textbee.dev/api/v1/gateway/devices/{TEXTBEE_DEVICE_ID}/sendSMS"
    headers = {
        "x-api-key": TEXTBEE_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "recipients": [phone_number],
        "smsBody": message
    }
    
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(url, headers=headers, json=payload, timeout=10.0)
            if res.status_code in (200, 201):
                logger.info(f"[COMMS] SMS successfully sent to {phone_number} via Textbee")
            else:
                logger.error(f"[COMMS] Textbee failed: {res.status_code} - {res.text}")
    except Exception as e:
        logger.error(f"[COMMS] Error calling Textbee API: {e}")

@router.post("/sms/")
async def send_sms(req: SMSRequest, background_tasks: BackgroundTasks):
    """
    Direct endpoint to send an SMS.
    """
    background_tasks.add_task(_send_textbee_sms, req.phone_number, req.message)
    return {"status": "queued", "phone": req.phone_number}

@router.post("/offline-alert/")
async def trigger_offline_alert(officer_id: str, phone: str, tower_id: str, background_tasks: BackgroundTasks):
    """
    Triggered when an officer enters a tower's coverage that is marked 'at_risk'.
    Sends an automated warning.
    """
    msg = (
        f"DISHA ALERT: Officer {officer_id}, you are entering a comms dead zone "
        f"near failing tower {tower_id}. Your app has been cached for offline use. "
        f"Last known GPS synced with Control Room."
    )
    background_tasks.add_task(_send_textbee_sms, phone, msg)
    return {"status": "alert_queued", "officer": officer_id}
