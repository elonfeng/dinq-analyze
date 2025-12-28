-- Jobs / Cards / Events / Artifacts tables for unified analysis pipeline

CREATE TABLE IF NOT EXISTS jobs (
  id VARCHAR(64) PRIMARY KEY,
  user_id VARCHAR(100) NOT NULL,
  source VARCHAR(50) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'queued',
  last_seq BIGINT NOT NULL DEFAULT 0,
  input JSONB,
  options JSONB,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  result JSONB,
  subject_key VARCHAR(256)
);

-- Backward-compatible column add (existing deployments won't get new columns from CREATE TABLE IF NOT EXISTS).
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS subject_key VARCHAR(256);
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS last_seq BIGINT DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_subject_key ON jobs(subject_key);

CREATE TABLE IF NOT EXISTS job_cards (
  id BIGSERIAL PRIMARY KEY,
  job_id VARCHAR(64) NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  card_type VARCHAR(50) NOT NULL,
  priority INTEGER NOT NULL DEFAULT 0,
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  deadline_ms INTEGER NULL,
  concurrency_group VARCHAR(64) NULL,
  input JSONB,
  deps JSONB,
  output JSONB,
  retry_count INTEGER NOT NULL DEFAULT 0,
  started_at TIMESTAMP NULL,
  ended_at TIMESTAMP NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Backward-compatible column add (existing deployments won't get new columns from CREATE TABLE IF NOT EXISTS).
ALTER TABLE job_cards ADD COLUMN IF NOT EXISTS deps JSONB;
ALTER TABLE job_cards ADD COLUMN IF NOT EXISTS priority INTEGER DEFAULT 0;
ALTER TABLE job_cards ADD COLUMN IF NOT EXISTS deadline_ms INTEGER;
ALTER TABLE job_cards ADD COLUMN IF NOT EXISTS concurrency_group VARCHAR(64);

CREATE INDEX IF NOT EXISTS idx_job_cards_job_id ON job_cards(job_id);
CREATE INDEX IF NOT EXISTS idx_job_cards_status ON job_cards(status);
CREATE INDEX IF NOT EXISTS idx_job_cards_card_type ON job_cards(card_type);
CREATE INDEX IF NOT EXISTS idx_job_cards_status_priority ON job_cards(status, priority);
CREATE INDEX IF NOT EXISTS idx_job_cards_concurrency_group ON job_cards(concurrency_group);

CREATE TABLE IF NOT EXISTS job_events (
  id BIGSERIAL PRIMARY KEY,
  job_id VARCHAR(64) NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  card_id BIGINT NULL REFERENCES job_cards(id) ON DELETE SET NULL,
  seq BIGINT NOT NULL,
  event_type VARCHAR(50) NOT NULL,
  payload JSONB,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_job_events_job_seq ON job_events(job_id, seq);
CREATE INDEX IF NOT EXISTS idx_job_events_job_id ON job_events(job_id);

CREATE TABLE IF NOT EXISTS artifacts (
  id BIGSERIAL PRIMARY KEY,
  job_id VARCHAR(64) NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  card_id BIGINT NULL REFERENCES job_cards(id) ON DELETE SET NULL,
  type VARCHAR(50) NOT NULL,
  payload JSONB,
  file_url TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_artifacts_job_id ON artifacts(job_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_card_id ON artifacts(card_id);

-- Unified subject + run + artifact cache (cross-job reuse, SWR)

CREATE TABLE IF NOT EXISTS analysis_subjects (
  id BIGSERIAL PRIMARY KEY,
  source VARCHAR(50) NOT NULL,
  subject_key VARCHAR(256) NOT NULL,
  canonical_input JSONB,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_analysis_subjects_source_key ON analysis_subjects(source, subject_key);

CREATE TABLE IF NOT EXISTS analysis_artifact_cache (
  artifact_key VARCHAR(128) PRIMARY KEY,
  kind VARCHAR(64) NOT NULL,
  payload JSONB,
  content_hash VARCHAR(128),
  created_at TIMESTAMP DEFAULT NOW(),
  expires_at TIMESTAMP NULL,
  meta JSONB
);

CREATE INDEX IF NOT EXISTS idx_analysis_artifact_cache_expires_at ON analysis_artifact_cache(expires_at);

CREATE TABLE IF NOT EXISTS analysis_runs (
  id BIGSERIAL PRIMARY KEY,
  subject_id BIGINT NOT NULL REFERENCES analysis_subjects(id) ON DELETE CASCADE,
  pipeline_version VARCHAR(64) NOT NULL,
  options_hash VARCHAR(128) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'running', -- running|completed|failed
  fingerprint VARCHAR(128),
  full_report_artifact_key VARCHAR(128) REFERENCES analysis_artifact_cache(artifact_key) ON DELETE SET NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  started_at TIMESTAMP DEFAULT NOW(),
  ended_at TIMESTAMP NULL,
  freshness_until TIMESTAMP NULL,
  meta JSONB
);

CREATE INDEX IF NOT EXISTS idx_analysis_runs_subject_id ON analysis_runs(subject_id);
CREATE INDEX IF NOT EXISTS idx_analysis_runs_status ON analysis_runs(status);
CREATE INDEX IF NOT EXISTS idx_analysis_runs_freshness_until ON analysis_runs(freshness_until);
CREATE INDEX IF NOT EXISTS idx_analysis_runs_subject_status ON analysis_runs(subject_id, status);

-- Optional: prevent duplicate running runs for the same key (Postgres partial index).
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = 'idx_analysis_runs_unique_running'
  ) THEN
    CREATE UNIQUE INDEX idx_analysis_runs_unique_running
      ON analysis_runs(subject_id, pipeline_version, options_hash)
      WHERE status = 'running';
  END IF;
END $$;

-- Resource versions (optional future expansion; keep schema ready)
CREATE TABLE IF NOT EXISTS analysis_resource_versions (
  id BIGSERIAL PRIMARY KEY,
  subject_id BIGINT NOT NULL REFERENCES analysis_subjects(id) ON DELETE CASCADE,
  resource_name VARCHAR(64) NOT NULL,
  fetch_params_hash VARCHAR(128) NOT NULL,
  content_hash VARCHAR(128),
  etag TEXT,
  last_modified TEXT,
  fetched_at TIMESTAMP DEFAULT NOW(),
  expires_at TIMESTAMP NULL,
  payload JSONB,
  meta JSONB
);

CREATE INDEX IF NOT EXISTS idx_analysis_resource_versions_subject_resource ON analysis_resource_versions(subject_id, resource_name);
CREATE INDEX IF NOT EXISTS idx_analysis_resource_versions_expires_at ON analysis_resource_versions(expires_at);
CREATE INDEX IF NOT EXISTS idx_analysis_resource_versions_subject_fetched ON analysis_resource_versions(subject_id, fetched_at);

-- Idempotency keys for create-job requests (Gateway-facing)
-- Allows clients to safely retry without creating duplicate jobs.

CREATE TABLE IF NOT EXISTS job_idempotency (
  id BIGSERIAL PRIMARY KEY,
  user_id VARCHAR(100) NOT NULL,
  idempotency_key VARCHAR(128) NOT NULL,
  request_hash VARCHAR(128) NOT NULL,
  job_id VARCHAR(64) NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_job_idempotency_user_key ON job_idempotency(user_id, idempotency_key);
CREATE INDEX IF NOT EXISTS idx_job_idempotency_job_id ON job_idempotency(job_id);
