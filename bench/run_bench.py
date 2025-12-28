#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Case:
    name: str
    source: str
    content: str
    options: dict[str, Any]
    tags: list[str]


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _http_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    body: Optional[dict[str, Any]] = None,
    timeout_s: int = 60,
) -> dict[str, Any]:
    data = None
    if body is not None:
        data = _json_dumps(body).encode("utf-8")
    req = Request(url=url, method=method, data=data)
    for k, v in headers.items():
        req.add_header(k, v)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
    except HTTPError as e:
        raw = ""
        try:
            raw = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code} {e.reason}: {raw[:500]}") from e
    except URLError as e:
        raise RuntimeError(f"Request failed: {e}") from e


def _wait_health(base_url: str, *, timeout_s: int = 45) -> None:
    deadline = time.monotonic() + timeout_s
    last_err: Optional[str] = None
    while time.monotonic() < deadline:
        try:
            out = _http_json("GET", f"{base_url}/health", headers={}, timeout_s=3)
            if isinstance(out, dict) and out.get("status") == "ok":
                return
        except Exception as e:
            last_err = str(e)
        time.sleep(0.3)
    raise RuntimeError(f"Server not healthy at {base_url}/health (last_err={last_err})")


def _sqlite_wall_time_seconds(db_path: Path, job_id: str) -> Optional[float]:
    if not db_path.exists():
        return None
    try:
        with sqlite3.connect(str(db_path)) as conn:
            row = conn.execute(
                "select min(created_at), max(created_at) from job_events where job_id = ?",
                (job_id,),
            ).fetchone()
            if not row or not row[0] or not row[1]:
                return None
            t0 = dt.datetime.fromisoformat(str(row[0]))
            t1 = dt.datetime.fromisoformat(str(row[1]))
            return max(0.0, (t1 - t0).total_seconds())
    except Exception:
        return None


def _coerce_has_data(val: Any) -> bool:
    if val is None:
        return False
    if isinstance(val, (list, dict, set, tuple)):
        return len(val) > 0
    if isinstance(val, str):
        return len(val.strip()) > 0
    return True


def _parse_sse(path: Path) -> dict[str, Any]:
    cards: dict[str, dict[str, Any]] = {}
    github_timing: dict[str, int] = {}
    linkedin_timing: dict[str, int] = {}
    scholar_timings: list[dict[str, Any]] = []
    job_terminal: Optional[dict[str, Any]] = None

    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip("\n")
            if not line.startswith("data: "):
                continue
            payload_raw = line[len("data: ") :].strip()
            if not payload_raw:
                continue
            try:
                evt = json.loads(payload_raw)
            except Exception:
                continue

            et = evt.get("event_type")
            p = evt.get("payload") or {}

            if et in ("job.completed", "job.failed") and isinstance(p, dict):
                job_terminal = p
                continue

            if not isinstance(p, dict):
                continue

            if et == "card.completed":
                card = str(p.get("card") or "")
                cards[card] = {
                    "card": card,
                    "internal": bool(p.get("internal")),
                    "status": "completed",
                    "duration_ms": (p.get("timing") or {}).get("duration_ms"),
                }
                continue

            if et == "card.failed":
                card = str(p.get("card") or "")
                cards[card] = {
                    "card": card,
                    "internal": bool(p.get("internal")),
                    "status": "failed",
                    "duration_ms": (p.get("timing") or {}).get("duration_ms"),
                    "error": p.get("error"),
                }
                continue

            if et != "card.progress":
                continue

            card = p.get("card")
            step = p.get("step")
            data = p.get("data") or {}

            if card == "resource.github.data" and isinstance(step, str) and step.startswith("timing.github."):
                name = step.replace("timing.github.", "", 1)
                dur = data.get("duration_ms") if isinstance(data, dict) else None
                if isinstance(dur, int):
                    github_timing[name] = dur
                continue

            if card == "resource.linkedin.raw_profile" and isinstance(step, str) and step.startswith("timing.linkedin."):
                name = step.replace("timing.linkedin.", "", 1)
                dur = data.get("duration_ms") if isinstance(data, dict) else None
                if isinstance(dur, int):
                    linkedin_timing[name] = dur
                continue

            if card == "resource.scholar.base" and isinstance(data, dict) and data.get("kind") == "timing":
                scholar_timings.append(data)

    return {
        "job_terminal": job_terminal,
        "cards": cards,
        "resource_breakdown": {
            "github": github_timing,
            "linkedin": linkedin_timing,
            "scholar": scholar_timings,
        },
    }


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _ensure_tables(db_url: str) -> None:
    env = os.environ.copy()
    env["DINQ_DB_URL"] = db_url
    cmd = [
        sys.executable,
        "-c",
        "from server.config.env_loader import load_environment_variables; "
        "load_environment_variables(log_dinq_vars=False); "
        "from src.utils.db_utils import create_tables; "
        "create_tables()",
    ]
    subprocess.run(cmd, cwd=str(REPO_ROOT), env=env, check=True)


