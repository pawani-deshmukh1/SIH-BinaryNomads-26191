"""
cache_osm.py — Builds Guwahati road graph from Geofabrik PBF (no Overpass needed).
Run once: python cache_osm.py
"""
import subprocess, sys, os, urllib.request

BACKEND_DIR = "C:\\Users\\Ashutosh\\Desktop\\DISHA\\backend"
OUT_GRAPHML = os.path.join(BACKEND_DIR, "guwahati_drive.graphml")
PBF_PATH    = os.path.join(BACKEND_DIR, "fixtures", "assam-latest.osm.pbf")
GEOFABRIK_URL = "https://download.geofabrik.de/asia/india/assam-latest.osm.pbf"

# Guwahati bbox
NORTH, SOUTH, EAST, WEST = 26.25, 26.05, 91.90, 91.55

# ── 1. Ensure pyrosm is installed ──────────────────────────────────────────
try:
    import pyrosm
except ImportError:
    print("Installing pyrosm...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyrosm", "-q"])
    import pyrosm

import osmnx as ox
import networkx as nx
import pandas as pd
from shapely.geometry import box

# ── 2. Download PBF if needed ───────────────────────────────────────────────
os.makedirs(os.path.dirname(PBF_PATH), exist_ok=True)
if os.path.exists(PBF_PATH) and os.path.getsize(PBF_PATH) > 100_000:
    print(f"PBF already present ({os.path.getsize(PBF_PATH)/1e6:.1f} MB)")
else:
    print("Downloading Assam OSM PBF from Geofabrik (~80MB, one-time)...")
    urllib.request.urlretrieve(GEOFABRIK_URL, PBF_PATH)
    print(f"Downloaded: {os.path.getsize(PBF_PATH)/1e6:.1f} MB")

# ── 3. Read drive network via pyrosm ───────────────────────────────────────
print("Parsing PBF and building drive graph (may take ~60s for Assam)...")
osm = pyrosm.OSM(PBF_PATH, bounding_box=[WEST, SOUTH, EAST, NORTH])
nodes, edges = osm.get_network(network_type="driving", nodes=True)

if nodes is None or edges is None or len(nodes) == 0:
    print("ERROR: No road data found in bbox. Check coordinates.")
    sys.exit(1)

print(f"Got {len(nodes)} nodes, {len(edges)} edges from pyrosm")

# ── 4. Convert to OSMnx graph ──────────────────────────────────────────────
G = osm.to_graph(nodes, edges, graph_type="networkx", retain_all=False)
G = ox.utils_graph.get_largest_component(G, strongly=True)

node_count = len(G.nodes)
if node_count < 100:
    print(f"ERROR: Graph too small ({node_count} nodes)")
    sys.exit(1)

# ── 5. Save ────────────────────────────────────────────────────────────────
ox.save_graphml(G, OUT_GRAPHML)
print(f"\nSUCCESS: {node_count} nodes, {len(G.edges)} edges")
print(f"Saved to: {OUT_GRAPHML}")
print("Uvicorn will auto-reload and log 'Graph loaded!' on next restart.")


