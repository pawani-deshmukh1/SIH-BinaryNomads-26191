"""
analysis_state.py — Shared in-memory state between all endpoints.

/analyze writes here after each COP computation.
/red-zones, /towers, /relocation-plan read from here to avoid
being disconnected from the actual AI output.

Thread-safety: FastAPI runs in a single-threaded async event loop,
so a plain dict is safe without locks for this use case.
"""
import threading
from datetime import datetime, timezone
from typing import Optional

_lock = threading.Lock()

# Last COP output from /analyze
_last_cop: Optional[dict] = None

# Last relocation plan from the optimizer
_last_relocation_plan: Optional[dict] = None

# Active vehicle registry: {vehicle_id: VehicleState dict}
_vehicles: dict[str, dict] = {}

# Active evac site states: {site_id: EvacSiteState dict}
_evac_sites: dict[str, dict] = {}

# Loaded red zone geometries for geofencing (list of shapely geometries, lazy-loaded)
_red_zone_geometries: Optional[list] = None


# ── COP ──────────────────────────────────────────────────────────────────────

def set_last_cop(cop: dict) -> None:
    global _last_cop, _red_zone_geometries
    with _lock:
        _last_cop = cop
        _red_zone_geometries = None  # invalidate geofence cache on new COP


def get_last_cop() -> Optional[dict]:
    with _lock:
        return _last_cop


# ── Relocation Plan ───────────────────────────────────────────────────────────

def set_last_relocation(plan: dict) -> None:
    global _last_relocation_plan
    with _lock:
        _last_relocation_plan = plan


def get_last_relocation() -> Optional[dict]:
    with _lock:
        return _last_relocation_plan


# ── Vehicles ─────────────────────────────────────────────────────────────────

def register_vehicle(vehicle_id: str, name: str, v_type: str, lat: float, lng: float,
                     assigned_route: list = None, destination_site_id: str = None) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    state = {
        "id": vehicle_id,
        "name": name,
        "type": v_type,
        "lat": lat,
        "lng": lng,
        "speed_kmh": 0.0,
        "heading_deg": 0.0,
        "status": "en_route",  # en_route | arrived | standby | alert
        "assigned_route": assigned_route or [],
        "destination_site_id": destination_site_id,
        "geofence_alert": False,
        "geofence_alert_zone": None,
        "registered_at": now,
        "last_updated": now,
    }
    with _lock:
        _vehicles[vehicle_id] = state
    return state


def update_vehicle_position(vehicle_id: str, lat: float, lng: float,
                             speed_kmh: float = None, heading_deg: float = None) -> Optional[dict]:
    """Update position and return (updated_state, geofence_violated: bool, zone_id: str|None)"""
    with _lock:
        if vehicle_id not in _vehicles:
            return None
        state = _vehicles[vehicle_id]
        state["lat"] = lat
        state["lng"] = lng
        state["last_updated"] = datetime.now(timezone.utc).isoformat()
        if speed_kmh is not None:
            state["speed_kmh"] = speed_kmh
        if heading_deg is not None:
            state["heading_deg"] = heading_deg
        return dict(state)  # return copy


def get_all_vehicles() -> list[dict]:
    with _lock:
        return list(_vehicles.values())


def get_vehicle(vehicle_id: str) -> Optional[dict]:
    with _lock:
        return _vehicles.get(vehicle_id)


def set_vehicle_status(vehicle_id: str, status: str, alert_zone: str = None) -> None:
    with _lock:
        if vehicle_id in _vehicles:
            _vehicles[vehicle_id]["status"] = status
            _vehicles[vehicle_id]["geofence_alert"] = (status == "alert")
            _vehicles[vehicle_id]["geofence_alert_zone"] = alert_zone


# ── Evac Sites ───────────────────────────────────────────────────────────────

def init_evac_site(site_id: str, name: str, lat: float, lng: float,
                   capacity: int, recommendation_score: float) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    state = {
        "id": site_id,
        "name": name,
        "lat": lat,
        "lng": lng,
        "capacity_total": capacity,
        "capacity_remaining": capacity,
        "occupancy": 0,
        "status": "available",  # available | partial | full | compromised
        "resources_needed": [],
        "ground_truth_confirmed": False,
        "in_red_zone": False,
        "last_updated": now,
    }
    with _lock:
        _evac_sites[site_id] = state
    return state


