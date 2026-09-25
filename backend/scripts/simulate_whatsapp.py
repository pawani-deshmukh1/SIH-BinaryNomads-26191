import requests
import json
import time
import uuid
from datetime import datetime

WEBHOOK_URL = "http://127.0.0.1:8001/api/sos/webhook"

MOCK_MESSAGES = [
    {
        "phone": "+91 9876543210",
        "text": "Bhaiya we are stuck near Zoo Road, water is 5ft, my grandma is 80 years old and needs oxygen."
    },
    {
        "phone": "+91 8765432109",
        "text": "Urgent! 3 kids trapped on roof behind Apollo hospital Christian Basti. Water rising fast!"
    },
    {
        "phone": "+91 7654321098",
        "text": "Need boat rescue near Dispur Secretariat. 10 people stuck, 1 pregnant woman."
    }
]

def simulate_sos_traffic():
    print("Initializing DISHA SOS WhatsApp Simulator...")
    print(f"Target Webhook: {WEBHOOK_URL}\n")
    
    for msg in MOCK_MESSAGES:
        payload = {
            "message_id": f"wamid.{uuid.uuid4().hex[:16]}",
            "sender_phone": msg["phone"],
            "raw_text": msg["text"],
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        print(f"Sending SOS from {payload['sender_phone']}...")
        try:
            res = requests.post(WEBHOOK_URL, json=payload)
            if res.status_code == 200:
                print(f"✅ Webhook acknowledged (Status: 200).")
            else:
                print(f"❌ Failed to reach Webhook (Status: {res.status_code})")
        except Exception as e:
            print(f"Error firing webhook: {e}")
            
        # Wait 3 seconds between fake messages to mimic real-world spacing
        time.sleep(3)
        
    print("\nSimulation complete. Check backend logs for LLM parsing output.")
    print("Frontend maps polling /api/sos/active will now render these points.")

if __name__ == "__main__":
    simulate_sos_traffic()
