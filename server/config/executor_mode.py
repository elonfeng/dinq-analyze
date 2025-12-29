"""Executor mode configuration for DINQ analysis.

The analysis stack supports two deployment topologies:

1) In-process execution (default for local/dev):
   - The Flask/gunicorn API process also starts the card scheduler and executes jobs.

2) External runner execution (recommended for production):
   - The API process ONLY handles HTTP (create job + snapshots + SSE replay).
   - A separate runner process claims ready cards from the DB and executes them.

Control this with `DINQ_EXECUTOR_MODE`:
  - "inprocess" (default): API starts scheduler
  - "external": API never starts scheduler (requires runner)
  - "runner": runner process mode (scheduler enabled; no HTTP server implied)
"""

from __future__ import annotations

import os
from typing import Literal


ExecutorMode = Literal["inprocess", "external", "runner"]


def get_executor_mode() -> ExecutorMode:
    raw = (os.getenv("DINQ_EXECUTOR_MODE") or "").strip().lower()
    if raw == "":
        # SQLite is used heavily for local/CI benches. External runner topology is not a good default
        # there (and often surprises users when DINQ_ENV=production is set in .env files).
        jobs_db_url = (os.getenv("DINQ_JOBS_DB_URL") or "").strip().lower()
        db_url = (jobs_db_url or os.getenv("DINQ_DB_URL") or os.getenv("DATABASE_URL") or "").strip().lower()
        if db_url.startswith("sqlite:"):
            return "inprocess"
        runtime_env = (os.getenv("DINQ_ENV") or os.getenv("FLASK_ENV") or "").strip().lower()
        if runtime_env in ("prod", "production"):
            # Production default: API-only + external runner for execution.
            return "external"
        return "inprocess"
    if raw in ("inprocess", "in-process", "in_process", "local"):
        return "inprocess"
    if raw in ("external", "api_only", "api-only"):
        return "external"
    if raw in ("runner", "worker", "executor"):
        return "runner"
    # Fail-safe: keep backward-compatible behavior.
    return "inprocess"


def scheduler_enabled() -> bool:
    """Whether a process is allowed to run the card scheduler."""
    return get_executor_mode() in ("inprocess", "runner")


def api_should_start_scheduler() -> bool:
    """Whether the API process should start the scheduler (in-process mode only)."""
    return get_executor_mode() == "inprocess"
