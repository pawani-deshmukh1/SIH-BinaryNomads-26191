import requests
import time

URL = "http://127.0.0.1:8000/dispatch/"
print("Dispatching TEAM-A1...")
requests.post(URL, json={
    "team_id": "TEAM-A1",
    "habitation_id": "HAB_CHAR_001",
    "safe_zone_id": "SZ001",
    "target_population": 100
})

time.sleep(1)

URL_LOC = "http://127.0.0.1:8000/dispatch/TEAM-A1/location"
print("Pinging location for TEAM-A1...")
requests.post(URL_LOC, json={"lat": 26.342, "lng": 92.651})
print("Pinged! Dashboard should show marker for TEAM-A1.")

print("Waiting 65 seconds to trigger SIGNAL_LOST...")
# Instead of waiting 65s in the script and holding the background task, I'll just check it manually later.
