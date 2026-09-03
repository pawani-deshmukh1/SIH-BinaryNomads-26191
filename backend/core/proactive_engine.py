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

MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "backend" / "models"

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
        self._landslide_model = None
        self._flood_model = None
        self._landslide_features: list[str] = []
        self._flood_features: list[str] = []
        self._ls_explainer = None
        self._fl_explainer = None
        self._loaded = False
        self._load_models()

    def _load_models(self):
        try:
            import joblib
        except ImportError:
            logger.error("[ProactiveEngine] joblib not installed. Run: pip install joblib")
            return

        ls_path  = MODELS_DIR / "landslide_model.joblib"
        fl_path  = MODELS_DIR / "flood_model.joblib"
        ls_feat  = MODELS_DIR / "landslide_features.csv"
        fl_feat  = MODELS_DIR / "flood_features.csv"

        missing = [p for p in [ls_path, fl_path, ls_feat, fl_feat] if not p.exists()]
        if missing:
            logger.warning(f"[ProactiveEngine] Missing model files: {[str(m) for m in missing]}")
            logger.warning("[ProactiveEngine] Falling back to heuristic scoring.")
            return

        try:
            self._landslide_model = joblib.load(ls_path)
            self._flood_model     = joblib.load(fl_path)
            self._landslide_features = pd.read_csv(ls_feat)["Feature"].tolist()
            self._flood_features     = pd.read_csv(fl_feat)["Feature"].tolist()
            self._loaded = True
            logger.info(f"[ProactiveEngine] Loaded landslide model. Features: {self._landslide_features}")
            logger.info(f"[ProactiveEngine] Loaded flood model. Features: {self._flood_features}")

            # Initialise SHAP TreeExplainer (fast, tree-native)
            try:
                import shap
                self._ls_explainer = shap.TreeExplainer(self._landslide_model)
                self._fl_explainer = shap.TreeExplainer(self._flood_model)
                logger.info("[ProactiveEngine] SHAP TreeExplainer initialised for both models.")
            except Exception as shap_err:
                logger.warning(f"[ProactiveEngine] SHAP not available — using feature_importances_ fallback: {shap_err}")
                self._ls_explainer = None
                self._fl_explainer = None
        except Exception as e:
            logger.error(f"[ProactiveEngine] Failed to load models: {e}")

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


    def score(self, features: dict) -> dict:
        """
        Score a single habitation.

        Args:
            features: dict with terrain/climate values. Any missing features
                      are filled with the training median (safe fallback).

        Returns:
            dict with landslide_score, flood_score, zone_class, top_factors,
            model_used, scored_at
        """
        # ── Model Inference ───────────────────────────────────────────────────
        if self._loaded:
            try:
                # Landslide inference
                ls_row = pd.DataFrame([{f: features.get(f, np.nan) for f in self._landslide_features}])
                ls_row = ls_row.fillna(ls_row.median(numeric_only=True).fillna(0))
                ls_prob = float(self._landslide_model.predict_proba(ls_row)[0][1])

                # Flood inference
                fl_row = pd.DataFrame([{f: features.get(f, np.nan) for f in self._flood_features}])
                fl_row = fl_row.fillna(fl_row.median(numeric_only=True).fillna(0))
                fl_prob = float(self._flood_model.predict_proba(fl_row)[0][1])

                top_ls = self._get_top_factors(self._landslide_model, self._landslide_features)
                top_fl = self._get_top_factors(self._flood_model, self._flood_features)
                model_used = "xgboost_nasa_chirps_hydrorivers"

                # Per-sample SHAP explanation (Lv et al. 2022 methodology)
                if self._ls_explainer and self._fl_explainer:
                    ls_explanation = self._shap_explain(
                        self._ls_explainer, ls_row, self._landslide_features, features
                    )
                    fl_explanation = self._shap_explain(
                        self._fl_explainer, fl_row, self._flood_features, features
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

    def score_batch(self, habitations: list[dict]) -> list[dict]:
        """
        Score a list of habitations efficiently.
        Each item in habitations must have 'id', 'lat', 'lng', and terrain features.
        Returns the same list with risk scores added to each item.
        """
        results = []
        for hab in habitations:
            score_result = self.score(hab)
            results.append({**hab, **score_result})
        return results


# Singleton — loaded once at import time
proactive_engine = ProactiveEngine()
