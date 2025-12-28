#!/usr/bin/env python3
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
from typing import Any, Dict, Optional, Tuple


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports" / "online_bench"


def _enabled(name: str) -> bool:
    return (os.getenv(name, "") or "").strip().lower() in ("1", "true", "yes", "on")


def _present(*names: str) -> bool:
    for n in names:
        if (os.getenv(n, "") or "").strip():
            return True
    return False


def _now_ts() -> str:
    return time.strftime("%Y%m%d_%H%M%S", time.localtime())


def _run(cmd: list[str], *, timeout: int = 10) -> Tuple[int, str]:
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=timeout)
        return 0, out
    except subprocess.CalledProcessError as e:
        return int(e.returncode), str(e.output or "")
    except Exception as e:  # noqa: BLE001
        return 1, str(e)


def _wait_health(base_url: str, *, timeout_seconds: int = 60) -> None:
    import requests  # type: ignore

    deadline = time.time() + timeout_seconds
    last_err: Optional[str] = None
    while time.time() < deadline:
        try:
            resp = requests.get(f"{base_url}/health", timeout=3)
            if resp.status_code == 200:
                return
            last_err = f"status={resp.status_code} body={resp.text[:200]}"
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
        time.sleep(1)
    raise RuntimeError(f"server not ready: {last_err}")


@dataclass
class BenchResult:
    name: str
    ok: bool
    status_code: int
    elapsed_seconds: float
    ttfb_seconds: Optional[float] = None
    time_to_end_seconds: Optional[float] = None
    events_total: int = 0
    events_by_type: Dict[str, int] = None  # type: ignore
    last_progress: Optional[float] = None
    first_error: Optional[Dict[str, Any]] = None
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "status_code": self.status_code,
            "elapsed_seconds": self.elapsed_seconds,
            "ttfb_seconds": self.ttfb_seconds,
            "time_to_end_seconds": self.time_to_end_seconds,
            "events_total": self.events_total,
            "events_by_type": self.events_by_type or {},
            "last_progress": self.last_progress,
            "first_error": self.first_error,
            "note": self.note,
        }


def _bench_sse(
    *,
    name: str,
    url: str,
    json_body: Dict[str, Any],
    headers: Dict[str, str],
    max_seconds: int,
    stop_on_pkdata: bool = False,
) -> BenchResult:
    import requests  # type: ignore

    started = time.time()
    events_by_type: Dict[str, int] = {}
    events_total = 0
    last_progress: Optional[float] = None
    ttfb: Optional[float] = None
    time_to_end: Optional[float] = None
    first_error: Optional[Dict[str, Any]] = None

    resp = requests.post(url, headers=headers, json=json_body, stream=True, timeout=max_seconds)
    status_code = resp.status_code

    try:
        if status_code != 200:
            return BenchResult(
                name=name,
                ok=False,
                status_code=status_code,
                elapsed_seconds=time.time() - started,
                note=f"non-200: {status_code}",
            )

        for raw_line in resp.iter_lines(decode_unicode=True):
            if raw_line is None:
                continue
            line = raw_line.strip()
            if not line or not line.startswith("data: "):
                continue

            if ttfb is None:
                ttfb = time.time() - started

            payload_text = line[len("data: ") :]
            try:
                payload = json.loads(payload_text)
            except Exception:  # noqa: BLE001
                continue

            events_total += 1
            et = payload.get("event_type") or payload.get("type") or "unknown"
            et = str(et)
            events_by_type[et] = events_by_type.get(et, 0) + 1

            p = payload.get("progress")
            if p is not None:
                try:
                    last_progress = float(p)
                except (TypeError, ValueError):
                    pass

            if stop_on_pkdata:
                if payload.get("type") == "pkData" or payload.get("step") == "pk_result":
                    time_to_end = time.time() - started
                    break

            if payload.get("event_type") == "error" and first_error is None:
                error_payload = payload.get("payload")
                if isinstance(error_payload, dict):
                    first_error = {
                        "code": error_payload.get("code"),
                        "message": error_payload.get("message") or payload.get("message"),
                        "retryable": error_payload.get("retryable"),
                        "detail": error_payload.get("detail"),
                        "step": payload.get("step"),
                    }
                else:
                    first_error = {"message": payload.get("message"), "step": payload.get("step")}

            if payload.get("event_type") == "end":
                time_to_end = time.time() - started
                break

            if time.time() - started > max_seconds:
                break

        ok = bool(events_total)
        return BenchResult(
            name=name,
            ok=ok,
            status_code=status_code,
            elapsed_seconds=time.time() - started,
            ttfb_seconds=ttfb,
            time_to_end_seconds=time_to_end,
            events_total=events_total,
            events_by_type=events_by_type,
            last_progress=last_progress,
            first_error=first_error,
            note=None if ok else "no events",
        )
    finally:
        try:
            resp.close()
        except Exception:  # noqa: BLE001
            pass


