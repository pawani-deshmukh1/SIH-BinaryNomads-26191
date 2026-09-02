from pydantic import BaseModel
from typing import Literal, Dict, Optional
from datetime import datetime

class ModelConfidence(BaseModel):
    score_type: Literal["model_confidence"] = "model_confidence"
    score: float           # softmax/sigmoid output, 0.0-1.0
    last_updated: datetime

class RiskScore(BaseModel):
    score_type: Literal["risk_score"] = "risk_score"
    score: float
    contributing_factors: Dict  # e.g., {"damage": {"weight": 0.4, "value": 0.8}, ...}
    color_tier: Literal["red", "orange", "green"]
    last_updated: datetime

class RouteSuitabilityScore(BaseModel):
    score_type: Literal["route_suitability_score"] = "route_suitability_score"
    score: float
    hazard_exposure_avoided_pct: float
    added_distance_m: float
    last_updated: datetime

class RecommendationScore(BaseModel):
    score_type: Literal["recommendation_score"] = "recommendation_score"
    score: float
    last_updated: datetime
