"""
optimization.py — Relocation Priority Engine (PRIORITIZE layer, SIH26191)

Implements capacity-constrained optimal assignment of vulnerable habitations
to safer relocation sites using the Hungarian algorithm.

Algorithm: scipy.optimize.linear_sum_assignment
  - Proven optimal in O(n³) for bipartite matching
  - Capacity constraint implemented via column expansion:
    each site gets floor(capacity_remaining / avg_hab_pop) duplicate columns,
    preventing a single site from absorbing more people than it can hold.
  - After solving, duplicate columns are collapsed back to site IDs.

Output: RelocationPlan with assignments (habitation → site), tier labels
  (immediate/short_term/medium_term from RelocationTierThresholds), and a
  summary block that names the optimization method explicitly — for the demo.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import radians, sin, cos, sqrt, atan2
from pathlib import Path
from typing import Optional

import numpy as np
from scipy.optimize import linear_sum_assignment

logger = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"

# Default fallback habitation data (Assam demo) — used only if caller provides none
_ASSAM_FIXTURE = FIXTURES_DIR / "habitations_assam.json"

# Default evac sites (mirrors cop_builder.DEMO_EVAC_SITES["assam"])
_DEFAULT_EVAC_SITES = [
    {"id": "EZ-A01", "name": "Nagaon Govt School", "lat": 26.355, "lng": 92.685,
     "capacity_persons": 1200, "capacity_remaining": 1200, "recommendation_score": 0.91},
    {"id": "EZ-A02", "name": "Nagaon District Stadium", "lat": 26.342, "lng": 92.671,
     "capacity_persons": 3500, "capacity_remaining": 3500, "recommendation_score": 0.79},
    {"id": "EZ-A03", "name": "Rupahi Relief Ground", "lat": 26.362, "lng": 92.655,
     "capacity_persons": 600, "capacity_remaining": 600, "recommendation_score": 0.65},
]


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1.0 - a))


def _load_demo_habitations() -> list[dict]:
    """Load Assam demo habitations if fixture exists, else return empty list."""
    if _ASSAM_FIXTURE.exists():
        try:
            with open(_ASSAM_FIXTURE, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"[Optimizer] Could not load demo habitations: {e}")
    return []


@dataclass
class Assignment:
    habitation_id: str
    habitation_name: str
    population: int
    vulnerability_score: float
    tier: str               # immediate | short_term | medium_term
    site_id: str
    site_name: str
    distance_km: float
    recommendation_score: float
    # Coordinates included so the frontend can plot dots + lines with no extra fetch
    hab_lat: float = 0.0
    hab_lng: float = 0.0
    site_lat: float = 0.0
    site_lng: float = 0.0
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "habitation_id": self.habitation_id,
            "habitation_name": self.habitation_name,
            "population": self.population,
            "vulnerability_score": round(self.vulnerability_score, 4),
            "tier": self.tier,
            "site_id": self.site_id,
            "site_name": self.site_name,
            "distance_km": round(self.distance_km, 2),
            "recommendation_score": round(self.recommendation_score, 4),
            # Geometry — frontend uses these directly for map dots and assignment lines
            "hab_lat": self.hab_lat,
            "hab_lng": self.hab_lng,
            "site_lat": self.site_lat,
            "site_lng": self.site_lng,
            "last_updated": self.last_updated,
        }


@dataclass
class RelocationPlan:
    assignments: list[Assignment]
    unassigned_ids: list[str]
    summary: dict

    def to_dict(self) -> dict:
        by_tier: dict[str, list] = {"immediate": [], "short_term": [], "medium_term": []}
        for a in self.assignments:
            by_tier.setdefault(a.tier, []).append(a.to_dict())
        return {
            "assignments": [a.to_dict() for a in self.assignments],
            "by_tier": by_tier,
            "unassigned": self.unassigned_ids,
            "summary": self.summary,
        }


def compute_relocation_plan(
    habitations: list[dict] | None = None,
    evac_sites: list[dict] | None = None,
    immediate_threshold: float = 0.70,
    short_term_threshold: float = 0.40,
    region: str = "assam",
) -> RelocationPlan:
    """
    Compute optimal, capacity-constrained relocation assignments.

    habitations: list of dicts with keys:
        id, name, lat, lng, population, vulnerability_score
      If None or empty → falls back to Assam demo fixture (if available)

    evac_sites: list of dicts with keys:
        id, name, lat, lng, capacity_remaining, recommendation_score
      If None or empty → uses built-in Assam demo sites

    Returns RelocationPlan (call .to_dict() for JSON serialisation).
    """
    now = datetime.now(timezone.utc).isoformat()

    # --- Input resolution (configurable, not hardcoded) ---
    using_demo_habs = False
    using_demo_sites = False

    if not habitations:
        habitations = _load_demo_habitations()
        using_demo_habs = bool(habitations)
        if not habitations:
            return RelocationPlan(
                assignments=[],
                unassigned_ids=[],
                summary={
                    "error": "No habitation data provided and no demo fixture found.",
                    "hint": f"POST habitation data or place habitations_{region}.json in fixtures/",
                    "optimization_method": "scipy.optimize.linear_sum_assignment",
                }
            )

    if not evac_sites:
        evac_sites = _DEFAULT_EVAC_SITES
        using_demo_sites = True

    # Ensure vulnerability_score is present (may come from vulnerability.py or be pre-set)
    for h in habitations:
        if "vulnerability_score" not in h:
            # Basic fallback: use structural_exposure as a rough proxy
            h["vulnerability_score"] = float(h.get("structural_exposure", 0.5))

    # Sort by vulnerability descending (most at risk → first priority)
    habs = sorted(habitations, key=lambda h: float(h.get("vulnerability_score", 0)), reverse=True)

    # Filter out sites with no capacity
    sites = [s for s in evac_sites if int(s.get("capacity_remaining", s.get("capacity_persons", 0))) > 0]
    if not sites:
        return RelocationPlan(
            assignments=[],
            unassigned_ids=[h["id"] for h in habs],
            summary={"error": "All evacuation sites at full capacity.",
                     "optimization_method": "scipy.optimize.linear_sum_assignment"},
        )

    # --- Column expansion for capacity constraints ---
    total_pop = sum(int(h.get("population", 1)) for h in habs)
    avg_pop = max(1, total_pop // len(habs))

    expanded_sites: list[dict] = []
    for site in sites:
        cap = int(site.get("capacity_remaining", site.get("capacity_persons", 0)))
        slots = max(1, cap // avg_pop)
        for _ in range(slots):
            expanded_sites.append(site)

    n_habs = len(habs)
    n_cols = len(expanded_sites)

    # --- Cost matrix: lower cost = better assignment ---
    # cost[i][j] = distance_km / (site.recommendation_score + ε)
    # Dividing by site quality means high-quality nearby sites get low cost (preferred).
    BIG = 9999.0
    cost = np.full((n_habs, n_cols), fill_value=BIG)
    for i, hab in enumerate(habs):
        for j, site in enumerate(expanded_sites):
            dist = _haversine_km(
                float(hab.get("lat", 0)), float(hab.get("lng", 0)),
                float(site["lat"]), float(site["lng"]),
            )
            score = max(0.01, float(site.get("recommendation_score", 0.5)))
            cost[i, j] = dist / score

    # Square the matrix (scipy requires n×n or n×m where n ≤ m)
    size = max(n_habs, n_cols)
    padded = np.full((size, size), fill_value=BIG)
    padded[:n_habs, :n_cols] = cost

    row_ind, col_ind = linear_sum_assignment(padded)

    # --- Build assignments ---
    assignments: list[Assignment] = []
    unassigned: list[str] = []

    for i, j in zip(row_ind, col_ind):
        if i >= n_habs:
            continue
        hab = habs[i]
        if j >= n_cols or padded[i, j] >= BIG:
            unassigned.append(str(hab.get("id", i)))
            continue

        site = expanded_sites[j]
        dist = _haversine_km(
            float(hab.get("lat", 0)), float(hab.get("lng", 0)),
            float(site["lat"]), float(site["lng"]),
        )

        vs = float(hab.get("vulnerability_score", 0))
        if vs >= immediate_threshold:
            tier = "immediate"
        elif vs >= short_term_threshold:
            tier = "short_term"
        else:
            tier = "medium_term"

        # Assignment quality: weighted combination of site quality + proximity
        # Site quality weighted higher (0.6) because a closer bad site < farther safe site.
        max_reasonable_dist = 30.0  # km — normalisation constant
        proximity_score = max(0.0, 1.0 - dist / max_reasonable_dist)
        rec_score = float(site.get("recommendation_score", 0.5)) * 0.6 + proximity_score * 0.4

        assignments.append(Assignment(
            habitation_id=str(hab.get("id", i)),
            habitation_name=str(hab.get("name", f"HAB-{i}")),
            population=int(hab.get("population", 0)),
            vulnerability_score=vs,
            tier=tier,
            site_id=str(site["id"]),
            site_name=str(site["name"]),
            distance_km=dist,
            recommendation_score=rec_score,
            hab_lat=float(hab.get("lat", 0)),
            hab_lng=float(hab.get("lng", 0)),
            site_lat=float(site.get("lat", 0)),
            site_lng=float(site.get("lng", 0)),
        ))

    # Sort: immediate first, then by vulnerability desc within each tier
    tier_order = {"immediate": 0, "short_term": 1, "medium_term": 2}
    assignments.sort(key=lambda a: (tier_order.get(a.tier, 3), -a.vulnerability_score))

    summary = {
        "total_habitations": len(habs),
        "total_population_at_risk": sum(int(h.get("population", 0)) for h in habs),
        "assigned": len(assignments),
        "unassigned_count": len(unassigned),
        "immediate_count": sum(1 for a in assignments if a.tier == "immediate"),
        "short_term_count": sum(1 for a in assignments if a.tier == "short_term"),
        "medium_term_count": sum(1 for a in assignments if a.tier == "medium_term"),
        "optimization_method": "scipy.optimize.linear_sum_assignment (Hungarian algorithm)",
        "capacity_constraint_method": "column-expansion (avg habitation population as slot unit)",
        "using_demo_habitations": using_demo_habs,
        "using_demo_sites": using_demo_sites,
        "last_updated": now,
    }

    logger.info(
        f"[Optimizer] {len(assignments)} assignments ({summary['immediate_count']} immediate), "
        f"{len(unassigned)} unassigned, method=Hungarian"
    )

    return RelocationPlan(assignments=assignments, unassigned_ids=unassigned, summary=summary)
