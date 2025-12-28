#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

# 默认不跑在线 smoke，避免 CI 不稳定；需要显式打开。
if [[ "${DINQ_RUN_ONLINE_SMOKE:-false}" != "true" && "${DINQ_RUN_ONLINE_SMOKE:-false}" != "1" ]]; then
  echo "[smoke] DINQ_RUN_ONLINE_SMOKE not enabled; skipping"
  exit 0
fi

PY="${PYTHON:-python3}"
BASE_URL="${DINQ_SMOKE_BASE_URL:-http://127.0.0.1:5001}"

export PYTHONDONTWRITEBYTECODE=1

# Smoke 测试默认绕过 Firebase verified-user（否则需要 service account/真实 token）
export DINQ_AUTH_BYPASS="${DINQ_AUTH_BYPASS:-true}"
export AXIOM_ENABLED="${AXIOM_ENABLED:-false}"

echo "[smoke] starting server..."
$PY -m server.app --host 127.0.0.1 --port 5001 >/tmp/dinq_smoke_server.log 2>&1 &
SERVER_PID=$!

cleanup() {
  echo "[smoke] stopping server (pid=$SERVER_PID)..."
  kill "$SERVER_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "[smoke] waiting for $BASE_URL/health ..."
for i in $(seq 1 60); do
  if curl -fsS "$BASE_URL/health" >/dev/null 2>&1; then
    echo "[smoke] server is ready"
    break
  fi
  sleep 1
  if [ "$i" -eq 60 ]; then
    echo "[smoke] server not ready in time" >&2
    tail -n 200 /tmp/dinq_smoke_server.log >&2 || true
    exit 1
  fi
done

echo "[smoke] running smoke tests..."
$PY -m unittest discover -v -s tests/smoke -p "test_*.py"
