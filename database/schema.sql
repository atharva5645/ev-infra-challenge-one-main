-- EV Infra Map India prototype schema.
-- Coordinates are stored as longitude/latitude numeric pairs so this file runs
-- on PostgreSQL before PostGIS is installed. See README.md for spatial setup.

CREATE TABLE states (
    state_code       VARCHAR(8) PRIMARY KEY,
    state_name       VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE districts (
    district_code    VARCHAR(16) PRIMARY KEY,
    state_code       VARCHAR(8) NOT NULL REFERENCES states(state_code),
    district_name    VARCHAR(120) NOT NULL,
    UNIQUE (state_code, district_name)
);

CREATE TABLE charger_source_records (
    source_record_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_name      VARCHAR(120) NOT NULL,
    source_record_key VARCHAR(160) NOT NULL,
    station_name     VARCHAR(200) NOT NULL,
    district_code    VARCHAR(16) REFERENCES districts(district_code),
    latitude         NUMERIC(9,6),
    longitude        NUMERIC(9,6),
    charger_type     VARCHAR(40),
    recorded_at      TIMESTAMPTZ,
    raw_attributes   JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (source_name, source_record_key),
    CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
    CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180)
);

CREATE TABLE chargers_unified (
    charger_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    station_name     VARCHAR(200) NOT NULL,
    district_code    VARCHAR(16) REFERENCES districts(district_code),
    latitude         NUMERIC(9,6) NOT NULL,
    longitude        NUMERIC(9,6) NOT NULL,
    charger_type     VARCHAR(40) NOT NULL,
    source_name      VARCHAR(120) NOT NULL,
    source_record_id BIGINT REFERENCES charger_source_records(source_record_id) ON DELETE SET NULL,
    confidence_score NUMERIC(4,3) NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (latitude BETWEEN -90 AND 90),
    CHECK (longitude BETWEEN -180 AND 180),
    CHECK (confidence_score BETWEEN 0 AND 1)
);

CREATE TABLE ev_registrations (
    registration_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    district_code   VARCHAR(16) NOT NULL REFERENCES districts(district_code),
    vehicle_class   VARCHAR(60) NOT NULL,
    reporting_period DATE NOT NULL,
    ev_count        INTEGER NOT NULL CHECK (ev_count >= 0),
    source_name     VARCHAR(120) NOT NULL,
    UNIQUE (district_code, vehicle_class, reporting_period)
);

CREATE TABLE hex_metrics (
    hex_metric_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cell_id         VARCHAR(32) NOT NULL,
    reporting_period DATE NOT NULL,
    ev_demand       INTEGER NOT NULL CHECK (ev_demand >= 0),
    charger_count   INTEGER NOT NULL CHECK (charger_count >= 0),
    coverage        NUMERIC(6,5) NOT NULL CHECK (coverage BETWEEN 0 AND 1),
    gap_score       NUMERIC(6,5) NOT NULL CHECK (gap_score BETWEEN 0 AND 1),
    UNIQUE (cell_id, reporting_period)
);

CREATE TABLE candidate_sites (
    candidate_site_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    site_name         VARCHAR(200) NOT NULL,
    district_code     VARCHAR(16) NOT NULL REFERENCES districts(district_code),
    latitude          NUMERIC(9,6) NOT NULL,
    longitude         NUMERIC(9,6) NOT NULL,
    estimated_cost_inr NUMERIC(14,2) NOT NULL CHECK (estimated_cost_inr >= 0),
    suitability_score NUMERIC(6,5) NOT NULL CHECK (suitability_score BETWEEN 0 AND 1),
    notes             TEXT,
    CHECK (latitude BETWEEN -90 AND 90),
    CHECK (longitude BETWEEN -180 AND 180)
);

CREATE TABLE assumptions (
    assumption_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    parameter_name  VARCHAR(120) NOT NULL UNIQUE,
    parameter_value NUMERIC(16,5) NOT NULL,
    units           VARCHAR(60) NOT NULL,
    description     TEXT NOT NULL,
    source           VARCHAR(240) NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE optimizer_runs (
    optimizer_run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_name         VARCHAR(160) NOT NULL,
    budget_inr       NUMERIC(16,2) NOT NULL CHECK (budget_inr >= 0),
    objective        VARCHAR(240) NOT NULL,
    recommended_sites JSONB NOT NULL DEFAULT '[]'::jsonb,
    estimated_new_chargers INTEGER NOT NULL CHECK (estimated_new_chargers >= 0),
    estimated_coverage_gain NUMERIC(6,5) NOT NULL CHECK (estimated_coverage_gain BETWEEN 0 AND 1),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (jsonb_typeof(recommended_sites) = 'array')
);

-- Indexes for common geography, source lookup, period and score filtering.
CREATE INDEX idx_districts_state_code ON districts(state_code);
CREATE INDEX idx_source_records_district ON charger_source_records(district_code);
CREATE INDEX idx_chargers_district ON chargers_unified(district_code);
CREATE INDEX idx_chargers_coordinates ON chargers_unified(latitude, longitude);
CREATE INDEX idx_ev_registrations_district_period ON ev_registrations(district_code, reporting_period);
CREATE INDEX idx_hex_metrics_period_gap ON hex_metrics(reporting_period, gap_score DESC);
CREATE INDEX idx_candidate_sites_district_score ON candidate_sites(district_code, suitability_score DESC);
CREATE INDEX idx_optimizer_runs_created_at ON optimizer_runs(created_at DESC);
