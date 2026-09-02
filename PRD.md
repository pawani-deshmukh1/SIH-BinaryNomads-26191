# PRD.md — Product Requirements Document

## Project
**DISHA — AI-Driven Red Zone, Carrying Capacity & Relocation Decision Support Platform**
SIH 2026 · SIH26191 · Ministry of Home Affairs (NDRF / DM Division) · Theme: Disaster Management

---

## 1. Problem Statement (official)

> *Intelligent Identification of Hazard-Based Red Zones, Carrying Capacity Assessment, and Immediate Relocation Needs for Vulnerable Habitations.*

Expected solution: an AI-driven GIS platform that maps and updates hazard-based Red Zones, assesses suitability and carrying capacity of safer relocation sites, prioritizes vulnerable habitations for immediate/short-term/medium-term relocation, and provides actionable insights to State Disaster Management Authorities (SDMAs).

## 2. Positioning (revised)

**SIH26191 is the core problem. DISHA is the platform that answers it.** DISHA's existing GIS + satellite-AI foundation (built pre-pivot) is genuinely useful infrastructure — but it does not, by itself, solve SIH26191. Five specific modules named in the PS (Red Zone ID, vulnerability assessment, site suitability, carrying capacity, relocation prioritization) had to be newly defined and built on top of that foundation. The honest framing, used consistently in the pitch and in code comments:

> *"Our existing DISHA architecture provides the foundation — satellite hazard detection, GIS processing, typed-score decision support. We built the SIH26191-specific modules on top of it, not as something it already did."*

This is still a **decision-support tool, not an autonomous decision-maker.** Every output carries a typed score (`model_confidence` / `risk_score` / `route_suitability_score` / `recommendation_score`) and a timestamp. A human SDMA operator reviews, confirms, or overrides every recommendation.

## 3. Target Users

| User | What they need from the system |
|---|---|
| **SDMA / DDMA operator** | Live Red Zone map, ranked relocation sites, a prioritized immediate/short-term/medium-term habitation list, override controls |
| **District administration** | Exportable summary for logistics planning |
| **NDRF/SDRF field responder** | (RESPOND extension) hazard-aware routes, ground-truth reporting |

## 4. Core Flow (revised)

**IDENTIFY → ASSESS → PRIORITIZE → RELOCATE → RESPOND**

This replaces the earlier SEE→ASSESS→ROUTE→CONNECT framing. The first four stages are the literal PS ask and are MVP-critical. RESPOND is DISHA's own extension layer — real, working, but explicitly secondary in the pitch.

### 1️⃣ IDENTIFY — Multi-Hazard Red Zone Mapping
Satellite/GIS-based hazard detection identifies which areas are unsafe for permanent habitation. **This is where the flood and landslide models belong** — hazard susceptibility mapping is literally how a Red Zone gets identified in the first place, not a post-disaster response feature. (Correction from the earlier draft, which had incorrectly grouped all three trained models under "response.")

### 2️⃣ ASSESS — Vulnerability + Alternative Site Suitability
Two sub-modules:
- **Vulnerability Assessment** (habitation side): scores each habitation on exposure, not just presence in a Red Zone
- **Site Suitability** (destination side): evaluates candidate relocation sites — this reuses and extends the existing evacuation-zone ranking logic

### 3️⃣ PRIORITIZE — Relocation Priority Engine
Ranks/tiers habitations into immediate / short-term / medium-term based on vulnerability score and site availability. This is the actual optimization/assignment engine — the core differentiator, and currently the least-built piece (see Section 7).

### 4️⃣ RELOCATE — Carrying Capacity Assessment
Computes how many people a candidate site can actually, safely accommodate, and factors that hard constraint into the assignment in step 3.

### 5️⃣ RESPOND — DISHA Extension Layer (not PS-core, shown as "we went further")
- Building damage-severity detection (Siamese ResNet50) — this one genuinely belongs here, since it's post-disaster triage, not proactive Red Zone identification
- Hazard-aware routing
- Communication-risk mapping (bonus layer)

## 5. Non-Goals (MVP)

- Live telecom network monitoring — communication risk is a modeled estimate, RESPOND-layer only
- Real-time hydrological/rainfall-driven flood forecasting — flood layer uses current observed extent, not a forecast
- Native mobile app / live vehicle-convoy tracking / WebSocket geofencing — genuinely valuable, but this is RESPOND-extension territory, explicitly deferred past MVP (see phases.md)
- Physical relay/drone hardware deployment

## 6. Module Definitions (concrete — not box-diagram labels)

