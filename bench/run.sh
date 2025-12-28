#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"

# Default: run an isolated local server to avoid interfering with any existing instance.
host="127.0.0.1"
port="${DINQ_BENCH_PORT:-8091}"
base_url="http://${host}:${port}"
db_path="${DINQ_BENCH_DB_PATH:-${repo_root}/.local/local_test.db}"

cd "${repo_root}"

python bench/run_bench.py \
  --start-server \
  --fresh-db \
  --host "${host}" \
  --port "${port}" \
  --base-url "${base_url}" \
  --db-path "${db_path}" \
  --samples "${repo_root}/bench/samples.json"
