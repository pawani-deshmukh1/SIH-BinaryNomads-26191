import osmnx as ox
import os

print("Downloading Guwahati road network graph...")

# Configure OSMnx to use a faster endpoint and a long timeout
ox.settings.timeout = 180
ox.settings.use_cache = True
ox.settings.overpass_endpoint = "https://lz4.overpass-api.de/api/interpreter"

# Bounding box for Guwahati (West, South, East, North)
bbox = (91.55, 26.05, 91.85, 26.22)

try:
    G = ox.graph_from_bbox(bbox=bbox, network_type='drive', simplify=True)
    
    out_path = os.path.join(os.path.dirname(__file__), "..", "backend", "guwahati_drive.graphml")
    ox.save_graphml(G, out_path)
    
    print(f"Graph successfully saved to {out_path}!")
    print(f"Nodes: {len(G.nodes)}, Edges: {len(G.edges)}")
except Exception as e:
    print(f"Failed to download graph: {e}")
