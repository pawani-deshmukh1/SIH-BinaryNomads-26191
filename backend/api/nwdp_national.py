from fastapi import APIRouter
import json
import random

router = APIRouter(prefix="/nwdp", tags=["NWDP National Integration"])

@router.get("/reservoirs")
async def get_national_reservoirs():
    """
    Simulates a fetch from nwdp.nwic.gov.in for major Indian reservoirs.
    In production, this proxies the NWDP telemetry API.
    """
    reservoirs = [
        {"id": "R1", "name": "Bhakra Dam", "lat": 31.3995, "lng": 76.4357, "level_m": 490.5, "capacity_pct": 75},
        {"id": "R2", "name": "Tehri Dam", "lat": 30.3789, "lng": 78.4800, "level_m": 810.0, "capacity_pct": 82},
        {"id": "R3", "name": "Hirakud Dam", "lat": 21.5284, "lng": 83.8741, "level_m": 185.0, "capacity_pct": 91},
        {"id": "R4", "name": "Nagarjuna Sagar", "lat": 16.5786, "lng": 79.3175, "level_m": 170.2, "capacity_pct": 60},
        {"id": "R5", "name": "Sardar Sarovar", "lat": 21.8315, "lng": 73.7493, "level_m": 130.5, "capacity_pct": 88},
        {"id": "R6", "name": "Umiam Lake (Barapani)", "lat": 25.6582, "lng": 91.8953, "level_m": 978.4, "capacity_pct": 96},  # Meghalaya/Assam critical
        {"id": "R7", "name": "Doyang Dam", "lat": 26.2238, "lng": 94.2818, "level_m": 315.6, "capacity_pct": 98},     # Nagaland (affects Assam)
        {"id": "R8", "name": "Ranganadi Dam", "lat": 27.3552, "lng": 93.7667, "level_m": 560.1, "capacity_pct": 99},   # Arunachal (critical for Assam)
    ]
    
    # Introduce some dynamic variance
    for res in reservoirs:
        res["capacity_pct"] = min(100, res["capacity_pct"] + random.uniform(-2, 5))
        if res["capacity_pct"] > 95:
            res["status"] = "WARNING_RELEASE_IMMINENT"
            res["color"] = "#ef4444" # red
        elif res["capacity_pct"] > 85:
            res["status"] = "HIGH"
            res["color"] = "#f97316" # orange
        else:
            res["status"] = "NORMAL"
            res["color"] = "#22c55e" # green

    return {"status": "success", "source": "nwdp.nwic.gov.in", "data": reservoirs}
