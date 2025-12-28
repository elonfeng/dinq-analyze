#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

export PYTHONDONTWRITEBYTECODE=1
export FLASK_ENV="${FLASK_ENV:-test}"

# Offline / CI safety knobs
export DINQ_AUTH_BYPASS="${DINQ_AUTH_BYPASS:-true}"
export DINQ_EMAIL_BACKEND="${DINQ_EMAIL_BACKEND:-file}"
export DINQ_TEST_EMAIL_OUTBOX_PATH="${DINQ_TEST_EMAIL_OUTBOX_PATH:-$ROOT/.test_outbox/emails.jsonl}"
export AXIOM_ENABLED="${AXIOM_ENABLED:-false}"

export DINQ_PG_PORT="${DINQ_PG_PORT:-55432}"
DINQ_COMPOSE_PROJECT_NAME="${DINQ_COMPOSE_PROJECT_NAME:-dinq_test}"

DEFAULT_PG_URL="postgresql+psycopg2://dinq:dinq@localhost:${DINQ_PG_PORT}/dinq"
DEFAULT_SQLITE_URL="sqlite:///$ROOT/.test_db.sqlite"
use_docker_pg="false"

if [[ -z "${DINQ_DB_URL:-}" ]]; then
  if docker info >/dev/null 2>&1; then
    export DINQ_DB_URL="$DEFAULT_PG_URL"
    use_docker_pg="true"
  else
    export DINQ_DB_URL="$DEFAULT_SQLITE_URL"
  fi
fi

mkdir -p "$(dirname "$DINQ_TEST_EMAIL_OUTBOX_PATH")"
rm -f "$DINQ_TEST_EMAIL_OUTBOX_PATH"

PY="${PYTHON:-python3}"

if [[ "$use_docker_pg" == "true" ]]; then
  echo "[offline] starting local dependencies (docker compose)..."
  docker compose -p "$DINQ_COMPOSE_PROJECT_NAME" up -d postgres

  echo "[offline] waiting for postgres..."
  for i in $(seq 1 60); do
    if docker compose -p "$DINQ_COMPOSE_PROJECT_NAME" exec -T postgres pg_isready -U dinq -d dinq >/dev/null 2>&1; then
      echo "[offline] postgres is ready"
      break
    fi
    sleep 1
    if [ "$i" -eq 60 ]; then
      echo "[offline] postgres not ready in time" >&2
      docker compose -p "$DINQ_COMPOSE_PROJECT_NAME" logs postgres >&2 || true
      exit 1
    fi
  done
elif [[ "$DINQ_DB_URL" == "$DEFAULT_SQLITE_URL" ]]; then
  echo "[offline] docker not available; using sqlite: $DINQ_DB_URL"
  rm -f "$ROOT/.test_db.sqlite"
else
  echo "[offline] using external db: $DINQ_DB_URL"
fi

echo "[offline] init db tables..."
$PY -c "from src.utils.db_utils import create_tables; assert create_tables()"

echo "[offline] run offline integration tests..."
$PY -m unittest discover -v -s tests/offline_integration -p "test_*.py"
