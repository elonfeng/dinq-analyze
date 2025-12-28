#!/usr/bin/env bash
# dinq-dev deployment helper (systemd + gunicorn)
#
# Usage:
#   ./deploy.sh setup|migrate|install|start|stop|restart|status|update|logs|help
#
# Notes:
# - Intended for /root/dinq-dev (dev branch) on 74.48.107.93.
# - Runs alongside existing dinq.service on :5001 (no impact).

set -euo pipefail

APP_NAME="dinq-dev"
RUNNER_APP_NAME="${RUNNER_APP_NAME:-${APP_NAME}-runner}"
GIT_BRANCH="dev"
BIND_ADDR="${DINQ_BIND_ADDR:-0.0.0.0}"
PORT="${DINQ_PORT:-8080}"
WORKERS="${WORKERS:-4}"
THREADS="${THREADS:-8}"
TIMEOUT="${TIMEOUT:-300}"
API_EXECUTOR_MODE="${API_EXECUTOR_MODE:-external}"
RUNNER_MAX_WORKERS="${RUNNER_MAX_WORKERS:-4}"
RUNNER_POLL_INTERVAL="${RUNNER_POLL_INTERVAL:-0.5}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${SCRIPT_DIR}"
VENV_DIR="${PROJECT_DIR}/venv"
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/server.log"
ERROR_LOG_FILE="${LOG_DIR}/server_error.log"
SERVICE_FILE="/etc/systemd/system/${APP_NAME}.service"
RUNNER_LOG_FILE="${LOG_DIR}/runner.log"
RUNNER_ERROR_LOG_FILE="${LOG_DIR}/runner_error.log"
RUNNER_SERVICE_FILE="/etc/systemd/system/${RUNNER_APP_NAME}.service"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

say() { echo -e "$*"; }
die() { say "${RED}ERROR:${NC} $*"; exit 1; }

check_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    die "Please run as root (sudo $0 $*)"
  fi
}

ensure_dirs() {
  mkdir -p "${LOG_DIR}"
}

activate_venv() {
  # shellcheck disable=SC1091
  source "${VENV_DIR}/bin/activate"
}

setup_venv() {
  ensure_dirs

  if [[ -d "${VENV_DIR}" ]]; then
    say "${GREEN}venv exists:${NC} ${VENV_DIR}"
    return 0
  fi

  if ! command -v python3 >/dev/null 2>&1; then
    die "python3 not found"
  fi

  say "${BLUE}Creating venv...${NC}"
  if ! python3 -m venv "${VENV_DIR}" >/dev/null 2>&1; then
    say "${YELLOW}python3 venv failed, trying to install python3-venv...${NC}"
    if command -v apt-get >/dev/null 2>&1; then
      check_root
      apt-get update
      apt-get install -y python3-venv
    else
      die "Cannot auto-install python3-venv (apt-get not found). Please install venv support and retry."
    fi
    python3 -m venv "${VENV_DIR}"
  fi

  say "${GREEN}venv created:${NC} ${VENV_DIR}"
}

install_deps() {
  setup_venv
  activate_venv

  say "${BLUE}Installing dependencies...${NC}"
  python -m pip install --upgrade pip wheel
  python -m pip install -r "${PROJECT_DIR}/requirements.txt"
  say "${GREEN}Dependencies installed.${NC}"
}

load_env_files_for_migration() {
  # For migrations we need DB URL; source env files if present.
  # Avoid "set -u" issues during sourcing.
  set +u
  if [[ -f "${PROJECT_DIR}/.env.production.local" ]]; then
    # shellcheck disable=SC1091
    set -a; source "${PROJECT_DIR}/.env.production.local"; set +a
  fi
  if [[ -f "${PROJECT_DIR}/.env.production" ]]; then
    # shellcheck disable=SC1091
    set -a; source "${PROJECT_DIR}/.env.production"; set +a
  fi
  set -u
}