def _start_server(*, host: str, port: int, db_url: str, log_path: Path) -> subprocess.Popen[bytes]:
    env = os.environ.copy()
    env["DINQ_DB_URL"] = db_url
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "ab", buffering=0)  # noqa: SIM115
    return subprocess.Popen(
        [sys.executable, "new_server.py", "--host", host, "--port", str(port)],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )


def _stop_server(proc: subprocess.Popen[bytes], *, timeout_s: int = 10) -> None:
    if proc.poll() is not None:
        return
    try:
        proc.send_signal(signal.SIGTERM)
    except Exception:
        return
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return
        time.sleep(0.1)
    try:
        proc.kill()
    except Exception:
        pass


def _curl_sse(*, stream_url: str, user_id: str, out_path: Path, timeout_s: int) -> tuple[float, dict[str, Any]]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    first_screen: dict[str, Any] = {
        # Client-side timings (seconds since SSE connection start).
        "tt_first_event_s": None,
        "tt_first_business_card_s": None,
        "tt_profile_completed_s": None,
        "tt_repos_append_s": None,
        "tt_papers_append_s": None,
        "tt_first_delta_s": None,
        "tt_job_completed_s": None,
        # Sequence numbers for debugging (best-effort).
        "first_event_seq": None,
        "first_business_card_seq": None,
        "profile_seq": None,
        "repos_append_seq": None,
        "papers_append_seq": None,
        "first_delta_seq": None,
        "job_completed_seq": None,
    }

    with out_path.open("wb") as f:
        proc = subprocess.Popen(  # noqa: S603
            [
                "curl",
                "-sS",
                "-N",
                "--max-time",
                str(int(timeout_s)),
                "-H",
                f"X-User-ID: {user_id}",
                stream_url,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        try:
            assert proc.stdout is not None
            while True:
                line = proc.stdout.readline()
                if not line:
                    break
                f.write(line)

                # Timing markers (client receive-time).
                now_s = max(0.0, time.monotonic() - started)
                if line.startswith(b"data: "):
                    # First event marker.
                    if first_screen.get("tt_first_event_s") is None:
                        first_screen["tt_first_event_s"] = round(now_s, 3)

                    payload_raw = line[len(b"data: ") :].strip()
                    if not payload_raw:
                        continue
                    try:
                        evt = json.loads(payload_raw.decode("utf-8", errors="replace"))
                    except Exception:
                        continue

                    et = evt.get("event_type")
                    p = evt.get("payload") or {}
                    seq = None
                    if isinstance(p, dict):
                        seq = p.get("seq")

                    # Prefer to store a seq for the first event marker.
                    if first_screen.get("first_event_seq") is None and seq is not None:
                        first_screen["first_event_seq"] = seq

                    if et == "card.delta" and first_screen.get("tt_first_delta_s") is None:
                        first_screen["tt_first_delta_s"] = round(now_s, 3)
                        first_screen["first_delta_seq"] = seq
                        continue

                    if et == "card.append" and isinstance(p, dict):
                        card = str(p.get("card") or "")
                        if card == "repos" and first_screen.get("tt_repos_append_s") is None:
                            first_screen["tt_repos_append_s"] = round(now_s, 3)
                            first_screen["repos_append_seq"] = seq
                        if card == "papers" and first_screen.get("tt_papers_append_s") is None:
                            first_screen["tt_papers_append_s"] = round(now_s, 3)
                            first_screen["papers_append_seq"] = seq
                        continue

                    if et == "card.completed" and isinstance(p, dict):
                        card = str(p.get("card") or "")
                        internal = bool(p.get("internal"))
                        if not internal and first_screen.get("tt_first_business_card_s") is None:
                            first_screen["tt_first_business_card_s"] = round(now_s, 3)
                            first_screen["first_business_card_seq"] = seq
                        if card == "profile" and (not internal) and first_screen.get("tt_profile_completed_s") is None:
                            first_screen["tt_profile_completed_s"] = round(now_s, 3)
                            first_screen["profile_seq"] = seq
                        continue

                    if et in ("job.completed", "job.failed") and first_screen.get("tt_job_completed_s") is None:
                        first_screen["tt_job_completed_s"] = round(now_s, 3)
                        first_screen["job_completed_seq"] = seq
                        continue
        finally:
            try:
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    wall = max(0.0, time.monotonic() - started)
    return wall, first_screen


def _load_cases(samples_path: Path) -> list[Case]:
    raw = json.loads(samples_path.read_text(encoding="utf-8"))
    cases_raw = (raw.get("cases") if isinstance(raw, dict) else None) or []
    cases: list[Case] = []
    for c in cases_raw:
        if not isinstance(c, dict):
            continue
        cases.append(
            Case(
                name=str(c.get("name") or ""),
                source=str(c.get("source") or ""),
                content=str(c.get("content") or ""),
                options=(c.get("options") if isinstance(c.get("options"), dict) else {}) or {},
                tags=[str(x) for x in (c.get("tags") or []) if x is not None],
            )
        )
    return cases


def _make_db_url(db_path: Path) -> str:
    # SQLAlchemy sqlite absolute path form: sqlite:////abs/path
    return f"sqlite:////{db_path.as_posix().lstrip('/')}"


def _render_markdown_report(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Analyze Bench Report")
    lines.append("")
    lines.append(f"- generated_at: `{report.get('generated_at')}`")
    lines.append(f"- base_url: `{report.get('base_url')}`")
    lines.append(f"- db_path: `{report.get('db_path')}`")
    lines.append("")

    for run in report.get("runs", []):
        lines.append(f"## {run.get('name')} ({run.get('source')}/{run.get('run_mode')})")
        lines.append("")
        lines.append(f"- job_id: `{run.get('job_id')}`")
        lines.append(f"- status: `{run.get('status')}`")
        if run.get("wall_time_db_s") is not None:
            lines.append(f"- wall_time_db_s: `{run.get('wall_time_db_s')}`")
        if run.get("wall_time_client_s") is not None:
            lines.append(f"- wall_time_client_s: `{run.get('wall_time_client_s')}`")

        fs = run.get("first_screen") or {}
        if isinstance(fs, dict) and fs:
            keys = [
                "tt_first_event_s",
                "tt_first_business_card_s",
                "tt_profile_completed_s",
                "tt_repos_append_s",
                "tt_papers_append_s",
                "tt_first_delta_s",
                "tt_job_completed_s",
            ]
            items = [(k, fs.get(k)) for k in keys if fs.get(k) is not None]
            if items:
                lines.append("")
                lines.append("First screen (client-side):")
                for k, v in items:
                    lines.append(f"- `{k}`: `{v}s`")

        slow = run.get("slow_cards") or []
        if slow:
            lines.append("")
            lines.append("Top slow cards:")
            for c in slow:
                lines.append(f"- `{c.get('card')}`: `{c.get('duration_ms')}ms` (internal={c.get('internal')})")

        empty = run.get("empty_business_cards") or []
        if empty:
            lines.append("")
            lines.append("Empty business cards (should not happen):")
            for c in empty:
                lines.append(f"- `{c}`")

        rb = run.get("resource_breakdown") or {}
        gh = rb.get("github") or {}
        li = rb.get("linkedin") or {}
        sch = rb.get("scholar") or []
        if gh or li or sch:
            lines.append("")
            lines.append("Resource breakdown:")
            if gh:
                lines.append("- GitHub timing.github.*:")
                for k, v in sorted(gh.items(), key=lambda kv: -int(kv[1])):
                    lines.append(f"  - `{k}`: `{v}ms`")
            if li:
                lines.append("- LinkedIn timing.linkedin.*:")
                for k, v in sorted(li.items(), key=lambda kv: -int(kv[1])):
                    lines.append(f"  - `{k}`: `{v}ms`")
            if sch:
                stage_totals: dict[str, int] = {}
                pages: list[dict[str, Any]] = []
                for item in sch:
                    if not isinstance(item, dict):
                        continue
                    stage = str(item.get("stage") or "")
                    dur = item.get("duration_ms")
                    if isinstance(dur, int) and stage:
                        stage_totals[stage] = stage_totals.get(stage, 0) + dur
                    if stage == "fetch_profile" and "page_idx" in item:
                        pages.append(item)
                if stage_totals:
                    lines.append("- Scholar stages (sum of emitted timings):")
                    for k, v in sorted(stage_totals.items(), key=lambda kv: -int(kv[1])):
                        lines.append(f"  - `{k}`: `{v}ms`")
                if pages:
                    lines.append("- Scholar fetch_profile pages:")
                    pages_sorted = sorted(pages, key=lambda x: int(x.get("page_idx") or 0))
                    for p in pages_sorted:
                        lines.append(
                            f"  - page={p.get('page_idx')} cstart={p.get('cstart')} "
                            f"dur={p.get('duration_ms')}ms fetch={p.get('fetch_ms')}ms parse={p.get('parse_ms')}ms"
                        )

        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Run local analyze benchmarks (sqlite) and generate a report.")
    ap.add_argument("--samples", default=str(REPO_ROOT / "bench/samples.json"), help="Path to samples.json")
    ap.add_argument("--only", action="append", default=[], help="Only run cases whose name contains this substring (repeatable)")
    ap.add_argument("--base-url", default="http://127.0.0.1:8090", help="Analyze server base URL")
    ap.add_argument("--user-id", default="local_test", help="X-User-ID header value")
    ap.add_argument("--db-path", default=str(REPO_ROOT / ".local/local_test.db"), help="sqlite DB path for wall-time reporting")
    ap.add_argument("--mode", choices=["cold", "warm", "both"], default="both", help="Benchmark mode")
    ap.add_argument("--repeat", type=int, default=1, help="Repeat each case N times")
    ap.add_argument("--timeout-s", type=int, default=1800, help="Per-job SSE max time (seconds)")
    ap.add_argument("--start-server", action="store_true", help="Start a local server for the run (recommended)")
    ap.add_argument("--host", default="127.0.0.1", help="Host for --start-server")
    ap.add_argument("--port", type=int, default=8091, help="Port for --start-server")
    ap.add_argument("--fresh-db", action="store_true", help="Create a fresh sqlite DB under output dir for a true cold run")
    ap.add_argument("--strict", action="store_true", help="Exit non-zero if any run failed or produced empty business cards")
    args = ap.parse_args()

    samples_path = Path(args.samples).resolve()
    if not samples_path.exists():
        raise SystemExit(f"samples not found: {samples_path}")

    cases = _load_cases(samples_path)
    if args.only:
        needles = [n.lower() for n in args.only]
        cases = [c for c in cases if any(n in c.name.lower() for n in needles)]
    if not cases:
        raise SystemExit("no cases to run (check --samples / --only)")

    now = dt.datetime.now(dt.UTC).strftime("%Y%m%d_%H%M%S")
    out_dir = (REPO_ROOT / ".local/bench/output" / now).resolve()
    (out_dir / "sse").mkdir(parents=True, exist_ok=True)
    (out_dir / "snapshot").mkdir(parents=True, exist_ok=True)

    base_url = str(args.base_url).rstrip("/")
    user_id = str(args.user_id)

    db_path = Path(args.db_path).resolve()
    if args.fresh_db:
        db_path = out_dir / "fresh.db"
    db_url = _make_db_url(db_path)

    server_proc: Optional[subprocess.Popen[bytes]] = None
    if args.start_server:
        base_url = f"http://{args.host}:{args.port}"
        _ensure_tables(db_url)
        server_log = out_dir / "server.log"
        server_proc = _start_server(host=args.host, port=args.port, db_url=db_url, log_path=server_log)
        try:
            _wait_health(base_url, timeout_s=45)
        except Exception:
            _stop_server(server_proc)
            raise

    run_modes = [args.mode] if args.mode in ("cold", "warm") else ["cold", "warm"]
    runs: list[dict[str, Any]] = []
    any_failed = False
    any_empty = False

    try:
        for case in cases:
            for rep in range(max(1, int(args.repeat))):
                for run_mode in run_modes:
                    run_name = case.name if rep == 0 else f"{case.name}__r{rep+1}"

                    options = dict(case.options or {})
                    options["force_refresh"] = bool(run_mode == "cold")

                    req_body = {
                        "source": case.source,
                        "mode": "async",
                        "input": {"content": case.content},
                        "options": options,
                    }
                    headers = {"X-User-ID": user_id}

                    run_out: dict[str, Any] = {
                        "name": run_name,
                        "source": case.source,
                        "content": case.content,
                        "run_mode": run_mode,
                        "options": options,
                    }

                    try:
                        created = _http_json("POST", f"{base_url}/api/analyze", headers=headers, body=req_body, timeout_s=60)
                    except Exception as e:
                        run_out["error"] = f"create_job_failed: {e}"
                        runs.append(run_out)
                        any_failed = True
                        print(f"[{case.source}/{run_mode}] {run_name}: ERROR create_job_failed")
                        continue

                    run_out["created"] = created
                    job_id = created.get("job_id")
                    run_out["job_id"] = job_id
                    run_out["needs_confirmation"] = bool(created.get("needs_confirmation"))

                    if run_out["needs_confirmation"] or not job_id:
                        runs.append(run_out)
                        print(f"[{case.source}/{run_mode}] {run_name}: needs_confirmation={run_out['needs_confirmation']}")
                        continue

                    sse_path = out_dir / "sse" / f"{job_id}.sse"
                    stream_url = f"{base_url}/api/analyze/jobs/{job_id}/stream?after=0"
                    wall_client_s, first_screen = _curl_sse(
                        stream_url=stream_url,
                        user_id=user_id,
                        out_path=sse_path,
                        timeout_s=int(args.timeout_s),
                    )

                    parsed = _parse_sse(sse_path)
                    run_out["wall_time_client_s"] = round(wall_client_s, 3)
                    run_out["first_screen"] = first_screen
                    run_out["resource_breakdown"] = parsed.get("resource_breakdown")
                    cards = list((parsed.get("cards") or {}).values()) if isinstance(parsed.get("cards"), dict) else []
                    run_out["cards"] = cards

                    try:
                        snapshot = _http_json("GET", f"{base_url}/api/analyze/jobs/{job_id}", headers=headers, timeout_s=60)
                        _write_json(out_dir / "snapshot" / f"{job_id}.json", snapshot)
                        run_out["snapshot_ok"] = True
                    except Exception as e:
                        snapshot = {}
                        run_out["snapshot_ok"] = False
                        run_out["snapshot_error"] = str(e)

                    wall_db_s = _sqlite_wall_time_seconds(db_path, str(job_id))
                    run_out["wall_time_db_s"] = round(wall_db_s, 3) if isinstance(wall_db_s, (int, float)) else None

                    status = None
                    jt = parsed.get("job_terminal") or {}
                    if isinstance(jt, dict):
                        status = jt.get("status")
                    if not status and isinstance(snapshot, dict):
                        status = (snapshot.get("job") or {}).get("status")
                    run_out["status"] = status or "unknown"

                    empty_cards: list[str] = []
                    if isinstance(snapshot, dict):
                        cards_obj = ((snapshot.get("job") or {}).get("cards") or {}) if isinstance(snapshot.get("job"), dict) else {}
                        if isinstance(cards_obj, dict):
                            for card_name, card_obj in cards_obj.items():
                                if not isinstance(card_obj, dict):
                                    continue
                                if bool(card_obj.get("internal")):
                                    continue
                                output = card_obj.get("output") or {}
                                data = output.get("data") if isinstance(output, dict) else None
                                if not _coerce_has_data(data):
                                    empty_cards.append(str(card_name))
                    run_out["empty_business_cards"] = empty_cards

                    if str(run_out["status"]).lower() == "failed":
                        any_failed = True
                    if empty_cards:
                        any_empty = True

                    slow_cards = sorted(
                        [c for c in cards if isinstance(c, dict) and isinstance(c.get("duration_ms"), int)],
                        key=lambda c: int(c.get("duration_ms") or 0),
                        reverse=True,
                    )[:6]
                    run_out["slow_cards"] = slow_cards

                    runs.append(run_out)

                    top = ", ".join([f"{c.get('card')}={c.get('duration_ms')}ms" for c in slow_cards[:3]])
                    wall = run_out.get("wall_time_db_s") or run_out.get("wall_time_client_s")
                    empty_note = f" empty={len(empty_cards)}" if empty_cards else ""
                    print(f"[{case.source}/{run_mode}] {run_name}: status={run_out['status']} wall={wall}s top={top}{empty_note}")

                    time.sleep(0.2)

        report = {
            "generated_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "base_url": base_url,
            "db_path": str(db_path),
            "samples": str(samples_path),
            "runs": runs,
        }
        _write_json(out_dir / "report.json", report)
        (out_dir / "report.md").write_text(_render_markdown_report(report), encoding="utf-8")

        print(f"\nReport written to: {out_dir}")
        if args.strict and (any_failed or any_empty):
            return 2
        return 0
    finally:
        if server_proc is not None:
            _stop_server(server_proc)


if __name__ == "__main__":
    raise SystemExit(main())
