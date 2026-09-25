import requests

url = "http://localhost:8001/api/strategic-reports/"

# Test 1: Valid
res = requests.post(url, json={
    "lat": 26.15,
    "lng": 91.75,
    "report_type": "waterlogging",
    "description": "Valid test"
})
print("Test 1 (Valid):", res.status_code, res.json())

# Test 2: Invalid type
res = requests.post(url, json={
    "lat": 26.15,
    "lng": 91.75,
    "report_type": "alien_landing",
    "description": "Invalid test"
})
print("Test 2 (Invalid Type):", res.status_code, res.json())

# Test 3: Missing fields (lat)
res = requests.post(url, json={
    "lng": 91.75,
    "report_type": "waterlogging",
    "description": "Missing lat"
})
print("Test 3 (Missing Lat):", res.status_code, res.json())
