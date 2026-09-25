"""
dynamic_routing.py - Layer 1 Dynamic Route Optimization
Builds OSMnx graphs and calculates hazard-avoiding shortest paths.
"""
import osmnx as ox
import networkx as nx
from shapely.geometry import Polygon, LineString
import logging
from pathlib import Path
import json
import os

ox.settings.use_cache = True
ox.settings.overpass_endpoint = "https://lz4.overpass-api.de/api/interpreter"
ox.settings.timeout = 5

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "osm_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# We use the bbox for Assam Nagaon district for the demo
# Adjusted slightly to capture Nagaon, Rupahi, and nearby chars
DEMO_BBOX = (92.35, 26.20, 92.75, 26.50) # min_lng, min_lat, max_lng, max_lat

def get_base_graph(bbox=DEMO_BBOX):
    """
    Load or fetch the base 'drive' network for the bounding box.
    """
    import hashlib
    key = f"{bbox[0]:.4f}_{bbox[1]:.4f}_{bbox[2]:.4f}_{bbox[3]:.4f}"
    filename = f"graph_{hashlib.md5(key.encode()).hexdigest()[:8]}.graphml"
    cache_path = CACHE_DIR / filename
    
    if cache_path.exists():
        logger.info(f"[OSMnx] Loading cached graph from {filename}")
        return ox.load_graphml(cache_path)
    
    logger.info(f"[OSMnx] Fetching road network from Overpass... This will take a moment.")
    min_lng, min_lat, max_lng, max_lat = bbox
    # osmnx uses (north, south, east, west)
    try:
        G = ox.graph_from_bbox(bbox=(max_lat, min_lat, max_lng, min_lng), network_type='drive')
        logger.info(f"[OSMnx] Graph fetched. Saving to {filename}")
        ox.save_graphml(G, cache_path)
        return G
    except Exception as e:
        logger.error(f"[OSMnx] Failed to fetch graph: {e}")
        return None

def build_safe_graph(G, hazard_polygons: list[Polygon]):
    """
    Removes edges from the graph that intersect with any hazard polygon.
    """
    if not hazard_polygons or G is None:
        return G
        
    G_safe = G.copy()
    edges_to_remove = []
    
    for u, v, key, data in G_safe.edges(keys=True, data=True):
        if 'geometry' in data:
            line = data['geometry']
        else:
            line = LineString([(G_safe.nodes[u]['x'], G_safe.nodes[u]['y']),
                               (G_safe.nodes[v]['x'], G_safe.nodes[v]['y'])])
        
        for poly in hazard_polygons:
            if line.intersects(poly):
                edges_to_remove.append((u, v, key))
                break
                
    G_safe.remove_edges_from(edges_to_remove)
    logger.info(f"[OSMnx] Removed {len(edges_to_remove)} hazard-intersecting edges.")
    return G_safe

def get_safe_route(G_safe, lat1, lng1, lat2, lng2):
    """
    Returns (distance_km, line_string_coords)
    If no path exists, returns (float('inf'), [])
    """
    if G_safe is None:
        # Fallback to Haversine if graph fails
        from math import radians, sin, cos, sqrt, atan2
        R = 6371.0
        dlat = radians(lat2 - lat1)
        dlng = radians(lng2 - lng1)
        a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
        dist = R * 2 * atan2(sqrt(a), sqrt(1.0 - a))
        return dist, [[lat1, lng1], [lat2, lng2]]

    try:
        orig = ox.distance.nearest_nodes(G_safe, X=lng1, Y=lat1)
        dest = ox.distance.nearest_nodes(G_safe, X=lng2, Y=lat2)
        
        # We use shortest_path_length with weight='length'
        route = nx.shortest_path(G_safe, orig, dest, weight='length')
        distance_meters = nx.shortest_path_length(G_safe, orig, dest, weight='length')
        
        # Build coordinates for the route
        coords = []
        for node_id in route:
            node = G_safe.nodes[node_id]
            coords.append([node['y'], node['x']]) # Leaflet expects [lat, lng]
            
        return distance_meters / 1000.0, coords
    except nx.NetworkXNoPath:
        logger.warning(f"[OSMnx] No safe path found between {(lat1, lng1)} and {(lat2, lng2)}")
        return float('inf'), []
    except Exception as e:
        logger.error(f"[OSMnx] Routing error: {e}")
        return float('inf'), []
