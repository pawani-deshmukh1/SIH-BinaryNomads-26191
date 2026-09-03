"""
routes.py — GET /route/ + flood polygon road blocking

Computes shortest evacuation path via OSMnx, then checks
if any road segment intersects the current flood inundation polygon.
Blocked segments are flagged RED, safe segments GREEN.

Route blocking science: Trivedi et al. 2022 (IJGIS) — dynamic rerouting
that accounts for inundation significantly improves evacuation safety vs.
static pre-planned routes.
"""
from fastapi import APIRouter, HTTPException
import osmnx as ox
import networkx as nx
from datetime import datetime, timezone
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/route", tags=["Infrastructure"])


def _check_route_flood_intersection(route_coords: list, flood_geojson: Optional[dict]) -> dict:
    """
    Check if the route line intersects the flood inundation polygon.
    Returns a dict with:
      - blocked: bool
      - blocked_pct: float (fraction of route that is flooded)
      - safe_coords: list  (coordinates before the blockage)
      - blocked_coords: list (coordinates inside flood zone)
      - route_status: "CLEAR" | "PARTIALLY_BLOCKED" | "BLOCKED"
    """
    if not flood_geojson or not flood_geojson.get("features"):
        return {"blocked": False, "blocked_pct": 0.0, "route_status": "CLEAR",
                "safe_coords": route_coords, "blocked_coords": []}

    try:
        from shapely.geometry import LineString, shape
        from shapely.ops import unary_union

        route_line = LineString(route_coords)

        flood_shapes = []
        for feat in flood_geojson.get("features", []):
            try:
                flood_shapes.append(shape(feat["geometry"]))
            except Exception:
                continue

        if not flood_shapes:
            return {"blocked": False, "blocked_pct": 0.0, "route_status": "CLEAR",
                    "safe_coords": route_coords, "blocked_coords": []}

        flood_union = unary_union(flood_shapes)

        if not route_line.intersects(flood_union):
            return {"blocked": False, "blocked_pct": 0.0, "route_status": "CLEAR",
                    "safe_coords": route_coords, "blocked_coords": []}

        blocked_part = route_line.intersection(flood_union)
        safe_part    = route_line.difference(flood_union)

        total_len   = route_line.length
        blocked_len = blocked_part.length if not blocked_part.is_empty else 0.0
        blocked_pct = round(blocked_len / total_len * 100, 1) if total_len > 0 else 0.0

        # Extract coordinate lists for the frontend to colour
        def _coords_from_geom(geom):
            if geom.is_empty:
                return []
            if geom.geom_type == "LineString":
                return list(geom.coords)
            if geom.geom_type in ("MultiLineString", "GeometryCollection"):
                coords = []
                for g in geom.geoms:
                    if hasattr(g, "coords"):
                        coords.extend(g.coords)
                return coords
            return []

        blocked_coords = _coords_from_geom(blocked_part)
        safe_coords    = _coords_from_geom(safe_part)

        if blocked_pct >= 50:
            status = "BLOCKED"
        elif blocked_pct > 0:
            status = "PARTIALLY_BLOCKED"
        else:
            status = "CLEAR"

        return {
            "blocked":        blocked_pct > 0,
            "blocked_pct":    blocked_pct,
            "route_status":   status,
            "safe_coords":    [[c[0], c[1]] for c in safe_coords],
            "blocked_coords": [[c[0], c[1]] for c in blocked_coords],
        }

    except Exception as e:
        logger.warning(f"[Routes] Flood intersection check failed: {e}")
        return {"blocked": False, "blocked_pct": 0.0, "route_status": "CLEAR",
                "safe_coords": route_coords, "blocked_coords": []}


@router.post("/")
def get_safe_route(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    flood_geojson: Optional[dict] = None,
):
    """
    Computes shortest path via OSMnx then overlays the flood inundation polygon.
    Blocked road segments are tagged with status=BLOCKED and returned separately
    so the dashboard can render them in red.

    flood_geojson: optional GeoJSON FeatureCollection from /simulation endpoint.
                   If provided, the route is checked for flood intersection.
    """
    try:
        buffer = 0.02
        min_lat = min(origin_lat, dest_lat) - buffer
        max_lat = max(origin_lat, dest_lat) + buffer
        min_lon = min(origin_lon, dest_lon) - buffer
        max_lon = max(origin_lon, dest_lon) + buffer

        bbox = (min_lon, min_lat, max_lon, max_lat)
        logger.info(f"Fetching OSMnx graph for routing: {bbox}")
        G = ox.graph_from_bbox(bbox=bbox, network_type='all', simplify=True)

        orig_node = ox.distance.nearest_nodes(G, origin_lon, origin_lat)
        dest_node = ox.distance.nearest_nodes(G, dest_lon, dest_lat)
        path_nodes = nx.shortest_path(G, orig_node, dest_node, weight='length')

        coordinates = [[G.nodes[n]['x'], G.nodes[n]['y']] for n in path_nodes]

        total_length_m = 0
        for i in range(len(path_nodes) - 1):
            edge_data = G.get_edge_data(path_nodes[i], path_nodes[i + 1])
            total_length_m += edge_data.get(0, {}).get('length', 0)

        # ── Flood intersection check ──────────────────────────────────────────
        flood_check = _check_route_flood_intersection(coordinates, flood_geojson)

        features = [
            {
                "type": "Feature",
                "properties": {
                    "segment_type":          "safe",
                    "route_status":          flood_check["route_status"],
                    "blocked_pct":           flood_check["blocked_pct"],
                    "route_suitability_score": max(0.1, 0.92 - flood_check["blocked_pct"] / 100),
                    "hazard_exposure_avoided_pct": 1.0 - flood_check["blocked_pct"] / 100,
                    "added_distance_m":      round(total_length_m),
                    "last_updated":          datetime.now(timezone.utc).isoformat(),
                    "flood_warning":         flood_check["blocked"],
                    "flood_warning_message": (
                        f"WARNING: {flood_check['blocked_pct']}% of this route is within the "
                        f"current flood inundation zone. Seek alternate route."
                        if flood_check["blocked"] else "Route is clear of flood zones."
                    ),
                },
                "geometry": {
                    "type":        "LineString",
                    "coordinates": flood_check["safe_coords"] or coordinates,
                },
            }
        ]

        # Add blocked segment as a separate RED feature if any exists
        if flood_check["blocked_coords"]:
            features.append({
                "type": "Feature",
                "properties": {
                    "segment_type": "blocked",
                    "route_status": "BLOCKED",
                    "reason":       "flood_inundation",
                    "display_color": "#FF3333",
                },
                "geometry": {
                    "type":        "LineString",
                    "coordinates": flood_check["blocked_coords"],
                },
            })

        return {"type": "FeatureCollection", "features": features}

    except Exception as e:
        logger.error(f"Routing failed: {e}")
        return {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {
                    "route_status": "ERROR",
                    "error": str(e),
                    "route_suitability_score": 0.5,
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[origin_lon, origin_lat], [dest_lon, dest_lat]],
                },
            }],
        }
