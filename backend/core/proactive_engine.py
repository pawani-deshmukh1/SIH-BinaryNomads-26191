"""
proactive_engine.py — Layer A Static Susceptibility Scorer

Loads the XGBoost joblib models trained on:
  - NASA Global Landslide Catalog (442 NE India events)
  - HydroRIVERS flood extents (10,000 NE India events)
  - NASA SRTM DEM (elevation, slope, aspect, TRI)
  - CHIRPS rainfall (annual + daily)
  - ESA WorldCover 2021 (vegetation proxy)

Accepts tabular terrain features for a habitation coordinate and returns:
  - landslide_score: 0.0 - 1.0 probability
  - flood_score: 0.0 - 1.0 probability
  - zone_class: RED / ORANGE / YELLOW / GREEN
  - top_factors: list of (feature, importance) for explainability

This is entirely separate from the ONNX image-based pipeline (pipeline.py).
That pipeline handles the bonus post-disaster analysis module.
This engine handles the core PS requirement: pre-disaster proactive scoring.
"""
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).resolve().parent.parent / "models" if (Path(__file__).resolve().parent.parent / "models").exists() else Path(__file__).resolve().parent.parent.parent / "layer0_imminent" / "models"

# Thresholds for Red/Orange/Yellow/Green classification
# Tuned for NE India hazard profile
ZONE_THRESHOLDS = {
    "RED":    0.70,
    "ORANGE": 0.45,
    "YELLOW": 0.25,
}


