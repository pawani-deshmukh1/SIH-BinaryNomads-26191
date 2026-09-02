-- DISHA PostGIS Schema
-- SIH26191 -- Ministry of Home Affairs, Disaster Management
-- Run: psql -U disha_user -d disha -f schema.sql
-- Requires: PostGIS extension (pre-installed in postgis/postgis Docker image)

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- ── Habitations ───────────────────────────────────────────────────────────────
-- Vulnerable settlements needing potential relocation.
CREATE TABLE IF NOT EXISTS habitations (
    id                  SERIAL PRIMARY KEY,
    name                TEXT NOT NULL,
    geometry            GEOMETRY(Point, 4326) NOT NULL,
    population          INT,
    vulnerability_score FLOAT DEFAULT 0.5,  -- 0.0-1.0; team-defined composite
    tier                TEXT,               -- 'immediate' | 'short_term' | 'medium_term' | NULL
    notes               TEXT,
    last_updated        TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_habitations_geom ON habitations USING GIST (geometry);

-- ── Relocation Sites ──────────────────────────────────────────────────────────
-- Candidate safe relocation destinations.
CREATE TABLE IF NOT EXISTS relocation_sites (
    id                  SERIAL PRIMARY KEY,
    name                TEXT NOT NULL,
    geometry            GEOMETRY(Polygon, 4326) NOT NULL,
    area_sqm            FLOAT,
    capacity_persons    INT,               -- max persons this site can accommodate
    elevation_m         FLOAT,
    suitability_score   FLOAT,             -- 0.0-1.0; computed from elevation, distance, land use
    recommendation_score FLOAT,            -- updated by optimization engine
    notes               TEXT,
    last_updated        TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sites_geom ON relocation_sites USING GIST (geometry);

-- ── Red Zones ─────────────────────────────────────────────────────────────────
-- Risk-fused hazard polygons (output of risk_scoring.py).
CREATE TABLE IF NOT EXISTS red_zones (
    id                    SERIAL PRIMARY KEY,
    geometry              GEOMETRY(Polygon, 4326) NOT NULL,
    risk_score            FLOAT NOT NULL,          -- 0.0-1.0
    color_tier            TEXT NOT NULL,           -- 'red' | 'orange' | 'green'
    damage_confidence     FLOAT,                   -- model_confidence from damage model (NULL if unavailable)
    flood_confidence      FLOAT,                   -- model_confidence from flood model
    landslide_confidence  FLOAT,                   -- model_confidence from landslide model
    contributing_factors  JSONB,                   -- {"damage": {"weight": 0.4, "value": 0.8}, ...}
    source_tile_id        TEXT,                    -- reference to the input satellite tile
    last_updated          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_redzones_geom      ON red_zones USING GIST (geometry);
CREATE INDEX IF NOT EXISTS idx_redzones_tier       ON red_zones (color_tier);
CREATE INDEX IF NOT EXISTS idx_redzones_updated    ON red_zones (last_updated DESC);

-- ── Cell Towers ───────────────────────────────────────────────────────────────
-- OpenCellID tower locations with computed status.
-- Status logic: if tower centroid falls within a red_zone polygon -> 'potentially_offline'
CREATE TABLE IF NOT EXISTS cell_towers (
    id                      SERIAL PRIMARY KEY,
    geometry                GEOMETRY(Point, 4326) NOT NULL,
    operator                TEXT,
    technology              TEXT,           -- '4G' | '3G' | '2G'
    status                  TEXT DEFAULT 'unknown',   -- 'operational' | 'potentially_offline' | 'unknown'
    overlapping_red_zone_id INT REFERENCES red_zones(id) ON DELETE SET NULL,
    last_updated            TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_towers_geom ON cell_towers USING GIST (geometry);

-- ── Relocation Assignments ────────────────────────────────────────────────────
-- Output of the optimization engine: which habitation goes to which site.
CREATE TABLE IF NOT EXISTS relocation_assignments (
    id                   SERIAL PRIMARY KEY,
    habitation_id        INT NOT NULL REFERENCES habitations(id) ON DELETE CASCADE,
    site_id              INT NOT NULL REFERENCES relocation_sites(id) ON DELETE CASCADE,
    tier                 TEXT NOT NULL,     -- 'immediate' | 'short_term' | 'medium_term'
    recommendation_score FLOAT,             -- 0.0-1.0; from optimization engine
    assignment_cost      FLOAT,             -- raw cost value from linear_sum_assignment
    last_updated         TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (habitation_id)                  -- each habitation assigned to exactly one site
);

-- ── Operator Feedback (Human-in-the-Loop) ────────────────────────────────────
CREATE TABLE IF NOT EXISTS operator_feedback (
    id              SERIAL PRIMARY KEY,
    entity_type     TEXT NOT NULL,   -- 'red_zone' | 'assignment' | 'tower' | 'route'
    entity_id       INT NOT NULL,
    feedback_type   TEXT NOT NULL,   -- 'mark_resolved' | 'mark_incorrect' | 'override'
    corrected_value TEXT,            -- free-text correction or JSON
    operator_id     TEXT DEFAULT 'operator',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_feedback_entity ON operator_feedback (entity_type, entity_id);

-- ── Inference Cache ────────────────────────────────────────────────────────────
-- Caches model outputs per tile to avoid re-inference on same tile.
-- Demo day: pre-populate this table with Assam sample tile outputs.
CREATE TABLE IF NOT EXISTS inference_cache (
    id               SERIAL PRIMARY KEY,
    tile_id          TEXT NOT NULL,
    model_name       TEXT NOT NULL,   -- 'damage' | 'flood' | 'landslide'
    output_geojson   JSONB,           -- segmentation result as GeoJSON
    model_confidence FLOAT,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (tile_id, model_name)
);

-- ── Ground Situation Snapshots (F11) ──────────────────────────────────────────
-- Timestamped full-picture snapshots for the Ground Situation Reconstruction feature.
CREATE TABLE IF NOT EXISTS ground_situation_snapshots (
    id              SERIAL PRIMARY KEY,
    snapshot_geojson JSONB NOT NULL,  -- complete GeoJSON FeatureCollection
    summary         JSONB NOT NULL,   -- {total_habitations, immediate_count, towers_offline, ...}
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
