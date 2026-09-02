"""
relocation.py — Relocation Priority Plan endpoint (PRIORITIZE layer)

GET  /relocation-plan/
  Returns the capacity-constrained, tier-sorted assignment of vulnerable
  habitations to safer relocation sites using scipy.optimize.linear_sum_assignment.

  Query params:
    region (optional): "assam" | "kedarnath" | any region key. Only affects
      which demo fixture loads if no habitation data has been POSTed. Defaults
      to "assam". Ignored if the caller has already submitted habitation data.

POST /relocation-plan/habitations
  Submit or update habitation data for the active region. Body: JSON array
  of habitation objects. Triggers an immediate re-run of the optimizer.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from core.optimization import compute_relocation_plan
from core.vulnerability import score_all_habitations
from core.analysis_state import get_last_cop, set_last_relocation, get_last_relocation
from core.settings import get_settings

router = APIRouter(prefix="/relocation-plan", tags=["PRIORITIZE — Relocation"])

# In-memory store for submitted habitation data (per region)
_submitted_habitations: dict[str, list] = {}


def _get_red_zones() -> list[dict]:
    """Pull red zone features from the last /analyze result for proximity scoring."""
    cop = get_last_cop()
    if not cop:
        return []
    return [
        f for f in cop.get("features", [])
        if f.get("properties", {}).get("layer_type") == "red_zone"
    ]


def _get_evac_sites() -> list[dict]:
    """Pull evac site features from the last /analyze result."""
    cop = get_last_cop()
    if not cop:
        return []
    sites = []
    for f in cop.get("features", []):
        if f.get("properties", {}).get("layer_type") == "evac_site":
            props = f.get("properties", {})
            geom = f.get("geometry", {})
            coords = geom.get("coordinates", [0, 0])
            sites.append({
                "id": props.get("id"),
                "name": props.get("name", "Unknown"),
                "lat": coords[1],
                "lng": coords[0],
                "capacity_persons": props.get("capacity_persons", 0),
                "capacity_remaining": props.get("capacity_persons", 0),  # live updates via field portal
                "recommendation_score": props.get("recommendation_score", 0.5),
            })
    return sites


@router.get("/")
def get_relocation_plan(region: str = Query(default="assam", description="Region key for demo fixture fallback")):
    """
    Returns the optimal, capacity-constrained relocation plan.

    - Uses habitations submitted via POST /relocation-plan/habitations if available.
    - Falls back to demo fixture (habitations_{region}.json) if not.
    - Evac sites come from the last /analyze COP output if available, else demo defaults.
    - Habitation vulnerability is scored live against current Red Zone positions.
    """
    try:
        settings = get_settings()
        tiers = settings.relocation_tiers
        red_zones = _get_red_zones()
        evac_sites = _get_evac_sites() or None  # None → optimizer uses its own defaults

        # Resolve habitation data
        raw_habs = _submitted_habitations.get(region)
        if not raw_habs:
            # Load demo fixture if nothing submitted so we can still score them dynamically
            from core.optimization import _load_demo_habitations
            raw_habs = _load_demo_habitations()

        # Score vulnerability against CURRENT red zones
        if raw_habs:
            scored = score_all_habitations(
                raw_habs, red_zones,
                immediate_threshold=tiers.immediate_threshold,
                short_term_threshold=tiers.short_term_threshold,
            )
            habitations = []
            for h, vr in zip(raw_habs, scored):
                habitations.append({**h, "vulnerability_score": vr.score})
        else:
            habitations = None

        plan = compute_relocation_plan(
            habitations=habitations,
            evac_sites=evac_sites,
            immediate_threshold=tiers.immediate_threshold,
            short_term_threshold=tiers.short_term_threshold,
            region=region,
        )

        result = plan.to_dict()
        set_last_relocation(result)
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/habitations")
def submit_habitations(habitations: list[dict], region: str = Query(default="assam")):
    """
    Submit habitation data for a region. Triggers an immediate optimizer run.
    
    Body: JSON array of habitation objects:
      [{id, name, lat, lng, population, structural_exposure?, historical_exposure?}, ...]
    """
    if not habitations:
        raise HTTPException(status_code=400, detail="Empty habitation list.")
    
    _submitted_habitations[region] = habitations
    
    # Re-run optimizer with new data
    try:
        settings = get_settings()
        tiers = settings.relocation_tiers
        red_zones = _get_red_zones()
        evac_sites = _get_evac_sites() or None

        scored = score_all_habitations(
            habitations, red_zones,
            immediate_threshold=tiers.immediate_threshold,
            short_term_threshold=tiers.short_term_threshold,
        )
        scored_habs = [{**h, "vulnerability_score": vr.score} for h, vr in zip(habitations, scored)]

        plan = compute_relocation_plan(
            habitations=scored_habs,
            evac_sites=evac_sites,
            immediate_threshold=tiers.immediate_threshold,
            short_term_threshold=tiers.short_term_threshold,
            region=region,
        )
        result = plan.to_dict()
        set_last_relocation(result)
        return {"status": "ok", "region": region, "habitations_received": len(habitations), "plan": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
