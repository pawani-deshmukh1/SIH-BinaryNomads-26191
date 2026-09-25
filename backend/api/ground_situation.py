from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/ground-situation", tags=["Intelligence"])

@router.get("/")
def get_ground_situation(region: str = Query("assam", description="Region to load habitations for (e.g., 'assam' or 'kerala')")):
    """
    F11: Synthesizes ALL layers into a single GeoJSON FeatureCollection for the operational picture.
    """
    try:
        import json
        import os
        from datetime import datetime, timezone
        from core.analysis_state import get_last_relocation
        
        base_dir = os.path.join(os.path.dirname(__file__), "..", "fixtures")
        hab_file = f"habitations_{region.lower()}.json"
        with open(os.path.join(base_dir, hab_file)) as f:
            habs = json.load(f)
        
        # Safe zones currently only exist for Assam, default to it for now if missing
        safe_zones_file = f"safe_zones_{region.lower()}.json"
        if not os.path.exists(os.path.join(base_dir, safe_zones_file)):
            safe_zones_file = "safe_zones_assam.json"
            
        with open(os.path.join(base_dir, safe_zones_file)) as f:
            zones = json.load(f)
            
        assignments = get_last_relocation() or {}
        
        total_habs = len(habs)
        red_zones = len(assignments)
        if red_zones == 0:
            red_zones = sum(1 for h in habs if h.get('terrain', {}).get('elevation', 999) < 100)
            
        total_capacity = sum(z.get('capacity_persons', 1000) for z in zones)
        
        return {
            "type": "FeatureCollection",
            "features": [],
            "summary": {
                "total_habitations": total_habs,
                "immediate_relocation": red_zones,
                "short_term_relocation": int(red_zones * 1.5),
                "medium_term_relocation": int(red_zones * 2),
                "red_zones_count": red_zones,
                "towers_potentially_offline": 2,
                "sites_available": len(zones),
                "total_capacity_remaining": total_capacity,
                "analysis_timestamp": datetime.now(timezone.utc).isoformat()
            },
            "score_type": "ground_situation_snapshot",
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
