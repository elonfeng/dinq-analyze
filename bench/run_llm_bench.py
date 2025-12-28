#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter

try:
    from json_repair import repair_json
except Exception:  # noqa: BLE001

    def repair_json(text: str) -> str:
        return text


REPO_ROOT = Path(__file__).resolve().parents[1]


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _iso_z(ts: dt.datetime) -> str:
    # Render as RFC3339-like "Z" for logs/files.
    return ts.isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class TaskCase:
    task: str
    expect_json: bool
    messages: list[dict[str, str]]
    temperature: float
    max_tokens: int
    timeout_s: float
    extra: dict[str, Any]


@dataclass(frozen=True)
class Route:
    provider: str
    model: str
    family: str

    def spec(self) -> str:
        p = str(self.provider or "").strip().lower()
        if not p or p == "openrouter":
            return f"openrouter:{self.model}"
        return f"{p}:{self.model}"


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _read_json(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    out = json.loads(raw)
    if not isinstance(out, dict):
        raise ValueError("samples must be a JSON object")
    return out


def _percentile(vals: list[float], p: float) -> Optional[float]:
    if not vals:
        return None
    if p <= 0:
        return float(min(vals))
    if p >= 100:
        return float(max(vals))
    xs = sorted(float(v) for v in vals)
    k = (len(xs) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    if f == c:
        return float(xs[f])
    d0 = xs[f] * (c - k)
    d1 = xs[c] * (k - f)
    return float(d0 + d1)


def _str_nonempty(x: Any) -> bool:
    return isinstance(x, str) and bool(x.strip())


def _dict(x: Any) -> dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _list(x: Any) -> list[Any]:
    return x if isinstance(x, list) else []


def _validate_github_best_pr(obj: Any) -> tuple[bool, str]:
    d = _dict(obj)
    required = ("repository", "url", "title", "additions", "deletions", "reason", "impact")
    for k in required:
        if k not in d:
            return False, f"missing:{k}"
    if not _str_nonempty(d.get("url")) or not _str_nonempty(d.get("title")):
        return False, "missing:url_or_title"
    if not _str_nonempty(d.get("repository")):
        return False, "missing:repository"
    try:
        int(d.get("additions") or 0)
        int(d.get("deletions") or 0)
    except Exception:
        return False, "invalid:additions_or_deletions"
    if not _str_nonempty(d.get("reason")):
        return False, "missing:reason"
    if not isinstance(d.get("impact"), str):
        return False, "invalid:impact"
    return True, "ok"


def _validate_linkedin_enrich_bundle(obj: Any) -> tuple[bool, str]:
    d = _dict(obj)
    for k in ("skills", "career", "work_experience_summary", "education_summary", "money", "summary"):
        if k not in d:
            return False, f"missing:{k}"
    skills = _dict(d.get("skills"))
    for k in ("industry_knowledge", "tools_technologies", "interpersonal_skills", "language"):
        v = skills.get(k)
        if not isinstance(v, list) or not any(isinstance(x, str) and x.strip() for x in v):
            return False, f"invalid:skills.{k}"
    money = _dict(d.get("money"))
    for k in ("level_us", "level_cn", "estimated_salary", "explanation"):
        if not isinstance(money.get(k), str):
            return False, f"invalid:money.{k}"
    yoe = _dict(money.get("years_of_experience"))
    if "years" not in yoe or "start_year" not in yoe or "calculation_basis" not in yoe:
        return False, "missing:money.years_of_experience"
    summary = _dict(d.get("summary"))
    if not isinstance(summary.get("about"), str):
        return False, "invalid:summary.about"
    tags = summary.get("personal_tags")
    if not isinstance(tags, list) or not all(isinstance(x, str) for x in tags):
        return False, "invalid:summary.personal_tags"
    if not isinstance(d.get("work_experience_summary"), str) or not isinstance(d.get("education_summary"), str):
        return False, "invalid:summaries"
    career = _dict(d.get("career"))
    if "development_advice" not in career or not isinstance(career.get("development_advice"), dict):
        return False, "invalid:career.development_advice"
    return True, "ok"


def _validate_github_enrich_bundle(obj: Any) -> tuple[bool, str]:
    d = _dict(obj)
    for k in ("description", "valuation_and_level", "role_model", "roast", "most_valuable_pull_request", "feature_project_tags"):
        if k not in d:
            return False, f"missing:{k}"
    if not _str_nonempty(d.get("description")):
        return False, "invalid:description"
    val = _dict(d.get("valuation_and_level"))
    for k in ("level", "salary_range", "total_compensation", "reasoning"):
        if not isinstance(val.get(k), str) or (k == "level" and not str(val.get(k)).strip()):
            return False, f"invalid:valuation_and_level.{k}"
    rm = _dict(d.get("role_model"))
    if not _str_nonempty(rm.get("name")):
        return False, "invalid:role_model.name"
    score = rm.get("similarity_score")
    try:
        score_f = float(score)
    except Exception:
        return False, "invalid:role_model.similarity_score"
    if score_f < 0.0 or score_f > 1.0:
        return False, "invalid:role_model.similarity_score_range"
    if not isinstance(rm.get("reason"), str):
        return False, "invalid:role_model.reason"
    if not _str_nonempty(d.get("roast")):
        return False, "invalid:roast"
    pr = _dict(d.get("most_valuable_pull_request"))
    for k in ("repository", "url", "title", "additions", "deletions", "reason", "impact"):
        if k not in pr:
            return False, f"invalid:most_valuable_pull_request.{k}"
    if not _str_nonempty(pr.get("url")) or not _str_nonempty(pr.get("title")):
        return False, "invalid:most_valuable_pull_request.url_or_title"
    try:
        int(pr.get("additions") or 0)
        int(pr.get("deletions") or 0)
    except Exception:
        return False, "invalid:most_valuable_pull_request.additions_or_deletions"
    tags = d.get("feature_project_tags")
    if not isinstance(tags, list) or not any(isinstance(x, str) and x.strip() for x in tags):
        return False, "invalid:feature_project_tags"
    return True, "ok"


def _validate_scholar_summary(text: str) -> tuple[bool, str]:
    markers = [
        "<!--section:overview-->",
        "<!--section:strengths-->",
        "<!--section:risks-->",
        "<!--section:questions-->",
    ]
    if not isinstance(text, str) or not text.strip():
        return False, "empty"
    pos = 0
    idxs: list[int] = []
    for m in markers:
        idx = text.find(m, pos)
        if idx < 0:
            return False, f"missing:{m}"
        # Must be on its own line.
        before = text[idx - 1] if idx > 0 else "\n"
        after = text[idx + len(m)] if idx + len(m) < len(text) else "\n"
        if before not in ("\n", "\r"):
            return False, f"marker_not_on_newline:{m}"
        if after not in ("\n", "\r"):
            return False, f"marker_not_terminated:{m}"
        pos = idx + len(m)
        idxs.append(idx)
    # Must not repeat markers.
    for m in markers:
        if text.count(m) != 1:
            return False, f"marker_repeated:{m}"
    # Sections must be non-empty.
    for i, m in enumerate(markers):
        start = idxs[i] + len(m)
        end = idxs[i + 1] if i + 1 < len(idxs) else len(text)
        content = text[start:end].strip()
        if not content:
            return False, f"empty_section:{m}"
    return True, "ok"


def _validate_scholar_level_fast(obj: Any) -> tuple[bool, str]:
    d = _dict(obj)
    for k in ("earnings", "level_cn", "level_us", "justification", "evaluation_bars", "years_of_experience"):
        if k not in d:
            return False, f"missing:{k}"
    for k in ("earnings", "level_cn", "level_us", "justification"):
        if not _str_nonempty(d.get(k)):
            return False, f"invalid:{k}"

    bars = _dict(d.get("evaluation_bars"))
    for k in ("depth_vs_breadth", "theory_vs_practice", "individual_vs_team"):
        item = _dict(bars.get(k))
        if "score" not in item or "explanation" not in item:
            return False, f"invalid:evaluation_bars.{k}"
        try:
            score = int(item.get("score") or 0)
        except Exception:
            return False, f"invalid:evaluation_bars.{k}.score"
        if score < 1 or score > 10:
            return False, f"invalid:evaluation_bars.{k}.score_range"
        if not _str_nonempty(item.get("explanation")):
            return False, f"invalid:evaluation_bars.{k}.explanation"

    yoe = _dict(d.get("years_of_experience"))
    for k in ("years", "start_year", "calculation_basis"):
        if k not in yoe:
            return False, f"missing:years_of_experience.{k}"
    try:
        years = int(yoe.get("years") or 0)
        start_year = int(yoe.get("start_year") or 0)
    except Exception:
        return False, "invalid:years_of_experience"
    if years < 0 or years > 60:
        return False, "invalid:years_of_experience.years_range"
    if start_year < 1950 or start_year > 2100:
        return False, "invalid:years_of_experience.start_year_range"
    if not _str_nonempty(yoe.get("calculation_basis")):
        return False, "invalid:years_of_experience.calculation_basis"
    return True, "ok"


_JSON_VALIDATORS: dict[str, Any] = {
    "github_enrich_bundle": _validate_github_enrich_bundle,
    "linkedin_enrich_bundle": _validate_linkedin_enrich_bundle,
    "github_best_pr": _validate_github_best_pr,
    "scholar_level_fast": _validate_scholar_level_fast,
}


def _parse_json_best_effort(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        try:
            repaired = repair_json(text)
            return json.loads(repaired)
        except Exception:
            return None


def _make_session(*, pool_max: int) -> requests.Session:
    sess = requests.Session()
    pool = max(4, min(int(pool_max), 256))
    try:
        sess.mount("https://", HTTPAdapter(pool_connections=pool, pool_maxsize=pool, max_retries=0))
        sess.mount("http://", HTTPAdapter(pool_connections=pool, pool_maxsize=pool, max_retries=0))
    except Exception:
        pass
    return sess


def _openrouter_key() -> str:
    # Align with server/config/api_keys.py aliases.
    return (os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_KEY") or os.getenv("GENERIC_OPENROUTER_API_KEY") or "").strip()


def _groq_key() -> str:
    return (os.getenv("GROQ_API_KEY") or "").strip()


def _post_chat(
    *,
    session: requests.Session,
    url: str,
    headers: dict[str, str],
    body: dict[str, Any],
    timeout_s: float,
) -> tuple[int, dict[str, Any]]:
    resp = session.post(url, headers=headers, json=body, timeout=max(1.0, float(timeout_s)))
    status = int(resp.status_code)
    try:
        data = resp.json() if resp.text else {}
    except Exception:
        data = {"_raw": resp.text[:2000]}
    return status, data if isinstance(data, dict) else {"_raw": data}


def _extract_text(resp_json: dict[str, Any]) -> str:
    choices = resp_json.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            msg = first.get("message")
            if isinstance(msg, dict):
                return str(msg.get("content") or "")
            # Some providers may return "text"
            if first.get("text") is not None:
                return str(first.get("text") or "")
    return ""


def _extract_usage(resp_json: dict[str, Any]) -> tuple[Optional[int], Optional[int]]:
    usage = resp_json.get("usage")
    if not isinstance(usage, dict):
        return None, None
    # OpenAI-style
    for k_in in ("prompt_tokens", "input_tokens"):
        if usage.get(k_in) is not None:
            try:
                tokens_in = int(usage.get(k_in) or 0)
                break
            except Exception:
                tokens_in = None
                break
    else:
        tokens_in = None
    for k_out in ("completion_tokens", "output_tokens"):
        if usage.get(k_out) is not None:
            try:
                tokens_out = int(usage.get(k_out) or 0)
                break
            except Exception:
                tokens_out = None
                break
    else:
        tokens_out = None
    return tokens_in, tokens_out


def _load_tasks(path: Path) -> list[TaskCase]:
    data = _read_json(path)
    defaults = data.get("defaults") if isinstance(data.get("defaults"), dict) else {}
    try:
        d_timeout = float(defaults.get("timeout_s", 45) or 45)
    except Exception:
        d_timeout = 45.0
    try:
        d_temp = float(defaults.get("temperature", 0.2) or 0.2)
    except Exception:
        d_temp = 0.2
    try:
        d_max_tokens = int(defaults.get("max_tokens", 900) or 900)
    except Exception:
        d_max_tokens = 900

    tasks: list[TaskCase] = []
    items = data.get("tasks")
    if not isinstance(items, list) or not items:
        raise ValueError("samples must include tasks[]")
    for item in items:
        if not isinstance(item, dict):
            continue
        task = str(item.get("task") or "").strip()
        if not task:
            continue
        expect_json = bool(item.get("expect_json"))
        messages = item.get("messages")
        if not isinstance(messages, list) or not messages:
            raise ValueError(f"task {task} missing messages")
        msgs: list[dict[str, str]] = []
        for m in messages:
            if not isinstance(m, dict):
                continue
            role = str(m.get("role") or "").strip()
            content = str(m.get("content") or "")
            if role not in ("system", "user", "assistant"):
                raise ValueError(f"task {task} invalid role: {role}")
            msgs.append({"role": role, "content": content})
        try:
            timeout_s = float(item.get("timeout_s") or d_timeout)
        except Exception:
            timeout_s = d_timeout
        try:
            temperature = float(item.get("temperature") if item.get("temperature") is not None else d_temp)
        except Exception:
            temperature = d_temp
        try:
            max_tokens = int(item.get("max_tokens") if item.get("max_tokens") is not None else d_max_tokens)
        except Exception:
            max_tokens = d_max_tokens
        extra = item.get("extra") if isinstance(item.get("extra"), dict) else {}
        tasks.append(
            TaskCase(
                task=task,
                expect_json=expect_json,
                messages=msgs,
                temperature=float(temperature),
                max_tokens=int(max_tokens),
                timeout_s=max(1.0, float(timeout_s)),
                extra=dict(extra),
            )
        )
    return tasks


def _default_routes() -> list[Route]:
    # Keep this list small and explicit; override via CLI flags.
    return [
        Route(provider="openrouter", model="google/gemini-2.5-flash", family="gemini-2.5-flash"),
        Route(provider="openrouter", model="google/gemini-2.5-flash-lite", family="gemini-2.5-flash"),
        Route(provider="openrouter", model="google/gemini-3-flash-preview", family="gemini-3-flash"),
        # Common Groq model ids (may vary by account/region; override if needed).
        Route(provider="groq", model="llama-3.1-70b-versatile", family="llama-3.1-70b"),
        Route(provider="groq", model="llama-3.1-8b-instant", family="llama-3.1-8b"),
        Route(provider="groq", model="mixtral-8x7b-32768", family="mixtral-8x7b"),
    ]


@dataclass
class Measurement:
    task: str
    provider: str
    model: str
    family: str
    run_idx: int
    total_ms: Optional[int]
    http_status: Optional[int]
    ok: bool
    error_type: str
    valid_json: bool
    schema_pass: bool
    schema_reason: str
    tokens_in: Optional[int]
    tokens_out: Optional[int]
    text_len: int
    text_preview: str


def _run_one(
    *,
    route: Route,
    case: TaskCase,
    run_idx: int,
    session_openrouter: requests.Session,
    session_groq: requests.Session,
    openrouter_url: str,
    groq_url: str,
) -> Measurement:
    provider = str(route.provider or "").strip().lower()
    model = str(route.model or "").strip()

    t0 = time.perf_counter()
    status: Optional[int] = None
    ok = False
    error_type = ""
    tokens_in = None
    tokens_out = None
    text = ""

    try:
        if provider in ("", "openrouter"):
            key = _openrouter_key()
            if not key:
                return Measurement(
                    task=case.task,
                    provider="openrouter",
                    model=model,
                    family=route.family,
                    run_idx=run_idx,
                    total_ms=None,
                    http_status=None,
                    ok=False,
                    error_type="missing_openrouter_key",
                    valid_json=False,
                    schema_pass=False,
                    schema_reason="no_key",
                    tokens_in=None,
                    tokens_out=None,
                    text_len=0,
                    text_preview="",
                )
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "HTTP-Referer": os.getenv("DINQ_HTTP_REFERER", "https://dinq.ai"),
            }
            body = {
                "model": model,
                "messages": case.messages,
                "temperature": float(case.temperature),
                "max_tokens": int(case.max_tokens),
                "stream": False,
            }
            if case.extra:
                body.update(case.extra)
            status, data = _post_chat(session=session_openrouter, url=openrouter_url, headers=headers, body=body, timeout_s=case.timeout_s)
            if status != 200:
                error_type = f"http_{status}"
            else:
                ok = True
                text = _extract_text(data)
                tokens_in, tokens_out = _extract_usage(data)
        elif provider == "groq":
            key = _groq_key()
            if not key:
                return Measurement(
                    task=case.task,
                    provider="groq",
                    model=model,
                    family=route.family,
                    run_idx=run_idx,
                    total_ms=None,
                    http_status=None,
                    ok=False,
                    error_type="missing_groq_key",
                    valid_json=False,
                    schema_pass=False,
                    schema_reason="no_key",
                    tokens_in=None,
                    tokens_out=None,
                    text_len=0,
                    text_preview="",
                )
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            body = {
                "model": model,
                "messages": case.messages,
                "temperature": float(case.temperature),
                "max_tokens": int(case.max_tokens),
                "stream": False,
            }
            if case.extra:
                body.update(case.extra)
            status, data = _post_chat(session=session_groq, url=groq_url, headers=headers, body=body, timeout_s=case.timeout_s)
            if status != 200:
                error_type = f"http_{status}"
            else:
                ok = True
                text = _extract_text(data)
                tokens_in, tokens_out = _extract_usage(data)
        else:
            error_type = f"unknown_provider:{provider}"
    except requests.exceptions.Timeout:
        error_type = "timeout"
    except Exception as e:  # noqa: BLE001
        error_type = f"error:{type(e).__name__}"

    total_ms = int((time.perf_counter() - t0) * 1000)
    text = str(text or "")
    preview = text.replace("\n", "\\n")[:200]

    valid_json = False
    schema_pass = False
    schema_reason = ""

    if ok and case.expect_json:
        parsed = _parse_json_best_effort(text)
        valid_json = parsed is not None
        validator = _JSON_VALIDATORS.get(case.task)
        if validator is None:
            schema_pass = valid_json
            schema_reason = "no_validator"
        else:
            schema_pass, schema_reason = validator(parsed)
    elif ok and not case.expect_json:
        schema_pass, schema_reason = _validate_scholar_summary(text)

    return Measurement(
        task=case.task,
        provider=("openrouter" if provider in ("", "openrouter") else provider),
        model=model,
        family=str(route.family or ""),
        run_idx=int(run_idx),
        total_ms=int(total_ms),
        http_status=int(status) if status is not None else None,
        ok=bool(ok),
        error_type=str(error_type or ""),
        valid_json=bool(valid_json),
        schema_pass=bool(schema_pass),
        schema_reason=str(schema_reason or ""),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        text_len=len(text),
        text_preview=preview,
    )


def _group_key(m: Measurement) -> tuple[str, str, str]:
    return (m.task, m.provider, m.model)


def _summarize_group(rows: list[Measurement], *, expect_json: bool) -> dict[str, Any]:
    n = len(rows)
    ok_rate = sum(1 for r in rows if r.ok) / max(1, n)
    timeout_rate = sum(1 for r in rows if r.error_type == "timeout") / max(1, n)
    if expect_json:
        valid_json_rate = sum(1 for r in rows if r.valid_json) / max(1, n)
    else:
        valid_json_rate = None
    schema_rate = sum(1 for r in rows if r.schema_pass) / max(1, n)
    usable_ms = [float(r.total_ms) for r in rows if r.schema_pass and isinstance(r.total_ms, int)]
    ok_ms = [float(r.total_ms) for r in rows if r.ok and isinstance(r.total_ms, int)]
    p50 = _percentile(usable_ms, 50) if usable_ms else _percentile(ok_ms, 50)
    p95 = _percentile(usable_ms, 95) if usable_ms else _percentile(ok_ms, 95)
    tokens_out = [int(r.tokens_out) for r in rows if isinstance(r.tokens_out, int)]
    tokens_out_mean = statistics.mean(tokens_out) if tokens_out else None
    return {
        "n": n,
        "ok_rate": ok_rate,
        "timeout_rate": timeout_rate,
        "valid_json_rate": valid_json_rate,
        "schema_pass_rate": schema_rate,
        "p50_ms": p50,
        "p95_ms": p95,
        "tokens_out_mean": tokens_out_mean,
    }


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _write_md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _render_task_table(task: str, rows: list[dict[str, Any]]) -> str:
    lines = []
    lines.append(f"## {task}")
    lines.append("")
    lines.append("| rank | provider | model | family | ok_rate | schema_rate | timeout_rate | p50_ms | p95_ms | tokens_out |")
    lines.append("| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for idx, r in enumerate(rows, start=1):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(idx),
                    str(r["provider"]),
                    str(r["model"]),
                    str(r.get("family") or ""),
                    f"{r['ok_rate']:.2f}",
                    f"{r['schema_pass_rate']:.2f}",
                    f"{r['timeout_rate']:.2f}",
                    str(int(r["p50_ms"])) if r.get("p50_ms") is not None else "",
                    str(int(r["p95_ms"])) if r.get("p95_ms") is not None else "",
                    str(int(r["tokens_out_mean"])) if r.get("tokens_out_mean") is not None else "",
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def _rank_groups(
    *,
    task: str,
    summaries: list[dict[str, Any]],
    expect_json: bool,
    schema_threshold: float,
    timeout_threshold: float,
) -> list[dict[str, Any]]:
    def meets(r: dict[str, Any]) -> bool:
        if not expect_json:
            return (r.get("ok_rate") or 0.0) >= 0.98 and (r.get("timeout_rate") or 0.0) <= timeout_threshold
        return (r.get("schema_pass_rate") or 0.0) >= schema_threshold and (r.get("timeout_rate") or 0.0) <= timeout_threshold

    def key(r: dict[str, Any]) -> tuple[int, float, float, float]:
        # Sort: meets thresholds first, then p95, then p50, then tokens_out.
        p95 = float(r.get("p95_ms") or 1e18)
        p50 = float(r.get("p50_ms") or 1e18)
        tok = float(r.get("tokens_out_mean") or 1e18)
        return (0 if meets(r) else 1, p95, p50, tok)

    ordered = sorted(summaries, key=key)
    for r in ordered:
        r["task"] = task
        r["meets_thresholds"] = meets(r)
    return ordered


def _write_recommendations(
    *,
    out_path: Path,
    ranked_by_task: dict[str, list[dict[str, Any]]],
) -> None:
    lines: list[str] = []
    lines.append(f"# Generated by bench/run_llm_bench.py at {_iso_z(_utc_now())}")
    lines.append("# Copy-paste into your .env.production (or task-level override env).")
    lines.append("# NOTE: Values use route specs like openrouter:<model> or groq:<model>.")
    lines.append("")
    for task, rows in ranked_by_task.items():
        if not rows:
            continue
        best = rows[0]
        route = f"{best['provider']}:{best['model']}"
        key = f"DINQ_LLM_TASK_MODEL_{task.replace('.', '_').replace('-', '_').upper()}"
        lines.append(f"{key}={route}")
    lines.append("")
    _write_md(out_path, "\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description="LLM bench: OpenRouter + Groq (direct HTTP).")
    parser.add_argument("--samples", type=str, default=str(REPO_ROOT / "bench/llm_samples.json"))
    parser.add_argument("--n", type=int, default=6, help="Runs per provider+model+task (default: 6)")
    parser.add_argument("--tasks", type=str, default="", help="Comma-separated tasks to run (default: all)")
    parser.add_argument("--providers", type=str, default="openrouter,groq", help="Comma-separated providers to run")
    parser.add_argument("--openrouter-model", action="append", default=[], help="OpenRouter model id (repeatable)")
    parser.add_argument("--groq-model", action="append", default=[], help="Groq model id (repeatable)")
    parser.add_argument("--openrouter-url", type=str, default="https://openrouter.ai/api/v1/chat/completions")
    parser.add_argument("--groq-url", type=str, default="https://api.groq.com/openai/v1/chat/completions")
    parser.add_argument("--schema-threshold", type=float, default=0.98)
    parser.add_argument("--timeout-threshold", type=float, default=0.02)
    parser.add_argument("--out-base", type=str, default=str(REPO_ROOT / ".local/bench/llm"))
    parser.add_argument("--pool-max", type=int, default=32)
    args = parser.parse_args()

    samples_path = Path(args.samples)
    tasks = _load_tasks(samples_path)

    wanted_tasks = {t.strip() for t in str(args.tasks or "").split(",") if t.strip()}
    if wanted_tasks:
        tasks = [t for t in tasks if t.task in wanted_tasks]
    if not tasks:
        raise SystemExit("No tasks selected")

    providers = {p.strip().lower() for p in str(args.providers or "").split(",") if p.strip()}
    routes: list[Route] = []
    if args.openrouter_model:
        for m in args.openrouter_model:
            routes.append(Route(provider="openrouter", model=str(m), family=str(m).split("/", 1)[-1]))
    if args.groq_model:
        for m in args.groq_model:
            routes.append(Route(provider="groq", model=str(m), family=str(m)))
    if not routes:
        routes = _default_routes()

    routes = [r for r in routes if str(r.provider).strip().lower() in providers]
    if not routes:
        raise SystemExit("No routes selected (providers/models mismatch)")

    run_n = max(1, min(int(args.n), 50))

    out_base = Path(args.out_base)
    ts = _utc_now().strftime("%Y%m%d_%H%M%S")
    out_dir = out_base / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    session_openrouter = _make_session(pool_max=int(args.pool_max))
    session_groq = _make_session(pool_max=int(args.pool_max))

    measurements: list[Measurement] = []
    for case in tasks:
        for route in routes:
            for i in range(run_n):
                m = _run_one(
                    route=route,
                    case=case,
                    run_idx=i + 1,
                    session_openrouter=session_openrouter,
                    session_groq=session_groq,
                    openrouter_url=str(args.openrouter_url),
                    groq_url=str(args.groq_url),
                )
                measurements.append(m)

    report = {
        "meta": {
            "utc_started_at": ts,
            "samples": str(samples_path),
            "n_per_group": run_n,
            "openrouter_url": str(args.openrouter_url),
            "groq_url": str(args.groq_url),
            "providers": sorted(providers),
            "routes": [r.__dict__ for r in routes],
        },
        "measurements": [m.__dict__ for m in measurements],
    }
    _write_json(out_dir / "report.json", report)

    summaries_by_task: dict[str, list[dict[str, Any]]] = {}
    ranked_by_task: dict[str, list[dict[str, Any]]] = {}

    for case in tasks:
        groups: dict[tuple[str, str, str], list[Measurement]] = {}
        for m in measurements:
            if m.task != case.task:
                continue
            groups.setdefault(_group_key(m), []).append(m)
        summaries: list[dict[str, Any]] = []
        for (_, provider, model), rows in groups.items():
            s = _summarize_group(rows, expect_json=bool(case.expect_json))
            s.update({"provider": provider, "model": model, "family": rows[0].family if rows else ""})
            summaries.append(s)
        summaries_by_task[case.task] = summaries
        ranked = _rank_groups(
            task=case.task,
            summaries=summaries,
            expect_json=bool(case.expect_json),
            schema_threshold=float(args.schema_threshold),
            timeout_threshold=float(args.timeout_threshold),
        )
        ranked_by_task[case.task] = ranked

    md_parts = []
    md_parts.append(f"# LLM Bench Report ({ts} UTC)")
    md_parts.append("")
    md_parts.append(f"- samples: `{samples_path}`")
    md_parts.append(f"- runs per group: `{run_n}`")
    md_parts.append(f"- providers: `{', '.join(sorted(providers))}`")
    md_parts.append("")
    for case in tasks:
        md_parts.append(_render_task_table(case.task, ranked_by_task.get(case.task, [])))
    _write_md(out_dir / "report.md", "\n".join(md_parts))

    _write_recommendations(out_path=out_dir / "recommendations.env", ranked_by_task=ranked_by_task)

    print(str(out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
