import os
import json
from fastapi import APIRouter, Request, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import random

try:
    from groq import Groq
    client = Groq()
except Exception as e:
    client = None
    print(f"Groq API skipped in SOS Webhook (Fallback mode): {e}")

router = APIRouter(prefix="/sos", tags=["SOS NLP Webhook"])

# In-memory store for SOS signals to be pulled by the frontend map
active_sos_signals = []

class WebhookPayload(BaseModel):
    message_id: str
    sender_phone: str
    raw_text: str
    timestamp: str

def process_sos_with_llm(payload: WebhookPayload):
    """
    Background task that calls Groq Llama-3 to parse the raw panic text.
    If Groq fails or is unconfigured, uses a heuristic fallback.
    """
    print(f"Processing incoming SOS from {payload.sender_phone}: {payload.raw_text}")
    
    extracted_data = {
        "location_entity": "Unknown Location",
        "severity": "YELLOW",
        "demographics": "Unknown",
        "raw_text": payload.raw_text
    }
    
    if client:
        prompt = f"""
        You are a highly advanced disaster response NLP engine. 
        Extract the following from this SOS message:
        1. location_entity: The specific neighborhood, road, or landmark mentioned.
        2. severity: Choose one of [RED, ORANGE, YELLOW] based on water depth and threat to life.
        3. demographics: Summarize the vulnerable people mentioned (e.g., "Elderly", "3 Children").
        
        Respond ONLY with a valid JSON object.
        
        Message: "{payload.raw_text}"
        """
        try:
            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={"type": "json_object"}
            )
            data = json.loads(completion.choices[0].message.content)
            extracted_data.update(data)
        except Exception as e:
            print(f"LLM parsing failed: {e}")
            # Fallback heuristics
            if "water" in payload.raw_text.lower() and "ft" in payload.raw_text.lower():
                extracted_data["severity"] = "RED"
    else:
        # Hardcoded fallback for demo reliability
        if "zoo road" in payload.raw_text.lower():
            extracted_data["location_entity"] = "Zoo Road"
            extracted_data["severity"] = "RED"
            extracted_data["demographics"] = "Elderly (80yrs)"
        elif "apollo" in payload.raw_text.lower():
            extracted_data["location_entity"] = "Apollo Hospital, Christian Basti"
            extracted_data["severity"] = "RED"
            extracted_data["demographics"] = "3 Kids"

    # Geocode the location entity (Mocked bounding box for Guwahati for instant demo mapping)
    # Guwahati rough bbox: 26.1, 91.7 to 26.2, 91.8
    mock_lat = round(random.uniform(26.12, 26.18), 5)
    mock_lng = round(random.uniform(91.72, 91.80), 5)
    
    signal = {
        "id": payload.message_id,
        "phone": payload.sender_phone,
        "lat": mock_lat,
        "lng": mock_lng,
        "location": extracted_data.get("location_entity", "Unknown"),
        "severity": extracted_data.get("severity", "YELLOW"),
        "demographics": extracted_data.get("demographics", "None specified"),
        "raw_text": payload.raw_text,
        "timestamp": payload.timestamp
    }
    
    active_sos_signals.append(signal)
    print(f"SOS Processed and Geocoded: {signal}")

@router.post("/webhook")
async def receive_whatsapp_webhook(payload: WebhookPayload, background_tasks: BackgroundTasks):
    """
    Standard webhook endpoint designed to be hit by Twilio or WhatsApp Business APIs.
    Offloads NLP processing to a background task so the messaging provider gets an instant 200 OK.
    """
    background_tasks.add_task(process_sos_with_llm, payload)
    return {"status": "received"}

@router.get("/active")
async def get_active_sos():
    """
    Endpoint for the Cesium map UI to poll and display pulsating red SOS markers.
    """
    return {"signals": active_sos_signals}
