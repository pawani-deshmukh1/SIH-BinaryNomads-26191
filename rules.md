# rules.md — Engineering Rules & AI-Assistance Boundaries

## 1. Libraries — use vs. avoid

| Area | Use | Avoid | Why |
|---|---|---|---|
| Model serving | `onnxruntime` / `onnxruntime-gpu` | Raw PyTorch inference in the API | Framework-agnostic, faster, smaller footprint, single interface for all 3 models |
| Backend | FastAPI + Pydantic v2 | Flask, Django REST | Async-friendly, auto-validation, matches team's existing familiarity |
| Geospatial | GeoPandas, Rasterio, OSMnx, Shapely | Hand-rolled geometry math | Don't reinvent spatial operations — bugs here are hard to catch visually |
| Routing | OSRM or GraphHopper on a local regional extract | Google Maps API / any paid routing API | Free-tier viability, and OSRM allows dynamic edge reweighting for hazard-avoidance, which a black-box API doesn't |
| Optimization | `scipy.optimize.linear_sum_assignment` | A hand-written greedy sort pretending to be "optimization" | The whole differentiator claim depends on this being real assignment logic, not a sorted list |
| Frontend state | React `useState`/`useReducer`, server as source of truth | `localStorage`/`sessionStorage` | Not reliably supported across target deployment surfaces; keep state server-side or in-memory |
| DB | PostgreSQL + PostGIS | SQLite, flat GeoJSON files as "the database" | Spatial indexing/queries at any real scale need PostGIS; flat files don't survive a live demo update loop |

## 2. Error Handling Conventions

- **Every model inference call is wrapped in try/except**, with a defined fallback (return `null` risk contribution + a `"model_unavailable"` flag in the response) — never let one model's failure 500 the whole `/red-zones` endpoint. The Red Zone fusion logic must degrade gracefully if one of the three models fails to load or errors on a tile.
- **Every external data dependency (OSM, routing engine) has a cached/local fallback for demo day.** Live API calls are not allowed to be the only path — pre-cache what the demo needs.
- **No silent failures.** Every caught exception is logged with enough context to debug (endpoint, input tile ID, model name) — not just `except: pass`.
- **GPU inference has a CPU fallback path**, tested on day 1, not discovered on demo day (see phases.md Phase 1).

## 3. Scoring Type Discipline (non-negotiable)

Do not use one generic "confidence" field anywhere in the codebase or API. Use exactly these four typed scores, matching what each computation actually is:

| Type | Used for | Comes from |
|---|---|---|
| `model_confidence` | Raw AI model outputs (damage, flood, landslide detection) | Model's own softmax/sigmoid probability |
| `risk_score` | Red Zone fusion, communication-risk estimate | Weighted combination of defined factors — always list the factors in the response |
| `route_suitability_score` | Routing engine outputs | Path-cost-derived, not a probability |
| `recommendation_score` | Evacuation-zone ranking, relocation assignment, relay placement | Optimization-objective-derived, not a probability |

Every API response includes `last_updated` (ISO timestamp). No exceptions — this is what makes the "live, re-optimizing system" claim true rather than decorative.

## 4. Claims Discipline

- Never say "predicts" for anything that is actually "estimates from a defined risk formula" — see PRD.md Section 2 framing. This applies to code comments, API field names, and docstrings too, not just the pitch deck — a judge who reads your code should see the same honesty as your slides.
- Never claim "real-time" for anything running on cached/pre-downloaded data. Label demo data paths as `sample`/`cached` in filenames and variable names, not `live`.
- The relocation-tiering output must always be presented as immediate/short-term/medium-term **candidates**, never as a final, unchallengeable decision.

## 5. AI-Assistance Boundaries (for using Claude/ChatGPT/Copilot on submodules)

Given quota constraints, AI assistance is scoped to **individual submodules**, not whole-system generation. Rules for what's in vs. out of bounds:

### In bounds — safe to hand to AI for a submodule
- Boilerplate: FastAPI route scaffolding, Pydantic schema definitions, ONNX Runtime loading wrapper, standard CRUD against PostGIS
- Individual, isolated utility functions (e.g., a GeoJSON-to-mask converter, a haversine distance helper)
- Frontend component scaffolding (a single React component, given a clear prop/data contract)
- Test-writing for a function whose expected behavior is already fully specified by a human
- Debugging a specific, pasted error with a specific, pasted code block

### Out of bounds — must be written/reviewed by a team member, not generated wholesale
- **The relocation/optimization engine's core assignment logic** (`optimization.py`) — this is the USP; if a judge asks "walk me through how this works," the answer needs to come from someone who actually built it, not someone reciting a generated docstring
- **The risk-fusion scoring formula** (`risk_scoring.py`) — the specific weights and factors need to be a team decision, defensible in Q&A, not an AI's arbitrary defaults
- **Any claim-bearing text** — PPT copy, PRD language, API-response field naming that implies confidence/certainty — must be reviewed against Section 4 of this document by a human before merging, since this is exactly where overclaiming crept in earlier in the project
- **Final integration/wiring between modules** — AI can write each piece in isolation, but a human should be the one connecting them, so the team actually understands the full data flow end-to-end

### Rule of thumb
If a judge could reasonably ask "why did you choose this approach/weight/threshold," and the honest answer would be "the AI decided," that piece is out of bounds for full AI generation. Use AI to accelerate the typing, not to make the decision.

## 6. Demo-Day Non-Negotiables

- All three model outputs on pre-cached tiles, verified working offline, before relying on any live inference
- ONNX output sanity-checked against PyTorch inference at least once per model (see phases.md)
- A rehearsed answer, verbatim, for: *"What if the AI is wrong?"* and *"How do you verify the risk estimate?"* (see PRD.md / prior conversation for exact phrasing)
