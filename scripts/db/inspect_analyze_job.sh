#!/usr/bin/env bash
set -euo pipefail

JOB_ID="${1:-}"
SUBJECT_KEY="${2:-}" # optional, e.g. id:1zmDOdwAAAAJ

die() { echo "ERROR: $*" >&2; exit 1; }

[[ -n "${JOB_ID}" ]] || die "usage: $0 <job_id> [subject_key]"

DB_URL="${DINQ_DB_URL:-${DATABASE_URL:-${DB_URL:-}}}"
[[ -n "${DB_URL}" ]] || die "Missing DB URL. Set DINQ_DB_URL or DATABASE_URL (or DB_URL)."

# Normalize sqlalchemy-style URLs for psql.
DB_URL="${DB_URL/postgresql+psycopg2:\/\//postgresql:\/\/}"
DB_URL="${DB_URL/postgresql+asyncpg:\/\//postgresql:\/\/}"

echo "== jobs ==" >&2
psql "${DB_URL}" -v ON_ERROR_STOP=1 -c "SELECT id, user_id, source, status, subject_key, last_seq, created_at, updated_at FROM jobs WHERE id='${JOB_ID}';"

echo "== job_cards (status + output summary) ==" >&2
psql "${DB_URL}" -v ON_ERROR_STOP=1 -c "SELECT id, card_type, status, COALESCE(jsonb_object_keys(output->'stream')::text, '') AS stream_field, jsonb_typeof(output->'data') AS data_type FROM job_cards WHERE job_id='${JOB_ID}' ORDER BY id ASC;"

echo "== job_cards (output pretty, first 8) ==" >&2
psql "${DB_URL}" -v ON_ERROR_STOP=1 -c "SELECT id, card_type, status, jsonb_pretty(output) AS output FROM job_cards WHERE job_id='${JOB_ID}' ORDER BY id ASC LIMIT 8;"

echo "== job_events (last 60) ==" >&2
psql "${DB_URL}" -v ON_ERROR_STOP=1 -c "SELECT seq, event_type, jsonb_pretty(payload) AS payload, created_at FROM job_events WHERE job_id='${JOB_ID}' ORDER BY seq DESC LIMIT 60;"

if [[ -n "${SUBJECT_KEY}" ]]; then
  echo "== analysis_subjects ==" >&2
  psql "${DB_URL}" -v ON_ERROR_STOP=1 -c "SELECT * FROM analysis_subjects WHERE subject_key='${SUBJECT_KEY}' ORDER BY id DESC LIMIT 5;"

  echo "== analysis_runs (by subject) ==" >&2
  psql "${DB_URL}" -v ON_ERROR_STOP=1 -c "SELECT r.* FROM analysis_runs r JOIN analysis_subjects s ON s.id=r.subject_id WHERE s.subject_key='${SUBJECT_KEY}' ORDER BY r.id DESC LIMIT 10;"
fi

