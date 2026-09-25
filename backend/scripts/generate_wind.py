import json
import math
import os

# India bounding box roughly: lat 5 to 40, lon 65 to 100
# We will create a grid of 1 degree resolution
lat_min, lat_max = 0, 45
lon_min, lon_max = 60, 105
dx = 1.0
dy = 1.0

nx = int((lon_max - lon_min) / dx) + 1
ny = int((lat_max - lat_min) / dy) + 1

u_data = []
v_data = []

# Simulate a cyclone/vortex over the Bay of Bengal (lat 15, lon 90)
center_lat = 15
center_lon = 90

for j in range(ny):
    # leaflet-velocity usually expects la1 to be top, la2 to be bottom, so lat decreases.
    # Actually, GFS format is usually lat from max to min. Let's do max to min.
    lat = lat_max - j * dy
    for i in range(nx):
        lon = lon_min + i * dx
        
        # Calculate distance to center
        dist = math.sqrt((lat - center_lat)**2 + (lon - center_lon)**2)
        
        if dist == 0:
            u, v = 0, 0
        else:
            # Vortex velocity (tangential)
            # strength decays with distance
            speed = 20.0 * math.exp(-dist / 10.0)
            
            # angle from center
            angle = math.atan2(lat - center_lat, lon - center_lon)
            
            # perpendicular angle (cyclonic, counter-clockwise in northern hemisphere)
            tangent_angle = angle + math.pi / 2
            
            u = speed * math.cos(tangent_angle)
            v = speed * math.sin(tangent_angle)
            
            # Add general monsoon flow (south-westerly)
            u += 5.0
            v += 3.0
            
        u_data.append(round(u, 2))
        v_data.append(round(v, 2))

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

print(f"Generated wind cache at {out_file}")