def update_evac_capacity(site_id: str, occupancy: int,
                          resources_needed: list = None) -> Optional[dict]:
    with _lock:
        if site_id not in _evac_sites:
            return None
        site = _evac_sites[site_id]
        site["occupancy"] = occupancy
        site["capacity_remaining"] = max(0, site["capacity_total"] - occupancy)
        site["last_updated"] = datetime.now(timezone.utc).isoformat()
        if resources_needed is not None:
            site["resources_needed"] = resources_needed
        # Auto-update status
        ratio = occupancy / site["capacity_total"] if site["capacity_total"] > 0 else 0
        if ratio >= 1.0:
            site["status"] = "full"
        elif ratio >= 0.75:
            site["status"] = "partial"
        else:
            site["status"] = "available"
        return dict(site)


def get_all_evac_sites() -> list[dict]:
    with _lock:
        return list(_evac_sites.values())


def get_evac_site(site_id: str) -> Optional[dict]:
    with _lock:
        return _evac_sites.get(site_id)


def flag_site_in_red_zone(site_id: str, red_zone_id: str) -> None:
    """Called by geofencing when a site falls inside a red zone. Triggers a ground truth ping."""
    with _lock:
        if site_id in _evac_sites:
            _evac_sites[site_id]["in_red_zone"] = True
            _evac_sites[site_id]["red_zone_id"] = red_zone_id
            _evac_sites[site_id]["ground_truth_confirmed"] = False


def confirm_site_safe(site_id: str) -> None:
    with _lock:
        if site_id in _evac_sites:
            _evac_sites[site_id]["in_red_zone"] = False
            _evac_sites[site_id]["ground_truth_confirmed"] = True


# ── Geofencing ────────────────────────────────────────────────────────────────

def get_red_zone_geometries() -> list:
    """
    Lazy-load red zone shapely geometries from the last COP.
    Cached until a new /analyze call invalidates it.
    """
    global _red_zone_geometries
    with _lock:
        if _red_zone_geometries is not None:
            return _red_zone_geometries
        cop = _last_cop
    
    if not cop:
        return []

    try:
        from shapely.geometry import shape
        geoms = []
        for feat in cop.get("features", []):
            if feat.get("properties", {}).get("layer_type") == "red_zone":
                try:
                    geom = shape(feat["geometry"])
                    zone_id = feat["properties"].get("id", "unknown")
                    risk = feat["properties"].get("risk_score", 0.0)
                    geoms.append({"geom": geom, "id": zone_id, "risk_score": risk})
                except Exception:
                    pass
        with _lock:
            _red_zone_geometries = geoms
        return geoms
    except ImportError:
        return []


def check_geofence(lat: float, lng: float) -> tuple[bool, Optional[str], float]:
    """
    Check if a point (lat, lng) is inside any red zone.
    Returns: (is_inside, zone_id, risk_score)
    """
    try:
        from shapely.geometry import Point
    except ImportError:
        return False, None, 0.0

    pt = Point(lng, lat)  # shapely uses (lng, lat)
    for zone in get_red_zone_geometries():
        try:
            if zone["geom"].contains(pt) or zone["geom"].distance(pt) < 0.001:  # ~100m buffer
                return True, zone["id"], zone["risk_score"]
        except Exception:
            pass
    return False, None, 0.0


# ── Bootstrap demo evac sites ─────────────────────────────────────────────────

def bootstrap_demo_sites():
    """Pre-load the Assam demo evac sites so the state is populated on startup."""
    demo_sites = [
        ("EZ-A01", "Nagaon Govt School", 26.355, 92.685, 1200, 0.91),
        ("EZ-A02", "Nagaon District Stadium", 26.342, 92.671, 3500, 0.79),
        ("EZ-A03", "Rupahi Relief Ground", 26.362, 92.655, 600, 0.65),
        ("EZ-K01", "Gaurikund Relief Camp", 30.734, 79.063, 800, 0.87),
        ("EZ-K02", "Sonprayag School Ground", 30.737, 79.057, 350, 0.74),
    ]
    for sid, name, lat, lng, cap, score in demo_sites:
        if sid not in _evac_sites:
            init_evac_site(sid, name, lat, lng, cap, score)


# Auto-bootstrap on import
bootstrap_demo_sites()