def _bench_http_get(*, name: str, url: str, timeout_seconds: int = 10) -> BenchResult:
    import requests  # type: ignore

    started = time.time()
    resp = requests.get(url, timeout=timeout_seconds)
    elapsed = time.time() - started
    ok = resp.status_code == 200
    return BenchResult(name=name, ok=ok, status_code=resp.status_code, elapsed_seconds=elapsed, note=None)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--max-seconds", type=int, default=180)
    args = parser.parse_args()

    base_url = f"http://{args.host}:{args.port}".rstrip("/")

    # Load .env.* (so local runs work without manual export).
    try:
        from server.config.env_loader import load_environment_variables

        load_environment_variables(log_dinq_vars=False)
    except Exception:
        pass

    # Start server in background
    env = os.environ.copy()
    env.setdefault("DINQ_AUTH_BYPASS", "true")
    env.setdefault("AXIOM_ENABLED", "false")
    env.setdefault("FLASK_ENV", env.get("DINQ_ENV", "test"))

    server_log = Path("/tmp/dinq_online_bench_server.log")
    server_cmd = [sys.executable, "-m", "server.app", "--host", args.host, "--port", str(args.port)]
    proc = subprocess.Popen(server_cmd, cwd=str(ROOT), env=env, stdout=server_log.open("w"), stderr=subprocess.STDOUT)

    try:
        _wait_health(base_url, timeout_seconds=60)

        results: list[BenchResult] = []
        results.append(_bench_http_get(name="health", url=f"{base_url}/health"))

        # GitHub (requires token)
        if _present("GITHUB_TOKEN"):
            results.append(_bench_http_get(name="github_health", url=f"{base_url}/api/github/health", timeout_seconds=15))
            results.append(
                _bench_sse(
                    name="github_analyze_stream",
                    url=f"{base_url}/api/github/analyze-stream",
                    headers={
                        "Content-Type": "application/json",
                        "Userid": "bench_user",
                        "Accept": "text/event-stream",
                    },
                    json_body={"username": "octocat"},
                    max_seconds=min(args.max_seconds, 120),
                )
            )
        else:
            results.append(
                BenchResult(
                    name="github_analyze_stream",
                    ok=True,
                    status_code=0,
                    elapsed_seconds=0.0,
                    note="skipped (GITHUB_TOKEN not set)",
                )
            )

        # Scholar stream (optionally; external website, may be unstable)
        if _enabled("DINQ_SMOKE_SCHOLAR"):
            results.append(
                _bench_sse(
                    name="scholar_stream",
                    url=f"{base_url}/api/stream",
                    headers={
                        "Content-Type": "application/json",
                        "Userid": "bench_user",
                        "Accept": "text/event-stream",
                    },
                    json_body={"query": "Y-ql3zMAAAAJ"},
                    max_seconds=args.max_seconds,
                )
            )
        else:
            results.append(
                BenchResult(
                    name="scholar_stream",
                    ok=True,
                    status_code=0,
                    elapsed_seconds=0.0,
                    note="skipped (DINQ_SMOKE_SCHOLAR not enabled)",
                )
            )

        # Scholar PK (very heavy; requires multiple keys)
        if _enabled("DINQ_SMOKE_SCHOLAR_PK") and _present("KIMI_API_KEY") and _present("OPENROUTER_API_KEY", "OPENROUTER_KEY", "GENERIC_OPENROUTER_API_KEY"):
            results.append(
                _bench_sse(
                    name="scholar_pk",
                    url=f"{base_url}/api/scholar-pk",
                    headers={
                        "Content-Type": "application/json",
                        "Userid": "bench_user",
                        "Accept": "text/event-stream",
                    },
                    json_body={"researcher1": "Y-ql3zMAAAAJ", "researcher2": "ZUeyIxMAAAAJ"},
                    max_seconds=max(args.max_seconds, 240),
                    stop_on_pkdata=True,
                )
            )
        else:
            results.append(
                BenchResult(
                    name="scholar_pk",
                    ok=True,
                    status_code=0,
                    elapsed_seconds=0.0,
                    note="skipped (DINQ_SMOKE_SCHOLAR_PK/KIMI/OPENROUTER not enabled)",
                )
            )

        report = {
            "base_url": base_url,
            "timestamp": _now_ts(),
            "git_sha": _run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], timeout=5)[1].strip(),
            "results": [r.to_dict() for r in results],
        }

        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = REPORT_DIR / f"{report['timestamp']}.json"
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        print(str(out_path))
        return 0
    finally:
        try:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=10)
        except Exception:  # noqa: BLE001
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass


if __name__ == "__main__":
    raise SystemExit(main())
