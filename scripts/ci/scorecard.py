#!/usr/bin/env python3
"""
Generate a local test + perf scorecard and export logs.

This is meant for:
- Quantifying regression risk after refactors
- Providing a stable, repeatable baseline for comparison

It never prints secrets; it only records whether a key is set.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


ROOT = Path(__file__).resolve().parents[2]


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _git_head() -> Optional[str]:
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT)
        return out.decode("utf-8", errors="replace").strip() or None
    except Exception:
        return None


def _git_dirty() -> Optional[bool]:
    try:
        out = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)
        return bool(out.decode("utf-8", errors="replace").strip())
    except Exception:
        return None


def _safe_key_presence() -> Dict[str, bool]:
    """
    Only report whether a key is set (env or env files). Never include values.
    """
    keys = [
        "GITHUB_TOKEN",
        "OPENROUTER_API_KEY",
        "CRAWLBASE_API_TOKEN",
        "TAVILY_API_KEY",
        "RESEND_API_KEY",
    ]

    present: Dict[str, bool] = {k: bool(os.getenv(k)) for k in keys}

    # Additionally, check common env files without exporting values.
    try:
        from dotenv import dotenv_values  # type: ignore

        # Mirror env_loader precedence (highest -> lowest).
        runtime_env = (os.getenv("DINQ_ENV") or os.getenv("FLASK_ENV") or "development").strip().lower()
        candidates = [
            f".env.{runtime_env}.local",
            ".env.local",
            f".env.{runtime_env}",
            ".env",
        ]
        for name in candidates:
            path = ROOT / name
            if not path.exists():
                continue
            values = dotenv_values(path) or {}
            for k in keys:
                if present[k]:
                    continue
                v = values.get(k)
                if v is None:
                    continue
                if str(v).strip():
                    present[k] = True
    except Exception:
        pass

    return present


@dataclass
class StepResult:
    name: str
    ok: bool
    exit_code: int
    duration_seconds: float
    stdout_path: str
    stderr_path: str
    extra: Dict[str, Any]


def _run_step(
    *,
    name: str,
    cmd: str,
    out_dir: Path,
    env: Optional[Dict[str, str]] = None,
    timeout_seconds: Optional[int] = None,
) -> StepResult:
    stdout_path = out_dir / f"{name}.stdout.log"
    stderr_path = out_dir / f"{name}.stderr.log"

    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    started = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        shell=True,
        env=merged_env,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
    )
    duration = time.perf_counter() - started

    stdout_path.write_text(proc.stdout or "", encoding="utf-8", errors="replace")
    stderr_path.write_text(proc.stderr or "", encoding="utf-8", errors="replace")

    extra: Dict[str, Any] = {}
    if name == "perf_sse":
        # Parse bench/sse_bench.py output.
        text = proc.stdout or ""
        m = re.search(r"data_lines_per_second=(?P<v>[0-9.]+)", text)
        if m:
            try:
                extra["data_lines_per_second"] = float(m.group("v"))
            except ValueError:
                pass
        m = re.search(r"elapsed_seconds=(?P<v>[0-9.]+)", text)
        if m:
            try:
                extra["elapsed_seconds"] = float(m.group("v"))
            except ValueError:
                pass

    return StepResult(
        name=name,
        ok=proc.returncode == 0,
        exit_code=int(proc.returncode),
        duration_seconds=float(duration),
        stdout_path=str(stdout_path.relative_to(ROOT)),
        stderr_path=str(stderr_path.relative_to(ROOT)),
        extra=extra,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="", help="output directory (default: reports/scorecard/<timestamp>-<sha>)")
    parser.add_argument("--events", type=int, default=20000, help="SSE bench events")
    parser.add_argument("--with-smoke", action="store_true", help="also run online smoke (needs keys, flaky)")
    args = parser.parse_args()

    head = _git_head() or "unknown"
    short = head[:8] if head != "unknown" else "unknown"
    default_out = ROOT / "reports" / "scorecard" / f"{_now_stamp()}-{short}"
    out_dir = Path(args.out).resolve() if args.out else default_out
    out_dir.mkdir(parents=True, exist_ok=True)

    meta: Dict[str, Any] = {
        "generated_at": _now_stamp(),
        "git": {"head": head, "dirty": _git_dirty()},
        "key_presence": _safe_key_presence(),
        "platform": {"python": sys.version.split()[0]},
    }

    results: Dict[str, Any] = {"meta": meta, "steps": []}

    steps = []
    steps.append(
        _run_step(
            name="unit",
            cmd="./scripts/ci/test_unit.sh",
            out_dir=out_dir,
            timeout_seconds=10 * 60,
        )
    )
    steps.append(
        _run_step(
            name="offline_integration",
            cmd="./scripts/ci/test_offline_integration.sh",
            out_dir=out_dir,
            timeout_seconds=20 * 60,
        )
    )
    steps.append(
        _run_step(
            name="perf_sse",
            cmd=f"PYTHONPATH=. python3 bench/sse_bench.py --events {int(args.events)}",
            out_dir=out_dir,
            timeout_seconds=5 * 60,
        )
    )
    if args.with_smoke:
        steps.append(
            _run_step(
                name="online_smoke",
                cmd="DINQ_RUN_ONLINE_SMOKE=true ./scripts/ci/test_online_smoke.sh",
                out_dir=out_dir,
                timeout_seconds=10 * 60,
            )
        )

    results["steps"] = [
        {
            "name": s.name,
            "ok": s.ok,
            "exit_code": s.exit_code,
            "duration_seconds": s.duration_seconds,
            "stdout": s.stdout_path,
            "stderr": s.stderr_path,
            "extra": s.extra,
        }
        for s in steps
    ]
    results["ok"] = all(s.ok for s in steps)

    (out_dir / "scorecard.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(str((out_dir / "scorecard.json").relative_to(ROOT)))
    return 0 if results["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
