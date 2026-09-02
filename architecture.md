# architecture.md — System Architecture

## 1. One-line architecture

**IDENTIFY → ASSESS → PRIORITIZE → RELOCATE → RESPOND**
Multi-hazard mapping → vulnerability + site suitability → relocation priority ranking → carrying-capacity-constrained assignment → (extension) emergency response layer.

Supersedes the earlier SEE→ASSESS→ROUTE→CONNECT framing — same underlying models and infrastructure, restructured around the literal SIH26191 modules instead of a generic pipeline shape.

## 2. Full data/system flow

```
┌──────────────────────────────────────────────────────────┐
│  DATA LAYER                                                │
│  • Pre/Post Satellite Imagery (xView2)                    │
│  • Flood imagery (Faiza Karim dataset)                    │
│  • Landslide imagery (Roboflow SEECS + Kaggle Barman)      │
│  • OSM Road, Building, Land-Use Data                       │
│  • DEM Elevation Data                                       │
│  • Population density, habitation, relocation-site data      │
│    (sample/curated for demo — labeled as such, not live)     │
└───────────────────────┬────────────────────────────────────┘
                         ↓
┌──────────────────────────────────────────────────────────┐
│  IDENTIFY — Multi-Hazard Red Zone Engine (ONNX Runtime)       │
│  • Flood model (SegFormer, binary) → model_confidence          │
│  • Landslide model (ResNet50 U-Net, binary) → model_confidence  │
│  • Terrain/elevation overlay                                     │
│  • Red Zone Fusion (cop_builder._fuse_red_zones) → risk_score    │
│    + contributing_factors + color_tier                             │
│  NOTE: flood + landslide live here, not in RESPOND — they are      │
│  hazard-susceptibility inputs to Red Zone identification, not       │
│  post-disaster response outputs.                                     │
└───────────────────────┬────────────────────────────────────┘
                         ↓
┌──────────────────────────────────────────────────────────┐
│  ASSESS — Vulnerability + Site Suitability                    │
│  • Vulnerability Assessment (habitation side, NEW):            │
│    proximity to Red Zone + population + structural exposure     │
│    → risk_score per habitation                                    │
│  • Site Suitability (destination side, reuses evac-zone           │
│    ranking): structural integrity, open-space class, elevation,    │
│    accessibility, distance from hazard → recommendation_score       │
└───────────────────────┬────────────────────────────────────┘
                         ↓
┌──────────────────────────────────────────────────────────┐
│  RELOCATE — Carrying Capacity Assessment                       │
│  capacity_total = site_area_sqm × persons_per_sqm_standard       │
│  capacity_remaining = capacity_total − current_occupancy          │
│  Hard constraint feeding into the assignment below                 │
└───────────────────────┬────────────────────────────────────┘
                         ↓
┌──────────────────────────────────────────────────────────┐
│  PRIORITIZE — Relocation Priority Engine (THE DIFFERENTIATOR)  │
│  scipy.optimize.linear_sum_assignment (or greedy weighted          │
│  bipartite fallback), constrained by carrying capacity              │
│  Tiers via RelocationTierThresholds (settings.py, already            │
│  exists — engine needs to actually read it):                          │
│    immediate ≥0.70 · short-term 0.40–0.70 · medium-term <0.40           │
│  Output: recommendation_score + tier per habitation-site pair            │
│  STATUS: stub only — top build priority                                   │
└───────────────────────┬────────────────────────────────────┘
                         ↓
┌──────────────────────────────────────────────────────────┐
│  RESPOND — DISHA Extension Layer (not PS-core)                 │
│  • Damage severity (Siamese ResNet50, 3-class) → model_confidence │
│  • Hazard-aware routing (OSRM/GraphHopper) → route_suitability_score│
│    + hazard_exposure_avoided_pct + added_distance_m                 │
│    STATUS: stub only — straight line, hardcoded scores               │
│  • Communication-risk (bonus): tower-in-red-zone spatial check        │
│    → implemented                                                        │
└───────────────────────┬────────────────────────────────────┘
                         ↓
┌──────────────────────────────────────────────────────────┐
│  API LAYER — FastAPI (Python)                                │
│  /analyze — master orchestrator, runs IDENTIFY models in       │
│    parallel (asyncio.gather), fuses via cop_builder, returns     │
│    one GeoJSON FeatureCollection with layer_type per feature       │
│  /red-zones /evac-zones /relocation-plan /route /towers /feedback   │
│  demo_mode=true → pre-cached fixture, no GPU needed                    │
│  Every typed score: { score_type, score, last_updated, ...extras }      │
└───────────────────────┬────────────────────────────────────┘
                         ↓
┌──────────────────────────────────────────────────────────┐
│  DASHBOARD — cop.html (SDMA authority view)                    │
│  Unified map: Red Zones + vulnerability + candidate sites +       │
│  relocation plan + (RESPOND) routes/towers, layer toggles,          │
│  visible timestamps, override controls                                │
└───────────────────────┬────────────────────────────────────┘
                         ↓
┌──────────────────────────────────────────────────────────┐
│  SDMA / RESPONDER LAYER (human-in-the-loop)                    │
│  Reviews recommendation → accepts / edits / overrides            │
│  → correction stored via /feedback as verified operator input       │
└──────────────────────────────────────────────────────────┘
```

