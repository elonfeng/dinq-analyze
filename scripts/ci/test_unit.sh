#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

export PYTHONDONTWRITEBYTECODE=1
export FLASK_ENV="${FLASK_ENV:-test}"
export DINQ_AUTH_BYPASS="${DINQ_AUTH_BYPASS:-true}"
export DINQ_DB_AUTO_CREATE_TABLES="${DINQ_DB_AUTO_CREATE_TABLES:-false}"
export DINQ_EMAIL_BACKEND="${DINQ_EMAIL_BACKEND:-noop}"
export AXIOM_ENABLED="${AXIOM_ENABLED:-false}"

PY="${PYTHON:-python3}"

$PY -m unittest -v \
  tests.unit_tests.test_http_fetcher_utils \
  tests.unit_tests.test_stream_task \
  tests.unit_tests.test_streaming_task_builder \
  tests.unit_tests.test_scholar_data_fetcher_adaptive \
  tests.unit_tests.test_scholar_pipeline \
  tests.unit_tests.test_scholar_pk_task \
  tests.unit_tests.test_scholar_pk_messages
