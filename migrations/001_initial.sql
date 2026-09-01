CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE source_registry (
  source_id VARCHAR(32) PRIMARY KEY,
  source_name TEXT NOT NULL UNIQUE,
  source_type TEXT NOT NULL CHECK (source_type IN ('AIRLINE','OTA','GDS','REGULATORY','OTHER')),
  access_method TEXT NOT NULL CHECK (access_method IN ('OFFICIAL_API','PARTNER_API','PERMITTED_SCRAPE','MANUAL','FILE_FEED','UNKNOWN')),
  authorization_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (authorization_status IN ('PENDING','APPROVED','REJECTED','EXPIRED')),
  tos_status TEXT NOT NULL DEFAULT 'UNKNOWN' CHECK (tos_status IN ('UNKNOWN','ALLOWED','RESTRICTED','PROHIBITED')),
  robots_status TEXT NOT NULL DEFAULT 'UNKNOWN' CHECK (robots_status IN ('UNKNOWN','ALLOWED','DISALLOWED','MIXED')),
  active BOOLEAN NOT NULL DEFAULT TRUE,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE routes (
  route_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  origin_iata CHAR(3) NOT NULL CHECK (origin_iata = upper(origin_iata)),
  destination_iata CHAR(3) NOT NULL CHECK (destination_iata = upper(destination_iata)),
  domestic BOOLEAN NOT NULL DEFAULT TRUE,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE(origin_iata, destination_iata)
);

CREATE TABLE route_weights (
  route_weight_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  route_id UUID NOT NULL REFERENCES routes(route_id),
  basket_version TEXT NOT NULL,
  weight NUMERIC(18,10) NOT NULL CHECK (weight >= 0),
  effective_from DATE NOT NULL,
  effective_to DATE,
  methodology_version TEXT NOT NULL,
  UNIQUE(route_id, basket_version, effective_from)
);

CREATE TABLE collection_runs (
  run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id VARCHAR(32) NOT NULL REFERENCES source_registry(source_id),
  started_at TIMESTAMPTZ NOT NULL,
  completed_at TIMESTAMPTZ,
  status TEXT NOT NULL CHECK (status IN ('RUNNING','SUCCEEDED','PARTIAL','FAILED')),
  records_seen INTEGER NOT NULL DEFAULT 0 CHECK (records_seen >= 0),
  records_accepted INTEGER NOT NULL DEFAULT 0 CHECK (records_accepted >= 0),
  records_rejected INTEGER NOT NULL DEFAULT 0 CHECK (records_rejected >= 0),
  error_code TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE raw_quotes (
  raw_quote_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id UUID NOT NULL REFERENCES collection_runs(run_id),
  captured_at TIMESTAMPTZ NOT NULL,
  source_record_key TEXT,
  payload JSONB NOT NULL,
  payload_sha256 CHAR(64) NOT NULL,
  content_type TEXT,
  UNIQUE(run_id, payload_sha256)
);

CREATE TABLE flights (
  flight_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  route_id UUID NOT NULL REFERENCES routes(route_id),
  marketing_carrier_code VARCHAR(3),
  flight_number TEXT,
  departure_at TIMESTAMPTZ NOT NULL,
  arrival_at TIMESTAMPTZ,
  cabin_class TEXT NOT NULL CHECK (cabin_class IN ('ECONOMY','PREMIUM_ECONOMY','BUSINESS','FIRST','UNKNOWN')),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE observations (
  observation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  raw_quote_id UUID NOT NULL REFERENCES raw_quotes(raw_quote_id),
  route_id UUID NOT NULL REFERENCES routes(route_id),
  flight_id UUID REFERENCES flights(flight_id),
  source_id VARCHAR(32) NOT NULL REFERENCES source_registry(source_id),
  collection_timestamp TIMESTAMPTZ NOT NULL,
  departure_at TIMESTAMPTZ NOT NULL,
  advance_purchase_days INTEGER NOT NULL CHECK (advance_purchase_days >= 0),
  advance_window TEXT NOT NULL CHECK (advance_window IN ('T+1','T+7','T+15','T+30','T+45','OTHER')),
  currency CHAR(3) NOT NULL,
  base_fare_minor BIGINT CHECK (base_fare_minor >= 0),
  mandatory_charges_minor BIGINT CHECK (mandatory_charges_minor >= 0),
  optional_charges_minor BIGINT CHECK (optional_charges_minor >= 0),
  total_payable_minor BIGINT CHECK (total_payable_minor >= 0),
  fare_family TEXT,
  availability_status TEXT NOT NULL DEFAULT 'AVAILABLE' CHECK (availability_status IN ('AVAILABLE','SOLD_OUT','UNKNOWN')),
  quality_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (quality_status IN ('PENDING','ACCEPTED','REJECTED','FLAGGED','MISSING_TEMPORARY','MISSING_PERMANENT')),
  canonical_version TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE fare_components (
  fare_component_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  observation_id UUID NOT NULL REFERENCES observations(observation_id) ON DELETE CASCADE,
  component_code TEXT NOT NULL,
  amount_minor BIGINT CHECK (amount_minor >= 0),
  currency CHAR(3) NOT NULL,
  source_label TEXT,
  is_estimated BOOLEAN NOT NULL DEFAULT FALSE,
  confidence TEXT NOT NULL DEFAULT 'UNKNOWN' CHECK (confidence IN ('CONFIRMED','INFERRED','UNKNOWN')),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE(observation_id, component_code)
);

CREATE TABLE quality_results (
  quality_result_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  observation_id UUID NOT NULL REFERENCES observations(observation_id) ON DELETE CASCADE,
  rule_version TEXT NOT NULL,
  quality_score NUMERIC(6,5) CHECK (quality_score >= 0 AND quality_score <= 1),
  decision TEXT NOT NULL CHECK (decision IN ('ACCEPT','REJECT','FLAG','IMPUTE','REPLACE')),
  reason_codes TEXT[] NOT NULL DEFAULT '{}',
  checked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE methodology_versions (
  methodology_version TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  formula TEXT,
  rules JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE index_values (
  index_value_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  index_name TEXT NOT NULL,
  period_start DATE NOT NULL,
  period_end DATE NOT NULL,
  frequency TEXT NOT NULL CHECK (frequency IN ('DAILY','WEEKLY','MONTHLY')),
  basket_version TEXT NOT NULL,
  methodology_version TEXT NOT NULL REFERENCES methodology_versions(methodology_version),
  value NUMERIC(20,8) NOT NULL,
  coverage_ratio NUMERIC(8,6) CHECK (coverage_ratio >= 0 AND coverage_ratio <= 1),
  observation_count INTEGER NOT NULL CHECK (observation_count >= 0),
  confidence TEXT NOT NULL CHECK (confidence IN ('HIGH','MEDIUM','LOW','NO_DATA')),
  published_at TIMESTAMPTZ,
  UNIQUE(index_name, period_start, period_end, frequency, basket_version, methodology_version)
);

CREATE TABLE lineage (
  lineage_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  index_value_id UUID REFERENCES index_values(index_value_id) ON DELETE CASCADE,
  observation_id UUID REFERENCES observations(observation_id),
  raw_quote_id UUID REFERENCES raw_quotes(raw_quote_id),
  route_id UUID REFERENCES routes(route_id),
  source_id VARCHAR(32) REFERENCES source_registry(source_id),
  transformation TEXT NOT NULL,
  transformation_version TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_raw_quotes_run_captured ON raw_quotes(run_id, captured_at);
CREATE INDEX idx_observations_route_departure ON observations(route_id, departure_at);
CREATE INDEX idx_observations_window ON observations(advance_window, collection_timestamp);
CREATE INDEX idx_observations_quality ON observations(quality_status);
CREATE INDEX idx_lineage_index ON lineage(index_value_id);
