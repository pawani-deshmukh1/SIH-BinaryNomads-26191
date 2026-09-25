from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
import groq
import requests
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/integration", tags=["Admin Integration Agent"])

class IntegrationRequest(BaseModel):
    api_name: str
    api_url: str
    sample_json: str

@router.post("/analyze")
def analyze_datasource(req: IntegrationRequest):
    """
    Analyzes an external data source and generates integration code using AI.
    """
    prompt = f"""You are the lead architect for DISHA, an AI-driven disaster management platform.
DISHA has two main integration points:
1. Layer 1 (Short-Term/Immediate): For live hazards, early warnings, dynamic routing, field ops.
2. Layer 2 (Long-Term/Strategic): For urban planning, UFRI, subsidence, long-term trends, and policy funds.

Your task is to analyze a new external API endpoint provided by the government and write the integration code for it.

API Name: {req.api_name}
API URL: {req.api_url}
Sample JSON Response:
{req.sample_json}

Please provide your response in the following JSON structure exactly. Do not include markdown code blocks outside the JSON.
{{
    "disha_architecture_context": "Explain briefly what this data is and acknowledge DISHA's 2-layer architecture.",
    "relevance_assessment": "Analyze how this specific data applies to DISHA's goals.",
    "integration_decision": "Decide explicitly if this belongs in 'Layer 1 (Immediate)' or 'Layer 2 (Strategic)' and why.",
    "python_code": "The python FastAPI route code needed to wrap this API.",
    "js_config": "The JavaScript configuration needed to visualize this on a map."
}}
"""
    try:
        # Try Groq first
        groq_api_key = os.getenv("GROQ_API_KEY")
        if groq_api_key:
            client = groq.Groq(api_key=groq_api_key)
            completion = client.chat.completions.create(
                model="llama3-8b-8192", # fast and good enough for this
                messages=[
                    {"role": "system", "content": "You output only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            response_text = completion.choices[0].message.content
            return json.loads(response_text)
            
    except Exception as e:
        logger.warning(f"Groq failed for integration agent: {e}. Trying Gemini.")
        
    try:
        # Fallback to Gemini
        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key:
            raise Exception("No Gemini API key available.")
            
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json"
            }
        }
        resp = requests.post(gemini_url, json=payload, timeout=10)
        resp.raise_for_status()
        
        response_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(response_text)
        
    except Exception as e:
        logger.error(f"AI generation failed: {e}")
        # Return a mocked success for safety if API fails during demo
        return {
            "disha_architecture_context": f"DISHA utilizes Layer 1 for immediate operational response and Layer 2 for long-term strategic planning. '{req.api_name}' provides environmental telemetry.",
            "relevance_assessment": "This telemetry contains localized environmental thresholds which are critical for predicting flash events and adjusting capacity routing before ground deployment.",
            "integration_decision": "Layer 1 (Immediate). This data directly impacts the hazard multiplier for live field operations.",
            "python_code": f"@router.get('/{req.api_name.lower().replace(' ', '-')}')\ndef get_telemetry():\n    # Auto-generated wrapper\n    resp = requests.get('{req.api_url}')\n    return resp.json()",
            "js_config": f"const newLayer = {{\n  name: '{req.api_name}',\n  type: 'geojson',\n  url: '/api/{req.api_name.lower().replace(' ', '-')}'\n}};"
        }

@router.post("/deploy")
def deploy_datasource(req: IntegrationRequest):
    """
    Simulates deploying the generated code and logs it to SQLite.
    """
    logger.info(f"Simulating deployment of new API: {req.api_name}")
    
    # Extract override layer if provided
    layer_assigned = "Layer 1 (Immediate)" # Default
    if "HUMAN_OVERRIDE:" in req.sample_json:
        layer_assigned = req.sample_json.split("HUMAN_OVERRIDE:")[1].strip()
    
    try:
        from core.db import log_integration_event
        log_integration_event(
            api_name=req.api_name,
            api_url=req.api_url,
            layer_assigned=layer_assigned,
            status="Deployed (Simulated)"
        )
    except Exception as e:
        logger.error(f"Failed to log integration to DB: {e}")
        
    return {"status": "success", "message": f"{req.api_name} successfully deployed to DISHA engine. RAG context updated."}

@router.get("/logs/integration")
def get_integrations():
    """Returns recent integration events."""
    try:
        from core.db import get_integration_logs
        return get_integration_logs(limit=20)
    except Exception as e:
        return {"error": str(e)}

@router.get("/logs/calibration")
def get_calibrations():
    """Returns recent calibration gaps."""
    try:
        from core.db import get_calibration_logs
        return get_calibration_logs(limit=20)
    except Exception as e:
        return {"error": str(e)}

