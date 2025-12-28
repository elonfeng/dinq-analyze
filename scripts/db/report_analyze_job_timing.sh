#!/usr/bin/env bash
set -euo pipefail

JOB_ID="${1:-}"

die() { echo "ERROR: $*" >&2; exit 1; }

[[ -n "${JOB_ID}" ]] || die "usage: $0 <job_id>"

DB_URL="${DINQ_DB_URL:-${DATABASE_URL:-${DB_URL:-}}}"
[[ -n "${DB_URL}" ]] || die "Missing DB URL. Set DINQ_DB_URL or DATABASE_URL (or DB_URL)."

# Normalize sqlalchemy-style URLs for psql.
DB_URL="${DB_URL/postgresql+psycopg2:\/\//postgresql:\/\/}"
DB_URL="${DB_URL/postgresql+asyncpg:\/\//postgresql:\/\/}"

echo "== job ==" >&2
psql "${DB_URL}" -v ON_ERROR_STOP=1 -c "SELECT id, user_id, source, status, subject_key, last_seq, created_at, updated_at FROM jobs WHERE id='${JOB_ID}';"

echo "== job duration (wall clock) ==" >&2
psql "${DB_URL}" -v ON_ERROR_STOP=1 -c "
SELECT
  MIN(created_at) AS first_event_at,
  MAX(created_at) AS last_event_at,
  ROUND(EXTRACT(EPOCH FROM (MAX(created_at) - MIN(created_at))) * 1000)::bigint AS duration_ms
FROM job_events
WHERE job_id='${JOB_ID}';
"

echo "== card durations (first start -> last end) ==" >&2
psql "${DB_URL}" -v ON_ERROR_STOP=1 -c "
WITH starts AS (
  SELECT card_id, MIN(created_at) AS started_at
  FROM job_events
  WHERE job_id='${JOB_ID}' AND event_type='card.started'
  GROUP BY card_id
),
ends AS (
  SELECT card_id, MAX(created_at) AS ended_at
  FROM job_events
  WHERE job_id='${JOB_ID}' AND event_type IN ('card.completed','card.failed')
  GROUP BY card_id
)
SELECT
  c.id,
  c.card_type,
  c.status,
  CASE
    WHEN s.started_at IS NULL OR e.ended_at IS NULL THEN NULL
    ELSE ROUND(EXTRACT(EPOCH FROM (e.ended_at - s.started_at)) * 1000)::bigint
  END AS duration_ms
FROM job_cards c
LEFT JOIN starts s ON s.card_id=c.id
LEFT JOIN ends e ON e.card_id=c.id
WHERE c.job_id='${JOB_ID}'
ORDER BY duration_ms DESC NULLS LAST, c.id ASC;
"

echo "== timing events (card.progress) ==" >&2
psql "${DB_URL}" -v ON_ERROR_STOP=1 -c "
SELECT
  seq,
  payload->>'card' AS card,
  payload->>'step' AS step,
  NULLIF(payload->'data'->>'duration_ms','')::bigint AS duration_ms,
  NULLIF(payload->'data'->>'fetch_ms','')::bigint AS fetch_ms,
  NULLIF(payload->'data'->>'parse_ms','')::bigint AS parse_ms,
  payload->>'message' AS message,
  created_at
FROM job_events
WHERE job_id='${JOB_ID}'
  AND event_type='card.progress'
  AND (
    payload->>'step' LIKE 'timing.%'
    OR payload->'data'->>'kind'='timing'
  )
ORDER BY seq ASC;
"
