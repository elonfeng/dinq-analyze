#!/usr/bin/env python3
"""
Local benchmark for DINQ unified analysis API.

What it measures (client-side):
  - /health readiness
  - POST /api/analyze latency
  - GET /api/analyze/jobs/<id> latency
  - SSE time-to-first-event and time-to-terminal

What it extracts (server-side, via SSE events):
  - timing events emitted as card.progress (step startswith "timing." or payload.data.kind=="timing")
  - card.append / card.completed milestones (per card)

It can run in two execution topologies:
  - inprocess: API process executes cards (scheduler inside API)
  - external: API is HTTP-only; a separate runner process executes cards

Recommended local usage:
  DINQ_DB_URL=sqlite:////tmp/dinq_bench.db python scripts/bench/analyze_latency.py \
    --modes inprocess external \
    --cases huggingface:openai huggingface:bigscience

Notes:
  - For github/scholar cases you must provide required tokens via env (e.g. GITHUB_TOKEN, CRAWLBASE_API_TOKEN).
  - The script auto-initializes DB tables via `src.utils.db_utils.create_tables()` for SQLite URLs.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests


REPO_ROOT = Path(__file__).resolve().parents[2]


def _now() -> float:
    return time.perf_counter()


def _sleep(seconds: float) -> None:
    time.sleep(max(0.0, float(seconds)))


def _is_sqlite_url(db_url: str) -> bool:
    return str(db_url or "").strip().lower().startswith("sqlite")


def _init_sqlite_tables(env: Dict[str, str]) -> None:
    """
    Ensure SQLAlchemy tables exist for the provided DINQ_DB_URL.

    We run this in a subprocess so that src.utils.db_utils picks up the env vars at import time.
    """

    cmd = [
        sys.executable,
        "-c",
        "from src.utils.db_utils import create_tables; raise SystemExit(0 if create_tables() else 1)",
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"DB init failed (rc={proc.returncode}):\n{proc.stdout}\n{proc.stderr}")


def _wait_health(base_url: str, timeout_s: float = 30.0) -> float:
    """
    Wait until GET /health returns 200.

    Returns elapsed seconds waited.
    """

    t0 = _now()
    deadline = t0 + float(timeout_s)
    while _now() < deadline:
        try:
            r = requests.get(f"{base_url}/health", timeout=1.0)
            if r.status_code == 200:
                return _now() - t0
        except Exception:
            pass
        _sleep(0.2)
    raise TimeoutError(f"health check timeout after {timeout_s}s: {base_url}/health")


def _kill_process(proc: subprocess.Popen, *, name: str, timeout_s: float = 8.0) -> None:
    if proc.poll() is not None:
        return
    try:
        proc.send_signal(signal.SIGTERM)
    except Exception:
        pass
    t0 = _now()
    while _now() - t0 < float(timeout_s):
        if proc.poll() is not None:
            return
        _sleep(0.1)
    try:
        proc.kill()
    except Exception:
        pass


def _parse_case(raw: str) -> Tuple[str, str]:
    """
    Parse a case string like: "github:torvalds" or "scholar:ZUeyIxMAAAAJ".
    """

    if ":" not in raw:
        raise ValueError(f"invalid case: {raw} (expected <source>:<content>)")
    source, content = raw.split(":", 1)
    source = source.strip().lower()
    content = content.strip()
    if not source or not content:
        raise ValueError(f"invalid case: {raw} (empty source/content)")
    return source, content


def _iter_sse_events(resp: requests.Response) -> Iterable[Dict[str, Any]]:
    for line in resp.iter_lines(decode_unicode=True):
        if not line:
            continue
        if not line.startswith("data:"):
            continue
        raw = line[len("data:") :].strip()
        if not raw:
            continue
        try:
            yield json.loads(raw)
        except Exception:
            continue


@dataclass
class BenchResult:
    env_name: str
    executor_mode: str
    source: str
    content: str
    base_url: str
    db_url: str
    job_id: str
    http: Dict[str, Any]
    milestones_ms: Dict[str, Any]
    timing_events: List[Dict[str, Any]]
    terminal_event_type: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "env": self.env_name,
            "executor_mode": self.executor_mode,
            "source": self.source,
            "content": self.content,
            "base_url": self.base_url,
            "db_url": self.db_url,
            "job_id": self.job_id,
            "terminal_event_type": self.terminal_event_type,
            "http": self.http,
            "milestones_ms": self.milestones_ms,
            "timing_events": self.timing_events,
        }


def _run_one_case(
    *,
    base_url: str,
    source: str,
    content: str,
    user_id: str,
    timeout_s: float,
    db_url_hint: str = "",
    force_refresh: bool = False,
) -> BenchResult:
    headers = {"X-User-ID": user_id, "Content-Type": "application/json"}

    # POST /api/analyze
    t_post0 = _now()
    payload: Dict[str, Any] = {"source": source, "mode": "async", "input": {"content": content}}
    if force_refresh:
        payload["options"] = {"force_refresh": True}

    r = requests.post(
        f"{base_url}/api/analyze",
        headers=headers,
        json=payload,
        timeout=30.0,
    )
    post_ms = (_now() - t_post0) * 1000.0
    r.raise_for_status()
    body = r.json() or {}
    if body.get("needs_confirmation"):
        raise RuntimeError(f"case needs confirmation; provide stable id/login/url: {body}")
    if not body.get("success"):
        raise RuntimeError(f"analyze failed: {body}")
    job_id = str(body.get("job_id") or "")
    if not job_id:
        raise RuntimeError(f"missing job_id: {body}")

    # GET snapshot once (baseline card states)
    t_get0 = _now()
    snap = requests.get(f"{base_url}/api/analyze/jobs/{job_id}", headers=headers, timeout=15.0)
    get_ms = (_now() - t_get0) * 1000.0
    snap.raise_for_status()

    # SSE stream
    stream_url = f"{base_url}/api/analyze/jobs/{job_id}/stream?after=0"
    t_sse0 = _now()
    resp = requests.get(stream_url, headers=headers, stream=True, timeout=30.0)
    resp.raise_for_status()

    milestones: Dict[str, Any] = {
        "ttfb_sse_ms": None,
        "first_event_ms": None,
        "first_card_completed_ms": None,
        "first_card_append_ms": None,
        "terminal_ms": None,
    }
    timing_events: List[Dict[str, Any]] = []

    first_event_at: Optional[float] = None
    terminal_event_type = ""

    # Per-card first occurrences
    first_append_by_card: Dict[str, float] = {}
    first_completed_by_card: Dict[str, float] = {}
    card_duration_ms: Dict[str, Any] = {}

    deadline = _now() + float(timeout_s)

    for ev in _iter_sse_events(resp):
        now = _now()
        if milestones["ttfb_sse_ms"] is None:
            milestones["ttfb_sse_ms"] = (now - t_sse0) * 1000.0

        et = str(ev.get("event_type") or "")
        payload = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}

        if first_event_at is None:
            first_event_at = now
            milestones["first_event_ms"] = (now - t_post0) * 1000.0

        if et == "card.append":
            card = str(payload.get("card") or "")
            if card and card not in first_append_by_card:
                first_append_by_card[card] = now
                if milestones["first_card_append_ms"] is None:
                    milestones["first_card_append_ms"] = (now - t_post0) * 1000.0

        if et == "card.completed":
            card = str(payload.get("card") or "")
            if card and card not in first_completed_by_card:
                first_completed_by_card[card] = now
                if milestones["first_card_completed_ms"] is None:
                    milestones["first_card_completed_ms"] = (now - t_post0) * 1000.0
            timing = payload.get("timing") if isinstance(payload.get("timing"), dict) else {}
            if card and "duration_ms" in timing and card not in card_duration_ms:
                card_duration_ms[card] = timing.get("duration_ms")

        if et == "card.progress":
            step = str(payload.get("step") or "")
            data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
            if step.startswith("timing.") or str(data.get("kind") or "") == "timing":
                rec: Dict[str, Any] = {
                    "seq": payload.get("seq"),
                    "card": payload.get("card"),
                    "step": step,
                    "duration_ms": data.get("duration_ms"),
                    "fetch_ms": data.get("fetch_ms"),
                    "parse_ms": data.get("parse_ms"),
                    "stage": data.get("stage"),
                    "page_idx": data.get("page_idx"),
                    "cstart": data.get("cstart"),
                    "ok": data.get("ok"),
                    "message": payload.get("message"),
                }
                timing_events.append(rec)

        if et in ("job.completed", "job.failed", "job.cancelled"):
            terminal_event_type = et
            milestones["terminal_ms"] = (now - t_post0) * 1000.0
            break

        if now >= deadline:
            terminal_event_type = "timeout"
            break

    # Make per-card milestones easier to read in JSON
    card_milestones: Dict[str, Any] = {
        "first_append_ms_by_card": {k: (v - t_post0) * 1000.0 for k, v in sorted(first_append_by_card.items())},
        "first_completed_ms_by_card": {k: (v - t_post0) * 1000.0 for k, v in sorted(first_completed_by_card.items())},
        "card_duration_ms_by_card": {k: card_duration_ms[k] for k in sorted(card_duration_ms.keys())},
    }
    milestones.update(card_milestones)

    http = {
        "post_analyze_ms": post_ms,
        "get_job_ms": get_ms,
        "stream_url": stream_url,
    }

    return BenchResult(
        env_name="",
        executor_mode="",
        source=source,
        content=content,
        base_url=base_url,
        db_url=str(db_url_hint or os.getenv("DINQ_DB_URL") or os.getenv("DATABASE_URL") or os.getenv("DB_URL") or ""),
        job_id=job_id,
        http=http,
        milestones_ms=milestones,
        timing_events=timing_events,
        terminal_event_type=terminal_event_type,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark DINQ unified analysis API (local)")
    parser.add_argument("--base-url", default="", help="Benchmark an existing server (no local spawn)")
    parser.add_argument("--label", default="", help="Label for --base-url runs")
    parser.add_argument("--modes", nargs="+", default=["inprocess", "external"], help="Executor modes to test")
    parser.add_argument("--cases", nargs="+", required=True, help="Cases: <source>:<content> ...")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host for local server")
    parser.add_argument("--port", type=int, default=18080, help="Base port; each mode uses port+index")
    parser.add_argument("--user-id", default="bench_user", help="X-User-ID header value")
    parser.add_argument("--timeout", type=float, default=120.0, help="Per job stream timeout (seconds)")
    parser.add_argument("--runner-max-workers", type=int, default=4, help="Runner max workers (external mode)")
    parser.add_argument("--runner-poll-interval", type=float, default=0.5, help="Runner DB poll interval (seconds)")
    parser.add_argument("--warmup-sleep", type=float, default=0.0, help="Sleep after starting runner (seconds)")
    parser.add_argument("--force-refresh", action="store_true", help="Send options.force_refresh=true in POST /api/analyze")
    parser.add_argument("--db-url", default="", help="Optional DB URL override (default: sqlite in .local/)")
    parser.add_argument("--out", default="", help="Write JSONL results to this path (optional)")
    args = parser.parse_args()

    modes = [str(m).strip().lower() for m in (args.modes or []) if str(m).strip()]
    cases = [_parse_case(c) for c in (args.cases or [])]

    log_dir = REPO_ROOT / ".local" / "bench_logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    out_fp = None
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_fp = out_path.open("w", encoding="utf-8")

    results: List[Dict[str, Any]] = []

    if args.base_url.strip():
        base_url = str(args.base_url).strip().rstrip("/")
        env_name = str(args.label or "target").strip() or "target"
        # Best-effort readiness check (do not wait forever).
        try:
            wait_s = _wait_health(base_url, timeout_s=10.0)
        except Exception:
            wait_s = 0.0

        for source, content in cases:
            res = _run_one_case(
                base_url=base_url,
                source=source,
                content=content,
                user_id=str(args.user_id),
                timeout_s=float(args.timeout),
                db_url_hint=str(args.db_url or ""),
                force_refresh=bool(args.force_refresh),
            )
            d = res.as_dict()
            d["env"] = env_name
            d["executor_mode"] = "unknown"
            d["db_url"] = str(args.db_url or "")
            d["http"]["health_wait_ms"] = wait_s * 1000.0
            results.append(d)
            line = json.dumps(d, ensure_ascii=False)
            print(line)
            if out_fp:
                out_fp.write(line + "\n")
                out_fp.flush()

        if out_fp:
            out_fp.close()

        print("\n== summary ==", file=sys.stderr)
        for r in results:
            print(
                f"{r['env']:>9} {r['source']:<10} post={r['http']['post_analyze_ms']:.0f}ms "
                f"ttfb_sse={r['milestones_ms'].get('ttfb_sse_ms') or 0:.0f}ms "
                f"terminal={r['milestones_ms'].get('terminal_ms') or 0:.0f}ms "
                f"({r['terminal_event_type']})",
                file=sys.stderr,
            )
        return

    for idx, mode in enumerate(modes):
        env_name = f"{mode}"
        port = int(args.port) + idx
        base_url = f"http://{args.host}:{port}"

        db_url = args.db_url.strip()
        if not db_url:
            db_path = (REPO_ROOT / ".local" / f"bench_{mode}.db").resolve()
            db_path.parent.mkdir(parents=True, exist_ok=True)
            db_url = f"sqlite:///{db_path}"

        env = os.environ.copy()
        env["DINQ_DB_URL"] = db_url
        env["FLASK_ENV"] = "production" if mode == "external" else "development"
        env["DINQ_ENV"] = env["FLASK_ENV"]
        env["AXIOM_ENABLED"] = "false"

        if mode == "external":
            # Be explicit: env files may set DINQ_EXECUTOR_MODE; ensure API stays HTTP-only here.
            env["DINQ_EXECUTOR_MODE"] = "external"
        else:
            env["DINQ_EXECUTOR_MODE"] = "inprocess"

        # Ensure tables exist for SQLite DBs.
        if _is_sqlite_url(db_url):
            _init_sqlite_tables(env)

        api_log_path = log_dir / f"api_{mode}.log"
        runner_log_path = log_dir / f"runner_{mode}.log"
        api_log = api_log_path.open("w", encoding="utf-8")
        runner_log = runner_log_path.open("w", encoding="utf-8")

        api_proc = subprocess.Popen(
            [sys.executable, "-u", "new_server.py", "--host", args.host, "--port", str(port)],
            cwd=str(REPO_ROOT),
            env=env,
            stdout=api_log,
            stderr=subprocess.STDOUT,
        )

        runner_proc = None
        try:
            wait_s = _wait_health(base_url, timeout_s=40.0)

            if mode == "external":
                runner_env = dict(env)
                runner_env["DINQ_EXECUTOR_MODE"] = "runner"
                runner_proc = subprocess.Popen(
                    [
                        sys.executable,
                        "-u",
                        "new_runner.py",
                        "--max-workers",
                        str(int(args.runner_max_workers)),
                        "--poll-interval",
                        str(float(args.runner_poll_interval)),
                    ],
                    cwd=str(REPO_ROOT),
                    env=runner_env,
                    stdout=runner_log,
                    stderr=subprocess.STDOUT,
                )
                if float(args.warmup_sleep or 0.0) > 0:
                    _sleep(float(args.warmup_sleep))

            for source, content in cases:
                res = _run_one_case(
                    base_url=base_url,
                    source=source,
                    content=content,
                    user_id=str(args.user_id),
                    timeout_s=float(args.timeout),
                    db_url_hint=db_url,
                    force_refresh=bool(args.force_refresh),
                )
                d = res.as_dict()
                d["env"] = env_name
                d["executor_mode"] = mode
                d["db_url"] = db_url
                d["http"]["health_wait_ms"] = wait_s * 1000.0
                results.append(d)
                line = json.dumps(d, ensure_ascii=False)
                print(line)
                if out_fp:
                    out_fp.write(line + "\n")
                    out_fp.flush()

        finally:
            if runner_proc is not None:
                _kill_process(runner_proc, name="runner")
            _kill_process(api_proc, name="api")
            try:
                api_log.close()
            except Exception:
                pass
            try:
                runner_log.close()
            except Exception:
                pass

    if out_fp:
        out_fp.close()

    # Compact summary to stderr for quick scanning.
    print("\n== summary ==", file=sys.stderr)
    for r in results:
        print(
            f"{r['env']:>9} {r['source']:<10} post={r['http']['post_analyze_ms']:.0f}ms "
            f"ttfb_sse={r['milestones_ms'].get('ttfb_sse_ms') or 0:.0f}ms "
            f"terminal={r['milestones_ms'].get('terminal_ms') or 0:.0f}ms "
            f"({r['terminal_event_type']})",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
