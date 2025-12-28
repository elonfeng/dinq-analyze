#!/usr/bin/env bash
set -euo pipefail

# Smoke test for gateway analyze endpoints:
#   POST /api/v1/analyze
#   GET  /api/v1/analyze/jobs/{job_id}
#   GET  /api/v1/analyze/jobs/{job_id}/stream?after=<seq>
#
# Env:
#   API_BASE         default: https://api.dinq.me
#   TOKEN            JWT token (with or without "Bearer ")
#   SOURCE           default: scholar
#   INPUT_JSON       default: {}
#   CARDS_JSON       optional JSON array, e.g. ["profile","summary"]
#   OPTIONS_JSON     default: {}
#   STREAM_TIMEOUT   default: 8 (seconds)
#
# Examples:
#   TOKEN=... ./test_analyze_gateway.sh smoke
#   TOKEN=... SOURCE=scholar INPUT_JSON='{"content":"Y-ql3zMAAAAJ"}' ./test_analyze_gateway.sh smoke

API_BASE="${API_BASE:-https://api.dinq.me}"
TOKEN="${TOKEN:-}"
SOURCE="${SOURCE:-scholar}"
MODE="${MODE:-sync}" # sync|async
INPUT_JSON="${INPUT_JSON:-{}}"
CARDS_JSON="${CARDS_JSON:-}"
OPTIONS_JSON="${OPTIONS_JSON:-{}}"
STREAM_TIMEOUT="${STREAM_TIMEOUT:-8}"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-60}"
POLL_INTERVAL="${POLL_INTERVAL:-2}"

die() { echo "ERROR: $*" >&2; exit 1; }

auth_header() {
  if [[ -z "${TOKEN}" ]]; then
    die "Missing TOKEN env (JWT)."
  fi
  if [[ "${TOKEN}" == Bearer\ * ]]; then
    echo "Authorization: ${TOKEN}"
    return 0
  fi
  echo "Authorization: Bearer ${TOKEN}"
}

build_payload() {
  python3 - <<PY
import json, os
payload = {
  "source": os.environ.get("SOURCE","scholar"),
  "mode": os.environ.get("MODE","sync"),
  "input": json.loads(os.environ.get("INPUT_JSON","{}")),
  "options": json.loads(os.environ.get("OPTIONS_JSON","{}")),
}
cards = os.environ.get("CARDS_JSON","").strip()
if cards:
  payload["cards"] = json.loads(cards)
print(json.dumps(payload, ensure_ascii=False))
PY
}

create_job() {
  local tmp code payload
  tmp="$(mktemp)"
  payload="$(build_payload)"
  code="$(curl -sS --max-time 180 -o "${tmp}" -w "%{http_code}" \
    -X POST \
    -H "$(auth_header)" \
    -H "Content-Type: application/json" \
    -d "${payload}" \
    "${API_BASE%/}/api/v1/analyze")"

  echo "create HTTP ${code}" >&2
  head -c 800 "${tmp}" >&2; echo >&2
  if [[ "${code}" != "200" ]]; then
    rm -f "${tmp}"
    return 1
  fi

  python3 - <<PY >&2
import json
with open("${tmp}","r",encoding="utf-8") as f:
  obj=json.load(f)
print("job_id=", obj.get("job_id"))
print("status=", obj.get("status"))
PY
  job_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("job_id",""))' < "${tmp}")"
  rm -f "${tmp}"
  [[ -n "${job_id}" ]] || die "create succeeded but missing job_id"
  echo "${job_id}"
}

wait_job() {
  local job_id="${1:-}"
  [[ -n "${job_id}" ]] || die "usage: wait <job_id>"

  API_BASE="${API_BASE}" TOKEN="${TOKEN}" WAIT_TIMEOUT="${WAIT_TIMEOUT}" POLL_INTERVAL="${POLL_INTERVAL}" JOB_ID="${job_id}" python3 - <<PY
import json, os, time, urllib.request
job_id = os.environ["JOB_ID"]
api = os.environ["API_BASE"].rstrip("/")
token = os.environ["TOKEN"]
timeout_s = int(os.environ.get("WAIT_TIMEOUT","60"))
poll = float(os.environ.get("POLL_INTERVAL","2"))

hdr = token if token.lower().startswith("bearer ") else f"Bearer {token}"
url = f"{api}/api/v1/analyze/jobs/{job_id}"
terminal = {"completed","partial","failed","cancelled"}

start = time.time()
while True:
    req = urllib.request.Request(url, headers={"Authorization": hdr})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    status = (data.get("job") or {}).get("status") or "unknown"
    print(f"status={status} last_seq={(data.get('job') or {}).get('last_seq')}")
    if status in terminal:
        break
    if time.time() - start > timeout_s:
        raise SystemExit(f"timeout waiting for terminal status (>{timeout_s}s)")
    time.sleep(poll)
PY
}

get_status() {
  local job_id="${1:-}"
  [[ -n "${job_id}" ]] || die "usage: status <job_id>"
  curl -sS --max-time 30 -H "$(auth_header)" "${API_BASE%/}/api/v1/analyze/jobs/${job_id}" | head -c 1200; echo
}

stream_preview() {
  local job_id="${1:-}"
  local after="${2:-0}"
  [[ -n "${job_id}" ]] || die "usage: stream <job_id> [after]"
  echo "stream: ${API_BASE%/}/api/v1/analyze/jobs/${job_id}/stream?after=${after}"
  echo "(Note: stream auto-closes after job completion; timeout is ok for preview.)"
  curl -sS -N -m "${STREAM_TIMEOUT}" -H "$(auth_header)" \
    "${API_BASE%/}/api/v1/analyze/jobs/${job_id}/stream?after=${after}" \
    | head -c 1200
  echo
}

cmd="${1:-smoke}"
case "${cmd}" in
  smoke)
    job_id="$(create_job)"
    echo "== status =="
    get_status "${job_id}"
    echo "== stream (preview) =="
    stream_preview "${job_id}" 0 || true
    ;;
  cache)
    [[ "${MODE}" == "async" ]] || export MODE="async"
    echo "== create 1 (expect cache miss) =="
    job_id_1="$(create_job)"
    echo "== wait 1 =="
    JOB_ID="${job_id_1}" API_BASE="${API_BASE}" TOKEN="${TOKEN}" WAIT_TIMEOUT="${WAIT_TIMEOUT}" POLL_INTERVAL="${POLL_INTERVAL}" wait_job "${job_id_1}"
    echo "== create 2 (expect cache hit, fast) =="
    job_id_2="$(create_job)"
    echo "== status 2 =="
    get_status "${job_id_2}"
    echo "== stream 2 (preview) =="
    stream_preview "${job_id_2}" 0 || true
    ;;
  create)
    create_job
    ;;
  status)
    get_status "${2:-}"
    ;;
  stream)
    stream_preview "${2:-}" "${3:-0}" || true
    ;;
  wait)
    wait_job "${2:-}"
    ;;
  help|-h|--help)
    sed -n '1,60p' "$0"
    ;;
  *)
    die "Unknown command: ${cmd} (use: smoke|cache|create|status|stream|wait)"
    ;;
esac
