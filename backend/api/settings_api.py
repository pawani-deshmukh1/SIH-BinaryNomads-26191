from fastapi import APIRouter
from core.settings import get_settings, update_settings, AppSettings, RiskFusionWeights, TerrainWeights, RelocationTierThresholds, CellTowerDeadZoneConfig, ScoringThresholds

router = APIRouter(prefix="/settings", tags=["Settings"])

@router.get("/")
def read_settings():
    """Returns current AppSettings along with default AHP values for reference."""
    current = get_settings()
    # Provide the default instance to help the frontend show reference markers
    defaults = AppSettings()
    
    return {
        "current": current.model_dump(),
        "defaults": defaults.model_dump(),
        "_description": {
            "risk_fusion": "Weights for the 3 hazards. Must sum to 1.0. Based on AHP.",
            "terrain": "Weights for terrain features in susceptibility scoring.",
            "relocation_tiers": "Thresholds for categorizing relocation urgency based on risk_score.",
            "cell_tower": "Logic for marking towers as potentially offline.",
            "scoring": "Thresholds for coloring red zones."
        }
    }

@router.put("/")
def write_settings(new_settings: AppSettings):
    """Updates the global AppSettings instance."""
    updated = update_settings(new_settings)
    return updated

@router.post("/reset")
def reset_settings():
    """Resets settings back to their AHP-derived defaults."""
    updated = update_settings(AppSettings())
    return updated
