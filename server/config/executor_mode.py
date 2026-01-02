"""Execution topology for DINQ analysis (single-machine only).

This repo now targets a simplified deployment model:
  - API process runs the scheduler (in-process execution only)
  - Primary storage is local SQLite (jobs + caches)
  - Remote Postgres is used only as an async outbox backup (optional)

Multi-process / multi-machine runner topologies were intentionally removed to reduce
operational burden and avoid surprising latency behaviors.
"""

from __future__ import annotations

import os
from typing import Literal


ExecutorMode = Literal["inprocess"]


def get_executor_mode() -> ExecutorMode:
    # Backward-compatible API: always in-process.
    return "inprocess"


def scheduler_enabled() -> bool:
    """Whether a process is allowed to run the card scheduler."""
    return True


def api_should_start_scheduler() -> bool:
    """Whether the API process should start the scheduler (in-process mode only)."""
    return True