class ProactiveEngine:
    """
    Singleton engine that loads joblib XGBoost models once at startup
    and serves tabular inference for any lat/lng coordinate.
    """

    def __init__(self):
        self._models = {
            "assam": {"ls": None, "fl": None, "ls_features": [], "fl_features": []},
            "kerala": {"ls": None, "fl": None, "ls_features": [], "fl_features": []}
        }
        self._explainers = {
            "assam": {"ls": None, "fl": None},
            "kerala": {"ls": None, "fl": None}
        }
        self._loaded = False
        self._load_models()

    def _load_models(self):
        try:
            import joblib
        except ImportError:
            logger.error("[ProactiveEngine] joblib not installed. Run: pip install joblib")
            return

        # Load Assam Models
        ls_path_assam = MODELS_DIR / "landslide_model.joblib"
        fl_path_assam = MODELS_DIR / "flood_model.joblib"
        ls_feat_assam = MODELS_DIR / "landslide_features.csv"
        fl_feat_assam = MODELS_DIR / "flood_features.csv"
        
        # Load Kerala Models
        ls_path_kerala = MODELS_DIR / "kerala_landslide_model.joblib"
        fl_path_kerala = MODELS_DIR / "kerala_flood_model.joblib"
        ls_feat_kerala = MODELS_DIR / "kerala_landslide_features.csv"
        fl_feat_kerala = MODELS_DIR / "kerala_flood_features.csv"

        missing = [p for p in [ls_path_assam, fl_path_assam, ls_feat_assam, fl_feat_assam] if not p.exists()]
        if missing:
            logger.warning(f"[ProactiveEngine] Missing Assam model files: {[str(m) for m in missing]}")
            logger.warning("[ProactiveEngine] Falling back to heuristic scoring for Assam.")
        else:
            try:
                self._models["assam"]["ls"] = joblib.load(ls_path_assam)
                self._models["assam"]["fl"] = joblib.load(fl_path_assam)
                self._models["assam"]["ls_features"] = pd.read_csv(ls_feat_assam)["Feature"].tolist()
                self._models["assam"]["fl_features"] = pd.read_csv(fl_feat_assam)["Feature"].tolist()
                
                try:
                    import shap
                    self._explainers["assam"]["ls"] = shap.TreeExplainer(self._models["assam"]["ls"])
                    self._explainers["assam"]["fl"] = shap.TreeExplainer(self._models["assam"]["fl"])
                except Exception as shap_err:
                    logger.warning(f"[ProactiveEngine] SHAP not available for Assam: {shap_err}")
            except Exception as e:
                logger.error(f"[ProactiveEngine] Failed to load Assam models: {e}")

        missing_kerala = [p for p in [ls_path_kerala, fl_path_kerala, ls_feat_kerala, fl_feat_kerala] if not p.exists()]
        if missing_kerala:
            logger.warning(f"[ProactiveEngine] Missing Kerala model files: {[str(m) for m in missing_kerala]}")
            logger.warning("[ProactiveEngine] Falling back to heuristic scoring for Kerala.")
        else:
            try:
                self._models["kerala"]["ls"] = joblib.load(ls_path_kerala)
                self._models["kerala"]["fl"] = joblib.load(fl_path_kerala)
                self._models["kerala"]["ls_features"] = pd.read_csv(ls_feat_kerala)["Feature"].tolist()
                self._models["kerala"]["fl_features"] = pd.read_csv(fl_feat_kerala)["Feature"].tolist()
                
                try:
                    import shap
                    self._explainers["kerala"]["ls"] = shap.TreeExplainer(self._models["kerala"]["ls"])
                    self._explainers["kerala"]["fl"] = shap.TreeExplainer(self._models["kerala"]["fl"])
                except Exception as shap_err:
                    logger.warning(f"[ProactiveEngine] SHAP not available for Kerala: {shap_err}")
            except Exception as e:
                logger.error(f"[ProactiveEngine] Failed to load Kerala models: {e}")

        self._loaded = True
        logger.info("[ProactiveEngine] Initialization complete.")

    def _classify_zone(self, landslide_score: float, flood_score: float) -> str:
        """
        Fuse landslide + flood scores into a single zone class.
        Takes the MAX risk across hazards (conservative — worst-case wins).
        """
        combined = max(landslide_score, flood_score)
        if combined >= ZONE_THRESHOLDS["RED"]:
            return "RED"
        elif combined >= ZONE_THRESHOLDS["ORANGE"]:
            return "ORANGE"
        elif combined >= ZONE_THRESHOLDS["YELLOW"]:
            return "YELLOW"
        return "GREEN"

    def _heuristic_score(self, features: dict) -> tuple[float, float]:
        """
        Physics-based fallback when joblib models are not loaded.
        Used during development / if model files are missing.
        """
        slope      = features.get("slope", 10.0)
        elevation  = features.get("elevation", 100.0)
        twi        = features.get("twi", 6.0)
        dist_river = features.get("dist_to_river_m", 5000.0)
        veg        = features.get("vegetation_proxy", 0.5)

        # Landslide heuristic: high slope + low vegetation + close to river = high risk
        ls = np.clip(
            (slope / 60.0) * 0.5 +
            (1.0 - veg) * 0.3 +
            (1.0 - min(dist_river, 10000) / 10000.0) * 0.2,
            0.0, 1.0
        )

        # Flood heuristic: low elevation + high TWI + close to river = high risk
        fl = np.clip(
            (1.0 - min(elevation, 200.0) / 200.0) * 0.5 +
            (min(twi, 15.0) / 15.0) * 0.3 +
            (1.0 - min(dist_river, 5000.0) / 5000.0) * 0.2,
            0.0, 1.0
        )

        return float(ls), float(fl)

    def _get_top_factors(self, model, feature_names: list[str], n: int = 3) -> list[dict]:
        """Extract top N important features from model for explainability."""
        try:
            importances = model.feature_importances_
            pairs = sorted(zip(feature_names, importances), key=lambda x: -x[1])
            return [{"feature": f, "importance": round(float(imp), 3)} for f, imp in pairs[:n]]
        except Exception:
            return []

    def _shap_explain(self, explainer, row_df: "pd.DataFrame", feature_names: list[str],
                      feature_vals: dict, n: int = 3) -> dict:
        """
        Generate per-sample SHAP explanation.
        Returns top-N factors with value, SHAP contribution, and a plain-English sentence.
        """
        try:
            shap_values = explainer.shap_values(row_df)
            # For binary classifiers shap_values may be [neg_class, pos_class]
            if isinstance(shap_values, list) and len(shap_values) == 2:
                sv = shap_values[1][0]   # positive class (risk=1) SHAP values
            else:
                sv = shap_values[0]      # regression / single output

            # Pair features with their SHAP contribution
            pairs = sorted(
                zip(feature_names, row_df.iloc[0].tolist(), sv),
                key=lambda x: abs(x[2]),
                reverse=True
            )
            top = pairs[:n]

            factors = [
                {
                    "feature":      f,
                    "value":        round(float(v), 3),
                    "shap_impact":  round(float(s), 4),
                    "direction":    "increases risk" if s > 0 else "reduces risk",
                }
                for f, v, s in top
            ]

            # Plain-English summary (top 2 factors)
            def _fmt(f, v, s):
                feat_labels = {
                    "dist_to_river_m": f"{v:.0f}m from river",
                    "twi":             f"TWI={v:.1f} (terrain wetness)",
                    "slope":           f"slope={v:.1f}°",
                    "elevation":       f"elevation={v:.0f}m",
                    "precip_daily_mm": f"{v:.1f}mm/day rainfall",
                    "vegetation_proxy":f"vegetation cover={v:.2f}",
                    "hand_proxy_m":    f"HAND={v:.1f}m above drainage",
                    "tri":             f"TRI={v:.1f}",
                }
                return feat_labels.get(f, f"{f}={v:.2f}")

            reason_parts = [_fmt(f, v, s) for f, v, s in top[:2]]
            direction = "HIGH" if top[0][2] > 0 else "MODERATE"
            plain = f"Risk is {direction} primarily due to {reason_parts[0]}"
            if len(reason_parts) > 1:
                plain += f" and {reason_parts[1]}"
            plain += "."

            return {"top_factors": factors, "plain_english": plain, "method": "shap_tree_explainer"}

        except Exception as e:
            logger.debug(f"[SHAP] Explanation failed: {e}")
            return {"top_factors": [], "plain_english": "Explanation unavailable.", "method": "shap_failed"}


    def score(self, features: dict, region: str = "assam") -> dict:
        """
        Score a single habitation.

        Args:
            features: dict with terrain/climate values. Any missing features
                      are filled with the training median (safe fallback).
            region: 'assam' or 'kerala' to route to specific models.

        Returns:
            dict with landslide_score, flood_score, zone_class, top_factors,
            model_used, scored_at
        """
        # ── Model Inference ───────────────────────────────────────────────────
        if self._loaded and region in self._models and self._models[region]["ls"] is not None:
            try:
                ls_model = self._models[region]["ls"]
                fl_model = self._models[region]["fl"]
                ls_features = self._models[region]["ls_features"]
                fl_features = self._models[region]["fl_features"]
                
                # Landslide inference
                ls_row = pd.DataFrame([{f: features.get(f, np.nan) for f in ls_features}])
                ls_row = ls_row.fillna(ls_row.median(numeric_only=True).fillna(0))
                ls_prob = float(ls_model.predict_proba(ls_row)[0][1])

                # Flood inference
                fl_row = pd.DataFrame([{f: features.get(f, np.nan) for f in fl_features}])
                fl_row = fl_row.fillna(fl_row.median(numeric_only=True).fillna(0))
                fl_prob = float(fl_model.predict_proba(fl_row)[0][1])

                top_ls = self._get_top_factors(ls_model, ls_features)
                top_fl = self._get_top_factors(fl_model, fl_features)
                model_used = f"xgboost_nasa_chirps_hydrorivers_{region}"

                # Per-sample SHAP explanation (Lv et al. 2022 methodology)
                ls_explainer = self._explainers[region]["ls"]
                fl_explainer = self._explainers[region]["fl"]
                
                if ls_explainer and fl_explainer:
                    ls_explanation = self._shap_explain(
                        ls_explainer, ls_row, ls_features, features
                    )
                    fl_explanation = self._shap_explain(
                        fl_explainer, fl_row, fl_features, features
                    )
                else:
                    ls_explanation = {"top_factors": top_ls, "plain_english": "Install 'shap' for detailed explanation.", "method": "feature_importance_fallback"}
                    fl_explanation = {"top_factors": top_fl, "plain_english": "Install 'shap' for detailed explanation.", "method": "feature_importance_fallback"}

            except Exception as e:
                logger.warning(f"[ProactiveEngine] Model inference failed, using heuristic: {e}")
                ls_prob, fl_prob = self._heuristic_score(features)
                top_ls, top_fl = [], []
                ls_explanation = fl_explanation = {"top_factors": [], "plain_english": "Model inference failed.", "method": "heuristic"}
                model_used = "heuristic_fallback"
        else:
            ls_prob, fl_prob = self._heuristic_score(features)
            top_ls, top_fl = [], []
            ls_explanation = fl_explanation = {"top_factors": [], "plain_english": "Models not loaded.", "method": "heuristic"}
            model_used = "heuristic_fallback"

        # ── Cascading Hazard SHAP Injection ──────────────────────────────────
        from core.settings import get_settings
        settings = get_settings()
        precip = features.get("precip_daily_mm", 0)
        slope = features.get("slope", 0)
        
        if precip > 50.0 and slope > 15.0:
            mult = settings.cascading_hazards.cascading_multiplier
            ls_prob = min(1.0, ls_prob * mult)
            cascade_msg = f"WARNING: Cascading Hazard detected. Extreme rainfall ({precip}mm) is causing rapid soil saturation, amplifying baseline slope instability by {mult}x."
            if isinstance(ls_explanation, dict) and "plain_english" in ls_explanation:
                ls_explanation["plain_english"] = f"{ls_explanation['plain_english']} {cascade_msg}"

        # ── Layer 2 Strategic Feedback Injection ─────────────────────────────
        forest_loss = features.get("forest_loss_pct_3yr", 0)
        if forest_loss > 15.0:
            ls_prob = min(1.0, ls_prob * 1.2) # 20% penalty for severe deforestation
            deforest_msg = f"WARNING: Layer 2 satellite tracking detected {forest_loss}% upstream forest cover loss over 3 years, significantly escalating baseline susceptibility due to root cohesion loss."
            if isinstance(ls_explanation, dict) and "plain_english" in ls_explanation:
                ls_explanation["plain_english"] = f"{ls_explanation['plain_english']} {deforest_msg}"
                
        zone = self._classify_zone(ls_prob, fl_prob)

        return {
            "landslide_score": round(ls_prob, 4),
            "flood_score":     round(fl_prob, 4),
            "zone_class":      zone,
            "combined_score":  round(max(ls_prob, fl_prob), 4),
            "top_landslide_factors": top_ls,
            "top_flood_factors":     top_fl,
            "landslide_explanation": ls_explanation,
            "flood_explanation":      fl_explanation,
            "model_used":      model_used,
            "scored_at":       datetime.now(timezone.utc).isoformat(),
        }

    def score_batch(self, habitations: list[dict], region: str = "assam") -> list[dict]:
        """
        Score a list of habitations efficiently.
        Each item in habitations must have 'id', 'lat', 'lng', and terrain features.
        Returns the same list with risk scores added to each item.
        """
        results = []
        for hab in habitations:
            score_result = self.score(hab, region=region)
            results.append({**hab, **score_result})
        return results


# Singleton — loaded once at import time
proactive_engine = ProactiveEngine()