resolve_db_url() {
  local url="${DINQ_DB_URL:-${DATABASE_URL:-${DB_URL:-}}}"
  if [[ -z "${url}" ]]; then
    die "Missing DB URL. Set DINQ_DB_URL or DATABASE_URL (or provide .env.production/.env.production.local)."
  fi

  url="${url/postgresql+psycopg2:\/\//postgresql:\/\/}"
  url="${url/postgresql+asyncpg:\/\//postgresql:\/\/}"
  echo "${url}"
}

migrate_db() {
  ensure_dirs
  load_env_files_for_migration

  if ! command -v psql >/dev/null 2>&1; then
    die "psql not found. Install postgres client tools first."
  fi

  local db_url
  db_url="$(resolve_db_url)"

  say "${BLUE}Running migrations...${NC}"
  psql "${db_url}" -v ON_ERROR_STOP=1 -f "${PROJECT_DIR}/migrations/create_job_tables.sql"
  psql "${db_url}" -v ON_ERROR_STOP=1 -f "${PROJECT_DIR}/migrations/create_llm_cache.sql"
  say "${GREEN}Migrations complete.${NC}"
}

write_service_file() {
  check_root
  ensure_dirs

  if [[ ! -x "${VENV_DIR}/bin/gunicorn" ]]; then
    say "${YELLOW}gunicorn not found in venv; running setup...${NC}"
    install_deps
  fi

  cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=DINQ Dev Analysis Service (dinq-dev)
After=network.target

[Service]
User=root
WorkingDirectory=${PROJECT_DIR}
ExecStart=${VENV_DIR}/bin/gunicorn --bind ${BIND_ADDR}:${PORT} --worker-class gthread --threads ${THREADS} --workers ${WORKERS} --timeout ${TIMEOUT} server.app:app
Restart=always
RestartSec=5
StandardOutput=append:${LOG_FILE}
StandardError=append:${ERROR_LOG_FILE}
LimitNOFILE=65535
Environment="PATH=${VENV_DIR}/bin:/usr/local/bin:/usr/bin:/bin"
Environment="DINQ_ENV=production"
Environment="FLASK_ENV=production"
Environment="DINQ_EXECUTOR_MODE=${API_EXECUTOR_MODE}"

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  say "${GREEN}Wrote systemd unit:${NC} ${SERVICE_FILE}"
}

write_runner_service_file() {
  check_root
  ensure_dirs

  if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    say "${YELLOW}python not found in venv; running setup...${NC}"
    install_deps
  fi

  cat > "${RUNNER_SERVICE_FILE}" <<EOF
[Unit]
Description=DINQ Dev Analysis Runner (dinq-dev-runner)
After=network.target

[Service]
User=root
WorkingDirectory=${PROJECT_DIR}
ExecStart=${VENV_DIR}/bin/python ${PROJECT_DIR}/new_runner.py --max-workers ${RUNNER_MAX_WORKERS} --poll-interval ${RUNNER_POLL_INTERVAL}
Restart=always
RestartSec=5
StandardOutput=append:${RUNNER_LOG_FILE}
StandardError=append:${RUNNER_ERROR_LOG_FILE}
LimitNOFILE=65535
Environment="PATH=${VENV_DIR}/bin:/usr/local/bin:/usr/bin:/bin"
Environment="DINQ_ENV=production"
Environment="FLASK_ENV=production"
Environment="DINQ_EXECUTOR_MODE=runner"

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  say "${GREEN}Wrote systemd unit:${NC} ${RUNNER_SERVICE_FILE}"
}

install_service() {
  write_service_file
  systemctl enable "${APP_NAME}"
  say "${GREEN}Enabled service:${NC} ${APP_NAME}"
}

install_runner_service() {
  write_runner_service_file
  systemctl enable "${RUNNER_APP_NAME}"
  say "${GREEN}Enabled service:${NC} ${RUNNER_APP_NAME}"
}

start_service() {
  check_root
  systemctl start "${APP_NAME}"
  say "${GREEN}Started:${NC} ${APP_NAME}"
}

start_runner_service() {
  check_root
  systemctl start "${RUNNER_APP_NAME}"
  say "${GREEN}Started:${NC} ${RUNNER_APP_NAME}"
}

