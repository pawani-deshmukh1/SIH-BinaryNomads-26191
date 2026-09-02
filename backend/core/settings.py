from pydantic import BaseModel
from typing import Literal

class RiskFusionWeights(BaseModel):
    """
    Default weights derived from AHP-based multi-hazard literature.
    Weights sum to 1.0. Team should validate against Assam ground truth.
    """
    damage_weight: float = 0.40    # Structural damage: highest immediate life risk
    flood_weight: float = 0.35     # Flood extent: widespread but survivable
    landslide_weight: float = 0.25 # Landslide: high severity but spatially limited

class TerrainWeights(BaseModel):
    slope_weight: float = 0.60     # Slope dominates landslide susceptibility (AHP)
    elevation_weight: float = 0.40 # Low elevation = flood exposure

class RelocationTierThresholds(BaseModel):
    immediate_threshold: float = 0.70   # risk_score >= 0.70 -> Immediate
    short_term_threshold: float = 0.40  # 0.40-0.70 -> Short-term
    # below 0.40 -> Medium-term

class CellTowerDeadZoneConfig(BaseModel):
    overlap_mode: Literal["centroid", "buffer_m"] = "centroid"
    buffer_m: float = 100.0  # only used if overlap_mode == "buffer_m"

class ScoringThresholds(BaseModel):
    red_zone_red: float = 0.70
    red_zone_orange: float = 0.40

class AppSettings(BaseModel):
    risk_fusion: RiskFusionWeights = RiskFusionWeights()
    terrain: TerrainWeights = TerrainWeights()
    relocation_tiers: RelocationTierThresholds = RelocationTierThresholds()
    cell_tower: CellTowerDeadZoneConfig = CellTowerDeadZoneConfig()
    scoring: ScoringThresholds = ScoringThresholds()

# Singleton
_settings = AppSettings()

def get_settings() -> AppSettings:
    return _settings

def update_settings(new: AppSettings) -> AppSettings:
    global _settings
    _settings = new
    return _settings
