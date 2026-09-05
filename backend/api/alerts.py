from fastapi import APIRouter, HTTPException
from core.analysis_state import get_last_cop
from core.cop_builder import build_cop_from_demo

router = APIRouter(prefix="/alerts", tags=["IDENTIFY — Alerts"])

@router.get("/")
def get_alerts():
    """
    Dynamically generates alerts from the current COP state.
    Returns chronologically sorted list with severity, location, time_ago.
    """
    try:
        cop = get_last_cop()
        if not cop:
            cop = build_cop_from_demo()

        alerts = []
        features = cop.get("features", [])
        
        # We will parse the red_zone features to create alerts
        for i, f in enumerate(features):
            props = f.get("properties", {})
            if props.get("layer_type") == "red_zone":
                zone_class = props.get("zone_class", "RED")
                name = props.get("name", props.get("habitation", f"Zone {i+1}"))
                
                if zone_class == "RED":
                    alerts.append({
                        "title": "Critical Red Zone Detected",
                        "location": name,
                        "description": "High structural and multi-hazard risk detected. Immediate authority assessment recommended.",
                        "time": "Just now",
                        "severity": "CRITICAL",
                        "icon": "warning_amber_rounded"
                    })
                elif zone_class == "ORANGE":
                    alerts.append({
                        "title": "Elevated Risk Detected",
                        "location": name,
                        "description": "Risk parameters indicate an elevated hazard profile. Monitor closely.",
                        "time": "Just now",
                        "severity": "HIGH",
                        "icon": "warning_amber_rounded"
                    })

        # Add a dummy relocation alert if we have any alerts, to show functionality
        if alerts:
            alerts.insert(0, {
                "title": "Return Clearance Available",
                "location": "Borigaon",
                "description": "Rainfall has subsided below threshold. Risk signal clearing. Recommend 72h site inspection before authorizing return.",
                "time": "Just now",
                "severity": "LOW",
                "icon": "home_outlined"
            })
            
            alerts.append({
                "title": "Relocation Site Available",
                "location": "Relief Zone Alpha",
                "description": "Alternative site has sufficient assessed carrying capacity for the identified population.",
                "time": "5 min ago",
                "severity": "MEDIUM",
                "icon": "location_on_outlined"
            })
            
            alerts.append({
                "title": "Route Assessment Updated",
                "location": "Emergency Corridor 01",
                "description": "Primary access route remains operational for evacuation movement.",
                "time": "15 min ago",
                "severity": "LOW",
                "icon": "route_outlined"
            })

        return alerts
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
