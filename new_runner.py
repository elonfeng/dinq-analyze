#!/usr/bin/env python3
"""
DINQ Analysis Runner

Standalone runner process for the unified analysis pipeline.

It continuously:
  - claims ready job cards from the DB
  - executes cards (crawlers/LLM/etc.)
  - emits job events for SSE replay

This is intended to be used when the API runs with:
  DINQ_EXECUTOR_MODE=external
and this runner runs with:
  DINQ_EXECUTOR_MODE=runner
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time
from typing import Optional

# Add the project root to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Load env files early (before importing DB modules that read env at import time).
from server.config.env_loader import load_environment_variables

load_environment_variables()

from server.utils.logging_config import setup_logging

from server.analyze.pipeline import PipelineExecutor
from server.tasks.artifact_store import ArtifactStore
from server.tasks.event_store import EventStore
from server.tasks.job_store import JobStore
from server.tasks.scheduler import CardScheduler


_stop = False


def _handle_signal(signum, frame) -> None:  # noqa: ARG001
    global _stop
    _stop = True


def _read_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return int(default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return int(default)


def _resolve_max_workers(cli_value: Optional[int]) -> int:
    if cli_value is not None:
        return max(1, min(int(cli_value), 64))
    return max(1, min(_read_int_env("DINQ_ANALYZE_SCHEDULER_MAX_WORKERS", 4), 64))


def main() -> None:
    os.environ.setdefault("DINQ_EXECUTOR_MODE", "runner")

    setup_logging()
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description="DINQ unified analysis runner")
    parser.add_argument("--max-workers", type=int, default=None, help="Max concurrent card executions (ThreadPoolExecutor)")
    parser.add_argument("--poll-interval", type=float, default=0.5, help="DB poll interval (seconds)")
    args = parser.parse_args()

    max_workers = _resolve_max_workers(args.max_workers)

    job_store = JobStore()
    event_store = EventStore()
    artifact_store = ArtifactStore()
    pipeline_executor = PipelineExecutor(job_store, artifact_store, event_store)

    scheduler = CardScheduler(
        job_store=job_store,
        event_store=event_store,
        artifact_store=artifact_store,
        card_executor=lambda card: pipeline_executor.execute_card(card, emit_deltas=True),
        max_workers=max_workers,
        poll_interval=float(args.poll_interval or 0.5),
    )

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    scheduler.start()
    logger.info("DINQ runner started (max_workers=%s, poll_interval=%s)", max_workers, args.poll_interval)

    try:
        while not _stop:
            time.sleep(1.0)
    finally:
        scheduler.stop()
        logger.info("DINQ runner stopped")


if __name__ == "__main__":
    main()
