import requests
import math
import json
import os
import time

print("Fetching REAL live wind data from Open-Meteo...")

# India bounding box roughly: lat 5 to 40, lon 65 to 100
lat_min, lat_max = 5.0, 40.0
lon_min, lon_max = 65.0, 100.0

# 25x25 grid = 625 points
nx, ny = 25, 25
dx = (lon_max - lon_min) / (nx - 1)
dy = (lat_max - lat_min) / (ny - 1)

points = []
# leaflet-velocity format expects data starting from top-left (lat_max, lon_min)
# iterating row by row, left to right.
for j in range(ny):
    lat = lat_max - j * dy
    for i in range(nx):
        lon = lon_min + i * dx
        points.append((lat, lon))

# Chunk into sizes of 100 for Open-Meteo
u_data = []
v_data = []

chunk_size = 50
for i in range(0, len(points), chunk_size):
    chunk = points[i:i+chunk_size]
    lats = ",".join([str(round(p[0], 4)) for p in chunk])
    lons = ",".join([str(round(p[1], 4)) for p in chunk])
    
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lats}&longitude={lons}&current=wind_speed_10m,wind_direction_10m"
    resp = requests.get(url)
    data = resp.json()
    
    if type(data) is list:
        # Multiple locations returned as a list
        for loc in data:
            speed = loc['current']['wind_speed_10m'] # km/h
            dir_deg = loc['current']['wind_direction_10m']
            
            speed_ms = speed * (1000.0 / 3600.0)
            dir_rad = math.radians(dir_deg)
            u = -speed_ms * math.sin(dir_rad)
            v = -speed_ms * math.cos(dir_rad)
            u_data.append(round(u, 2))
            v_data.append(round(v, 2))
    elif 'current' in data:
        # Single location
        speed = data['current']['wind_speed_10m']
        dir_deg = data['current']['wind_direction_10m']
        speed_ms = speed * (1000.0 / 3600.0)
        dir_rad = math.radians(dir_deg)
        u = -speed_ms * math.sin(dir_rad)
        v = -speed_ms * math.cos(dir_rad)
        u_data.append(round(u, 2))
        v_data.append(round(v, 2))
    else:
        print("Error from API:", data)
        # fallback to 0
        for _ in chunk:
            u_data.append(0)
            v_data.append(0)
        
    time.sleep(1.0) # avoid rate limit

# leaflet-velocity format
wind_json = [
    {
        "header": {
            "parameterCategory": 2,
            "parameterNumber": 2,
            "surface1Type": 103,
            "surface1Value": 10.0,
            "scanMode": 0,
            "nx": nx,
            "ny": ny,
            "lo1": lon_min,
            "la1": lat_max,
            "lo2": lon_max,
            "la2": lat_min,
            "dx": dx,
            "dy": dy
        },
        "data": u_data
    },
    {
        "header": {
            "parameterCategory": 2,
            "parameterNumber": 3,
            "surface1Type": 103,
            "surface1Value": 10.0,
            "scanMode": 0,
            "nx": nx,
            "ny": ny,
            "lo1": lon_min,
            "la1": lat_max,
            "lo2": lon_max,
            "la2": lat_min,
            "dx": dx,
            "dy": dy
        },
        "data": v_data
    }
]

# Ensure data dir exists
data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "dashboard", "data")
os.makedirs(data_dir, exist_ok=True)

out_file = os.path.join(data_dir, "wind-global.json")
with open(out_file, "w") as f:
    json.dump(wind_json, f)

print(f"Successfully cached REAL wind data at {out_file}")