stop_service() {
  check_root
  systemctl stop "${APP_NAME}"
  say "${GREEN}Stopped:${NC} ${APP_NAME}"
}

stop_runner_service() {
  check_root
  systemctl stop "${RUNNER_APP_NAME}"
  say "${GREEN}Stopped:${NC} ${RUNNER_APP_NAME}"
}

restart_service() {
  check_root
  systemctl restart "${APP_NAME}"
  say "${GREEN}Restarted:${NC} ${APP_NAME}"
}

restart_runner_service() {
  check_root
  systemctl restart "${RUNNER_APP_NAME}"
  say "${GREEN}Restarted:${NC} ${RUNNER_APP_NAME}"
}

status_service() {
  systemctl status "${APP_NAME}" --no-pager -l || true
}

status_runner_service() {
  systemctl status "${RUNNER_APP_NAME}" --no-pager -l || true
}

update_code() {
  say "${BLUE}Updating code (branch: ${GIT_BRANCH})...${NC}"
  git -C "${PROJECT_DIR}" fetch origin
  git -C "${PROJECT_DIR}" checkout "${GIT_BRANCH}"
  git -C "${PROJECT_DIR}" pull --ff-only origin "${GIT_BRANCH}"
  say "${GREEN}Code updated.${NC}"
}

update_and_restart() {
  check_root
  update_code
  install_deps
  migrate_db
  write_service_file
  restart_service
  if [[ "${API_EXECUTOR_MODE}" != "inprocess" ]]; then
    write_runner_service_file
    systemctl enable "${RUNNER_APP_NAME}" || true
    restart_runner_service || true
  fi
}

show_logs() {
  # Follow systemd logs for this service.
  journalctl -u "${APP_NAME}" -n 200 --no-pager || true
}

show_help() {
  cat <<EOF
${APP_NAME} deploy helper

Usage:
  ./deploy.sh setup        # create venv + install deps
  ./deploy.sh migrate      # run SQL migrations (psql)
  ./deploy.sh install      # install/enable systemd unit (${APP_NAME}.service)
  ./deploy.sh install-runner # install/enable runner unit (${RUNNER_APP_NAME}.service)
  ./deploy.sh start|stop|restart|status
  ./deploy.sh start-runner|stop-runner|restart-runner|status-runner
  ./deploy.sh update       # git pull + deps + migrate + restart
  ./deploy.sh logs         # journalctl -u ${APP_NAME}
  ./deploy.sh logs-runner  # journalctl -u ${RUNNER_APP_NAME}

Notes:
  - Service binds ${BIND_ADDR}:${PORT}. If you removed shared-secret auth, lock this port down to gateway IP(s).
  - Ensure /root/dinq-dev has .env.production (or .env.production.local) and systemd sets DINQ_ENV/FLASK_ENV=production.
  - Default topology is API+Runner (external runner). To force legacy in-process execution, set API_EXECUTOR_MODE=inprocess.
EOF
}

main() {
  case "${1:-}" in
    setup)
      install_deps
      ;;
    migrate)
      migrate_db
      ;;
    install)
      install_service
      if [[ "${API_EXECUTOR_MODE}" != "inprocess" ]]; then
        install_runner_service
      fi
      ;;
    install-runner)
      install_runner_service
      ;;
    start)
      start_service
      ;;
    start-runner)
      start_runner_service
      ;;
    stop)
      stop_service
      ;;
    stop-runner)
      stop_runner_service
      ;;
    restart)
      restart_service
      ;;
    restart-runner)
      restart_runner_service
      ;;
    status)
      status_service
      ;;
    status-runner)
      status_runner_service
      ;;
    update)
      update_and_restart
      ;;
    logs)
      show_logs
      ;;
    logs-runner)
      journalctl -u "${RUNNER_APP_NAME}" -n 200 --no-pager || true
      ;;
    help|-h|--help|"")
      show_help
      ;;
    *)
      die "Unknown command: ${1}. Run: ./deploy.sh help"
      ;;
  esac
}

main "$@"