## 3. Tech Stack

| Layer | Tools | Notes |
|---|---|---|
| Model training | PyTorch, `segmentation_models_pytorch`, Kaggle GPU | Never trained locally |
| Model serving | ONNX Runtime (GPU + CPU fallback) | All 3 models loaded once at API startup, run in parallel via `asyncio.gather` in `pipeline.py` |
| Geospatial | GeoPandas, Rasterio/GDAL, OSMnx, Shapely | Shapely used for tower/red-zone spatial containment checks |
| Routing | OSRM or GraphHopper on a single-region OSM extract | Not yet wired — current `/route` is a placeholder straight line |
| Optimization | `scipy.optimize.linear_sum_assignment` | Not yet wired — current `/relocation-plan` is a hardcoded stub |
| Backend | Python 3.11, FastAPI, Pydantic v2 | `cop_builder.py` assembles the fused GeoJSON; `scoring_types.py` defines the four typed-score Pydantic models |
| Database | PostgreSQL + PostGIS | Target — currently using in-memory/fixture data for demo mode |
| Frontend | HTML/JS + Leaflet (`cop.html`) | Role-scoped web views recommended over native mobile app for MVP timeline reasons |
| Deployment (demo only) | Local + ngrok for sharing | Explicitly a demo convenience |

## 4. Folder Structure (matches actual repo)

```
/project-root
├── PRD.md / architecture.md / rules.md / phases.md
│
├── backend/
│   ├── main.py                      # FastAPI app, router registration
│   ├── api/
│   │   ├── analyze.py               # POST /analyze — master orchestrator (IDENTIFY→fusion)
│   │   ├── damage.py                # RESPOND — Siamese model endpoint
│   │   ├── flood.py                 # IDENTIFY — SegFormer endpoint
│   │   ├── landslide.py             # IDENTIFY — ResNet50 U-Net endpoint
│   │   ├── red_zones.py             # 🔴 needs reconciling with cop_builder output
│   │   ├── evac_zones.py            # ASSESS — site suitability
│   │   ├── relocation.py            # PRIORITIZE — 🔴 stub, top priority to build
│   │   ├── routes.py                # RESPOND — 🔴 stub, needs OSRM wiring
│   │   ├── towers.py                # RESPOND bonus — 🔴 needs reconciling with cop_builder
│   │   ├── settings_api.py          # AHP weights, tier thresholds — read/write/reset
│   │   ├── feedback.py              # human-in-the-loop corrections
│   │   └── ground_situation.py      # legacy naming — superseded by analyze.py
│   ├── core/
│   │   ├── pipeline.py              # runs 3 models in parallel, preprocesses images
│   │   ├── cop_builder.py           # fuses model outputs into one GeoJSON + summary
│   │   ├── inference.py             # ONNX Runtime engine wrapper
│   │   ├── mask_to_geojson.py       # converts model output masks to GeoJSON features
│   │   ├── osm_overlay.py           # cross-references damage with OSM buildings
│   │   ├── scoring_types.py         # ModelConfidence, RiskScore, RouteSuitabilityScore, RecommendationScore
│   │   ├── settings.py              # AppSettings, RiskFusionWeights, RelocationTierThresholds
│   │   ├── vulnerability.py         # 🔴 NEW — to be built, see PRD.md Section 6
│   │   ├── carrying_capacity.py     # 🔴 NEW — to be built
│   │   └── optimization.py          # 🔴 NEW — the relocation assignment engine
│   └── fixtures/
│       └── demo_result.json         # pre-cached COP for demo_mode=true
│
├── ml/
│   ├── damage/model_def.py          # reconstructed Siamese ResNet50 U-Net architecture
│   ├── landslide/model_def.py       # reconstructed monolith ResNet50 U-Net
│   └── export_onnx.py
│
├── models/                          # .onnx exports
│   ├── damage_model.onnx
│   ├── flood_model.onnx
│   └── landslide_model.onnx
│
├── dashboard/
│   ├── cop.html                     # SDMA authority view (primary demo surface)
│   └── index.html                   # debug/test console
│
└── data/
    └── generate_seed_data.py        # sample habitations/sites/population for demo
```

## 5. Key Architectural Rules (see rules.md for full detail)

- Flood and landslide models are IDENTIFY-layer, not RESPOND-layer — this affects which slide/module they get pitched under, don't regroup them back under "response" out of habit.
- Every typed score follows `scoring_types.py` exactly — no generic unlabeled confidence anywhere.
- `relocation.py`'s real logic (`optimization.py`) is the protected, top-priority module — nothing else gets built or polished ahead of it.
- `red_zones.py` and `towers.py` must be reconciled to read from whatever `/analyze` last computed — currently two disconnected sources of truth for the same concepts.
- Native mobile/WebSocket real-time layer is explicitly RESPOND-extension, deferred past MVP — see phases.md.