Each of these needs a defined formula before it goes in the PPT as "done." This section exists specifically so none of them stay vague through to demo day.

### Multi-Hazard Red Zone Engine (IDENTIFY)
Inputs: damage severity map, flood extent map, landslide extent map, terrain/elevation, population density.
Output: `risk_score` (0–1) + `color_tier` (🔴/🟠/🟢) per zone, with `contributing_factors` breakdown (already implemented in `scoring_types.RiskScore` and `cop_builder._fuse_red_zones` — formula needs tightening, see rules.md).

### Vulnerability Assessment (ASSESS — habitation side)
Inputs per habitation: proximity to nearest identified Red Zone, population count/density, structural exposure (proxy: OSM building type/age tags where available, else regional default), historical disaster exposure count for that habitation (if data available, else omitted rather than fabricated).
Output: `risk_score` per habitation — this is the origin-side score that feeds the priority ranking in step 3. **Not the same score as the Red Zone risk score** — a habitation's vulnerability also depends on things the zone-level fusion doesn't capture (population, structure type).

### Alternative Site Suitability (ASSESS — destination side)
Extends the existing evac-zone ranking: structural integrity, open-space classification, elevation, road accessibility, distance from nearest Red Zone.
Output: `recommendation_score` per candidate site (already implemented as evac-zone ranking logic — needs to be explicitly reused here, not rebuilt).

### Carrying Capacity Assessment (RELOCATE)
Formula: `capacity_total = site_area_sqm × persons_per_sqm_standard` (use a documented humanitarian-shelter density standard, cite it), `capacity_remaining = capacity_total − current_occupancy`.
Output: a plain number (persons), not a 0–1 score — paired with the site's `recommendation_score` for ranking, but capacity itself is a hard constraint, not a soft preference.

### Relocation Priority Engine (PRIORITIZE — the actual differentiator)
Capacity-constrained assignment: given N vulnerable habitations (with vulnerability scores) and M candidate sites (with suitability scores and hard capacity limits), solve for the assignment that minimizes total expected harm — `scipy.optimize.linear_sum_assignment` or a greedy weighted-bipartite fallback.
Tiering: assignment scores/thresholds map to immediate (≥0.70) / short-term (0.40–0.70) / medium-term (<0.40) — thresholds already exist as configurable settings (`RelocationTierThresholds`), just need to be read by the actual engine instead of hardcoded.
Output: `recommendation_score` per assignment + tier label.
**Status: stubbed, not implemented — see Section 7. This is the top build priority.**

## 7. Current Build Status (be honest here — this is what a judge will ask about)

| Module | Status |
|---|---|
| Flood detection (IDENTIFY) | ✅ Trained, validated — 92.82% accuracy, 86.04% mIoU |
| Landslide detection (IDENTIFY) | ✅ Trained, validated — strong on solid hazard regions, documented weaker recall on thin/branching streaks |
| Damage detection (RESPOND) | ✅ Trained, fine-tuned, visually validated including rare class |
| Red Zone fusion (IDENTIFY) | 🟡 Implemented, formula needs tightening — some contributions currently added regardless of spatial overlap |
| Vulnerability Assessment (ASSESS) | 🔴 Not implemented — formula defined above, needs building |
| Site Suitability (ASSESS) | 🟡 Existing evac-zone ranking logic covers this — needs to be explicitly reused/renamed, not rebuilt from scratch |
| Carrying Capacity (RELOCATE) | 🔴 Not implemented — formula defined above |
| Relocation Priority Engine (PRIORITIZE) | 🔴 Stub only — returns one hardcoded example. **Top priority.** |
| Hazard-aware routing (RESPOND) | 🔴 Stub only — currently a straight line with hardcoded scores regardless of input |
| Communication risk (RESPOND, bonus) | 🟡 Tower-in-red-zone spatial check implemented |

## 8. Success Criteria / Validation Targets

| Component | Target |
|---|---|
| Flood/landslide detection | Achieved — see above |
| Damage detection | 0.75–0.85 F1 (matches published xView2 benchmark) — achieved |
| Relocation engine | Demonstrate optimal-vs-naive assignment under a constrained capacity scenario, live |
| Routing | Hazard-aware route vs. shortest path — report added distance & hazard exposure avoided (fields already exist in `RouteSuitabilityScore`, engine doesn't yet) |

## 9. Judge-Facing One-Liner

> *"The PS asks us to identify who's at risk, find them somewhere safer, check that place can actually hold them, and decide who moves first. That's exactly what these five modules do — and we built a working emergency-response layer on top, because identifying the risk is only half the job."*
