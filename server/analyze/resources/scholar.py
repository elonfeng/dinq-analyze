from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, Optional

from server.services.scholar.scholar_service import (
    DB_CACHE_AVAILABLE,
    ScholarService,
    find_arxiv,
    generate_critical_evaluation,
    get_best_collaborator,
    get_latest_news,
    get_random_avatar,
    get_random_description,
    get_role_model,
    save_scholar_to_cache,
    summarize_paper_of_year,
    validate_and_complete_cache,
)
from server.services.scholar.pipeline import ScholarPipelineDeps, run_scholar_pipeline, stage_enrich, stage_persist, stage_render, ScholarPipelineContext, ScholarPipelineState
from server.services.scholar.pipeline import stage_fetch_profile, stage_search
from server.utils.timing import elapsed_ms, now_perf
import requests

try:
    from server.api.scholar.db_cache import get_scholar_from_cache  # type: ignore
except Exception:  # noqa: BLE001
    get_scholar_from_cache = None  # type: ignore


ProgressFn = Callable[[str, str, Optional[Dict[str, Any]]], None]


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return int(default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return int(default)


def _make_callback(progress: Optional[ProgressFn]) -> Optional[Callable]:
    if progress is None:
        return None

    def cb(payload):
        if isinstance(payload, dict):
            message = str(payload.get("message") or "")
            p = payload.get("progress")
            extra = {k: v for k, v in payload.items() if k not in ("message", "progress")}
            extra["progress"] = p
            progress("scholar.progress", message, extra)
            return
        progress("scholar.progress", str(payload), None)

    return cb


def _career_level(report: Dict[str, Any], from_cache: bool = False, cb: Optional[Callable] = None) -> Any:
    from server.services.scholar.career_level_service import get_career_level_info

    return get_career_level_info(report, from_cache=from_cache, callback=cb)


def estimate_scholar_level_fast(
    *,
    report: Dict[str, Any],
    timeout_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Fast (<= ~10s) Scholar level estimate using a stable JSON-friendly model.

    This is designed for the critical path: return a usable payload quickly and let a slower
    juris.*-based refinement run in the background.
    """

    from server.llm.gateway import openrouter_chat
    from server.config.llm_models import get_model

    r = report if isinstance(report, dict) else {}
    researcher = r.get("researcher") if isinstance(r.get("researcher"), dict) else {}
    pub_stats = r.get("publication_stats") if isinstance(r.get("publication_stats"), dict) else {}

    def _int(value: Any) -> int:
        try:
            if value is None or isinstance(value, bool):
                return 0
            if isinstance(value, (int, float)):
                return int(value)
            s = str(value).strip().lower().replace(",", "")
            if not s:
                return 0
            if s.endswith("k"):
                return int(float(s[:-1]) * 1000)
            return int(float(s))
        except Exception:
            return 0

    def _fallback_level_estimate() -> Dict[str, Any]:
        total_citations = _int(researcher.get("total_citations"))
        citations_5y = _int(researcher.get("citations_5y"))
        h_index = _int(researcher.get("h_index"))
        h_index_5y = _int(researcher.get("h_index_5y"))
        total_papers = _int(pub_stats.get("total_papers"))

        # Heuristic level buckets (conservative, deterministic).
        if h_index >= 140 or total_citations >= 200_000 or citations_5y >= 120_000:
            level_us = "L8"
        elif h_index >= 90 or total_citations >= 80_000 or citations_5y >= 45_000:
            level_us = "L7"
        elif h_index >= 50 or total_citations >= 20_000 or citations_5y >= 12_000:
            level_us = "L6"
        elif h_index >= 25 or total_citations >= 5_000 or citations_5y >= 2_500:
            level_us = "L5"
        else:
            level_us = "L4"

        level_cn = {
            "L4": "P6",
            "L5": "P7",
            "L6": "P8",
            "L7": "P9",
            "L8": "P10",
        }.get(level_us, "P7")

        # Salary ranges are used by the UI as a rough "Estimated Salary" indicator.
        # Return a parseable USD range string without commas to maximize compatibility.
        base_ranges = {
            "L4": (180_000, 260_000),
            "L5": (260_000, 360_000),
            "L6": (360_000, 520_000),
            "L7": (520_000, 760_000),
            "L8": (760_000, 1_050_000),
        }
        lo, hi = base_ranges.get(level_us, (260_000, 360_000))

        # Light signal-based adjustment (still deterministic).
        scale = 1.0
        if total_papers >= 300 or h_index >= 100:
            scale *= 1.08
        if total_citations >= 150_000:
            scale *= 1.06
        lo_i = int(lo * scale)
        hi_i = int(hi * scale)
        if lo_i >= hi_i:
            lo_i, hi_i = lo, hi

        earnings = f"{lo_i}-{hi_i}"

        name = str(researcher.get("name") or "").strip() or "This researcher"
        affiliation = str(researcher.get("affiliation") or "").strip()
        justification = (
            f"{name} shows strong research impact signals (h-index {h_index}, total citations {total_citations}). "
            + (f"Affiliation: {affiliation}. " if affiliation else "")
            + f"Estimated level: {level_us}/{level_cn}."
        ).strip()

        # Conservative default bars with mild tuning from publication volume.
        depth = 7 if h_index >= 50 else 6
        breadth = 7 if total_papers >= 100 else 6
        depth_vs_breadth = max(1, min(10, int(round((depth + breadth) / 2))))
        theory_vs_practice = 7 if citations_5y >= 10_000 else 6
        individual_vs_team = 6 if total_papers >= 80 else 5

        years = max(3, min(45, int(round(max(h_index_5y, h_index) / 4))))
        try:
            from datetime import datetime

            current_year = int(datetime.utcnow().year)
        except Exception:
            current_year = 2025
        start_year = max(1970, current_year - years)

        return {
            "earnings": earnings,
            "level_cn": level_cn,
            "level_us": level_us,
            "justification": justification,
            "evaluation_bars": {
                "depth_vs_breadth": {"score": depth_vs_breadth, "explanation": "Balanced depth and breadth based on publication impact signals."},
                "theory_vs_practice": {"score": theory_vs_practice, "explanation": "Inferred from recent citations and venue mix."},
                "individual_vs_team": {"score": individual_vs_team, "explanation": "Inferred from coauthor patterns and publication volume."},
            },
            "years_of_experience": {"years": years, "start_year": start_year, "calculation_basis": "Heuristic based on impact metrics (h-index/citations)."},
        }

    def _pick_paper(p: Any) -> Dict[str, Any]:
        if not isinstance(p, dict):
            return {}
        out = {}
        for k in ("title", "year", "venue", "citations", "url"):
            if p.get(k) is not None:
                out[k] = p.get(k)
        return out

    llm_input = {
        "name": researcher.get("name"),
        "affiliation": researcher.get("affiliation"),
        "research_fields": researcher.get("research_fields") or researcher.get("fields") or [],
        "metrics": {
            "total_citations": researcher.get("total_citations"),
            "citations_5y": researcher.get("citations_5y"),
            "h_index": researcher.get("h_index"),
            "h_index_5y": researcher.get("h_index_5y"),
            "total_papers": pub_stats.get("total_papers"),
        },
        "highlights": {
            "most_cited_paper": _pick_paper(pub_stats.get("most_cited_paper")),
            "paper_of_year": _pick_paper(pub_stats.get("paper_of_year")),
            "top_tier": pub_stats.get("top_tier_papers") or pub_stats.get("top_tier_publications"),
        },
    }

    system = (
        "You are an expert research career evaluator.\n"
        "Given a compact scholar profile summary, estimate career level in CN/US and provide a short justification.\n"
        "Return ONLY valid JSON.\n\n"
        "Schema:\n"
        "{\n"
        '  \"earnings\": \"string (annual USD total compensation estimate)\",\n'
        '  \"level_cn\": \"string (e.g., P7)\",\n'
        '  \"level_us\": \"string (e.g., L5)\",\n'
        '  \"justification\": \"string (2-4 sentences)\",\n'
        '  \"evaluation_bars\": {\n'
        '    \"depth_vs_breadth\": {\"score\": 0, \"explanation\": \"string\"},\n'
        '    \"theory_vs_practice\": {\"score\": 0, \"explanation\": \"string\"},\n'
        '    \"individual_vs_team\": {\"score\": 0, \"explanation\": \"string\"}\n'
        "  },\n"
        '  \"years_of_experience\": {\"years\": 0, \"start_year\": 0, \"calculation_basis\": \"string\"}\n'
        "}\n"
        "Rules:\n"
        "- scores are integers 1-10.\n"
        "- be conservative; avoid wild claims.\n"
    )

    try:
        if timeout_seconds is None:
            timeout_seconds = float(os.getenv("DINQ_SCHOLAR_LEVEL_FAST_TIMEOUT_SECONDS", "10") or "10")
    except Exception:
        timeout_seconds = 10.0
    timeout_seconds = max(3.0, min(float(timeout_seconds), 60.0))

    model = get_model("fast", task="scholar_level_fast")
    primary_timeout = min(float(timeout_seconds), 3.0) if str(model).strip().lower().startswith("groq:") else float(timeout_seconds)
    try:
        out = openrouter_chat(
            task="scholar_level_fast",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(llm_input, ensure_ascii=False, separators=(",", ":"))},
            ],
            model=model,
            temperature=0.2,
            max_tokens=700,
            expect_json=True,
            stream=False,
            cache=False,
            timeout_seconds=primary_timeout,
        )
    except requests.exceptions.Timeout:
        out = None
    except Exception:
        out = None

    if not isinstance(out, dict) or not out:
        # Fallback: Gemini Flash tends to be more stable for strict JSON when Groq is rate-limited.
        try:
            out = openrouter_chat(
                task="scholar_level_fast",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(llm_input, ensure_ascii=False, separators=(",", ":"))},
                ],
                model="google/gemini-2.5-flash",
                temperature=0.2,
                max_tokens=700,
                expect_json=True,
                stream=False,
                cache=False,
                timeout_seconds=float(timeout_seconds),
            )
        except Exception:
            out = None

    base = _fallback_level_estimate()
    payload = out if isinstance(out, dict) else {}

    # Merge: keep model outputs when present, but always fill required keys so downstream formatted cards
    # (estimatedSalary/researcherCharacter) don't end up missing critical fields.
    merged: Dict[str, Any] = dict(base)
    for k, v in payload.items():
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        if isinstance(v, dict) and not v:
            continue
        if isinstance(v, list) and not v:
            continue
        merged[k] = v

    # Ensure earnings is always parseable.
    earnings_val = merged.get("earnings")
    if isinstance(earnings_val, bool):
        earnings_val = None
    if isinstance(earnings_val, (int, float)) and earnings_val is not None:
        if int(earnings_val) <= 0:
            merged["earnings"] = base.get("earnings")
    elif isinstance(earnings_val, str):
        earnings = earnings_val.strip()
        if not earnings or earnings.lower() in ("n/a", "na", "unknown", "none"):
            merged["earnings"] = base.get("earnings")
        else:
            # Some models return qualitative text ("competitive") which breaks downstream USD parsing.
            if not any(ch.isdigit() for ch in earnings):
                merged["earnings"] = base.get("earnings")
    else:
        # Reject non-scalar earnings (dict/list/etc) to keep downstream formatting stable.
        merged["earnings"] = base.get("earnings")

    def _norm_level_us(raw: Any, fallback: Any) -> Any:
        s = str(raw or "").strip().upper().replace(" ", "")
        if s.startswith("L") and len(s) > 1 and s[1:].isdigit():
            try:
                n = int(s[1:])
            except Exception:
                n = 0
            if 3 <= n <= 8:
                return f"L{n}"
        return fallback

    def _norm_level_cn(raw: Any, fallback: Any) -> Any:
        s = str(raw or "").strip().upper().replace(" ", "")
        if s.startswith("P") and len(s) > 1 and s[1:].isdigit():
            try:
                n = int(s[1:])
            except Exception:
                n = 0
            if 3 <= n <= 12:
                return f"P{n}"
        return fallback

    merged["level_us"] = _norm_level_us(merged.get("level_us"), base.get("level_us"))
    merged["level_cn"] = _norm_level_cn(merged.get("level_cn"), base.get("level_cn"))

    return merged


def _build_deps(
    *,
    use_cache: bool,
    cache_max_age_days: int,
    enable_enrich: bool,
    enable_cache_save: bool,
    fetch_timeout_seconds: Optional[float] = None,
    fetch_max_retries: Optional[int] = None,
) -> ScholarPipelineDeps:
    api_token = (os.getenv("CRAWLBASE_API_TOKEN") or os.getenv("CRAWLBASE_TOKEN") or "").strip() or None
    use_crawlbase = _bool_env("DINQ_SCHOLAR_USE_CRAWLBASE", default=bool(api_token))

    service = ScholarService(
        use_crawlbase=use_crawlbase,
        api_token=api_token,
        use_cache=use_cache,
        cache_max_age_days=cache_max_age_days,
        fetch_timeout_seconds=fetch_timeout_seconds,
        fetch_max_retries=fetch_max_retries,
    )

    effective_use_cache = bool(use_cache) and bool(DB_CACHE_AVAILABLE)
    cache_save = save_scholar_to_cache if (effective_use_cache and enable_cache_save) else None
    # Cache "validation" is expensive (it may recompute enrich fields). Only enable it
    # when we are actually running enrich in this pipeline. For page0/full (enable_enrich=False),
    # we want fast-first behavior: reuse cached payload immediately without heavy repair.
    cache_validate = validate_and_complete_cache if (effective_use_cache and enable_enrich) else None

    return ScholarPipelineDeps(
        data_fetcher=service.data_fetcher,
        analyzer=service.analyzer,
        tvly_client=service.tvly_client,
        tavily_id_extractor=service.extract_scholar_id_from_tavily_response,
        use_cache=effective_use_cache,
        cache_max_age_days=cache_max_age_days,
        cache_get=get_scholar_from_cache if effective_use_cache else None,
        cache_save=cache_save,
        cache_validate=cache_validate,
        avatar_provider=get_random_avatar,
        description_provider=get_random_description,
        best_collaborator=get_best_collaborator if enable_enrich else None,
        arxiv_finder=find_arxiv if enable_enrich else None,
        news_provider=get_latest_news if enable_enrich else None,
        role_model_provider=get_role_model if enable_enrich else None,
        career_level_provider=_career_level if enable_enrich else None,
        critical_evaluator=generate_critical_evaluation if enable_enrich else None,
        paper_summary_provider=summarize_paper_of_year if enable_enrich else None,
        logger=None,
        max_enrich_workers=5,
    )


def run_scholar_base(
    *,
    scholar_id: Optional[str],
    researcher_name: Optional[str],
    user_id: Optional[str],
    progress: Optional[ProgressFn] = None,
) -> Dict[str, Any]:
    """
    Compute the scholar base report (no enrich tasks).
    """
    return run_scholar_page0(
        scholar_id=scholar_id,
        researcher_name=researcher_name,
        user_id=user_id,
        progress=progress,
    )


def run_scholar_preview(
    *,
    scholar_id: Optional[str],
    researcher_name: Optional[str],
    user_id: Optional[str],
    progress: Optional[ProgressFn] = None,
) -> Dict[str, Any]:
    """
    Emit immediate skeleton prefills for Scholar UI cards (no network).

    This is designed to eliminate "blank screen" time: the frontend can render card shells
    instantly, then cards are upgraded by resource.scholar.page0/full.
    """

    if progress is None:
        return {"preview": True, "scholar_id": scholar_id, "query": researcher_name}

    sid = str(scholar_id or "").strip() or None
    query = str(researcher_name or "").strip() or None

    # Preview is a "skeleton" only; avoid showing scholar_id as the person's name (bad UX flicker).
    display_name = query

    # If the user provided a stable scholar_id, avoid showing a random avatar that will be
    # replaced almost immediately by the real photo (bad flicker). For name-queries, keep a
    # lightweight placeholder avatar so the UI isn't blank while resolving candidates.
    avatar = get_random_avatar() if query else None
    # Avoid "made-up" content; keep description empty for preview.
    description = ""

    meta = {"partial": True, "degraded": True, "source": "resource.scholar.preview", "preserve_empty": True}

    prefills: list[Dict[str, Any]] = []

    prefills.append(
        {
            "card": "researcherInfo",
            "data": {
                "name": display_name or None,
                "abbreviatedName": display_name or None,
                "affiliation": None,
                "email": None,
                "researchFields": [],
                "totalCitations": None,
                "citations5y": None,
                "hIndex": None,
                "hIndex5y": None,
                "yearlyCitations": {},
                "scholarId": sid,
                "avatar": avatar,
                "description": description,
            },
            "meta": dict(meta),
        }
    )

    prefills.append(
        {
            "card": "publicationStats",
            "data": {
                "blockTitle": "Papers",
                "totalPapers": None,
                "totalCitations": None,
                "hIndex": None,
                "yearlyCitations": {},
                "yearlyPapers": {},
            },
            "meta": dict(meta),
        }
    )

    prefills.append(
        {
            "card": "publicationInsight",
            "data": {
                "blockTitle": "Insight",
                "totalPapers": None,
                "topTierPapers": None,
                "firstAuthorPapers": None,
                "firstAuthorCitations": None,
                "totalCoauthors": None,
                "lastAuthorPapers": None,
                "conferenceDistribution": {},
            },
            "meta": dict(meta),
        }
    )

    prefills.append(
        {
            "card": "roleModel",
            "data": {
                "blockTitle": "Role Model",
                "found": False,
                "name": None,
                "institution": None,
                "position": None,
                "photoUrl": None,
                "achievement": None,
                "similarityReason": None,
                "isSelf": False,
            },
            "meta": dict(meta),
        }
    )

    prefills.append(
        {
            "card": "closestCollaborator",
            "data": {
                "blockTitle": "Closest Collaborator",
                "fullName": None,
                "affiliation": None,
                "researchInterests": [],
                "scholarId": None,
                "coauthoredPapers": None,
                "avatar": None,
                "bestCoauthoredPaper": {
                    "title": None,
                    "year": None,
                    "venue": None,
                    "fullVenue": None,
                    "citations": None,
                },
                "connectionAnalysis": None,
            },
            "meta": dict(meta),
        }
    )

    prefills.append(
        {
            "card": "estimatedSalary",
            "data": {
                "blockTitle": "Estimated Salary",
                "earningsPerYearUSD": None,
                "levelEquivalency": {"us": None, "cn": None},
                "reasoning": None,
            },
            "meta": dict(meta),
        }
    )

    prefills.append(
        {
            "card": "researcherCharacter",
            "data": {
                "blockTitle": "Researcher Character",
                "depthVsBreadth": None,
                "theoryVsPractice": None,
                "soloVsTeamwork": None,
                "justification": None,
            },
            "meta": dict(meta),
        }
    )

    prefills.append(
        {
            "card": "paperOfYear",
            "data": {
                "blockTitle": "Paper of Year",
                "title": None,
                "year": None,
                "venue": None,
                "citations": None,
                "authorPosition": None,
                "summary": None,
            },
            "meta": dict(meta),
        }
    )

    prefills.append(
        {
            "card": "representativePaper",
            "data": {
                "blockTitle": "Representative Paper",
                "title": None,
                "year": None,
                "venue": None,
                "fullVenue": None,
                "citations": None,
                "authorPosition": None,
                "paper_news": None,
            },
            "meta": dict(meta),
        }
    )

    prefills.append(
        {
            "card": "criticalReview",
            "data": {
                "blockTitle": "Roast",
                "evaluation": "",
            },
            "meta": dict(meta),
        }
    )

    try:
        progress("preview.scholar.skeleton", "Scholar cards prefilled (skeleton)", {"prefill_cards": prefills})
    except Exception:
        pass

    return {"preview": True, "scholar_id": sid, "query": query, "user_id": user_id}


def run_scholar_page0(
    *,
    scholar_id: Optional[str],
    researcher_name: Optional[str],
    user_id: Optional[str],
    progress: Optional[ProgressFn] = None,
) -> Dict[str, Any]:
    """
    Fetch ONLY Scholar page0 (+ base stats) for fast-first UX.

    Key knobs:
      - DINQ_SCHOLAR_PAGE0_FETCH_TIMEOUT_SECONDS (default 10)
      - DINQ_SCHOLAR_PAGE0_FETCH_MAX_RETRIES (default 1)
    """

    cache_max_age_days = max(0, min(_int_env("DINQ_SCHOLAR_CACHE_MAX_AGE_DAYS", 3), 30))
    # Keep page0 small to stay within the 10s first-screen budget (also reduces Crawlbase payload size).
    max_papers_page0 = max(0, _int_env("DINQ_SCHOLAR_MAX_PAPERS_PAGE0", 30))
    cb = _make_callback(progress)

    try:
        page0_timeout = float(os.getenv("DINQ_SCHOLAR_PAGE0_FETCH_TIMEOUT_SECONDS", "10") or "10")
    except Exception:
        page0_timeout = 10.0
    page0_timeout = max(1.0, min(float(page0_timeout), 30.0))

    try:
        page0_retries = int(os.getenv("DINQ_SCHOLAR_PAGE0_FETCH_MAX_RETRIES", "1") or "1")
    except Exception:
        page0_retries = 1
    page0_retries = max(0, min(int(page0_retries), 2))

    deps = _build_deps(
        use_cache=True,
        cache_max_age_days=cache_max_age_days,
        enable_enrich=False,
        enable_cache_save=False,
        fetch_timeout_seconds=page0_timeout,
        fetch_max_retries=page0_retries,
    )

    # Fast-first pipeline: only run search + fetch_profile + render.
    # Avoid heavy analyze/coauthor graph on the 10s critical path; full stats come from resource.scholar.full.
    ctx = ScholarPipelineContext(callback=cb, cancel_event=None, status_sender=None)
    state = ScholarPipelineState(researcher_name=researcher_name, scholar_id=scholar_id, user_id=user_id)

    if researcher_name:
        ctx.status(f"Searching for author: {researcher_name}", progress=5.0)
    if scholar_id:
        ctx.status(f"Generating report for ID: {scholar_id}...", progress=10.0)

    t_search = now_perf()
    if not stage_search(ctx, deps, state):
        ctx.status("Stage search failed", progress=ctx.last_progress, kind="timing", stage="search", duration_ms=elapsed_ms(t_search))
        return {}
    ctx.status("Stage search completed", progress=ctx.last_progress, kind="timing", stage="search", duration_ms=elapsed_ms(t_search))

    if not state.from_cache:
        t_fetch = now_perf()
        if not stage_fetch_profile(ctx, deps, state, max_papers=int(max_papers_page0)):
            ctx.status("Stage fetch_profile failed", progress=ctx.last_progress, kind="timing", stage="fetch_profile", duration_ms=elapsed_ms(t_fetch))
            return {}
        ctx.status("Stage fetch_profile completed", progress=ctx.last_progress, kind="timing", stage="fetch_profile", duration_ms=elapsed_ms(t_fetch))

        # Minimal pub_stats for early metrics card; full stats are computed by resource.scholar.full.
        author_data = state.author_data if isinstance(state.author_data, dict) else {}
        papers = author_data.get("papers") if isinstance(author_data.get("papers"), list) else []
        years = author_data.get("years_of_papers") if isinstance(author_data.get("years_of_papers"), dict) else {}
        state.pub_stats = {
            "papers_loaded": len(papers),
            "year_distribution": years,
        }

    t_render = now_perf()
    out = stage_render(ctx, deps, state)
    ctx.status("Stage render completed", progress=ctx.last_progress, kind="timing", stage="render", duration_ms=elapsed_ms(t_render))
    out = out or {}

    # Phase-2 UX: emit early, user-facing previews from page0 without waiting for downstream cards.
    # - prefill core formatted blocks used by the frontend contract
    if progress and isinstance(out, dict) and out:
        try:
            researcher = out.get("researcher") if isinstance(out.get("researcher"), dict) else {}
            pub_stats = out.get("publication_stats") if isinstance(out.get("publication_stats"), dict) else {}

            prefills: list[Dict[str, Any]] = []
            if researcher:
                researcher_info: Dict[str, Any] = {
                    "name": researcher.get("name"),
                    "abbreviatedName": researcher.get("abbreviated_name"),
                    "affiliation": researcher.get("affiliation"),
                    "email": researcher.get("email"),
                    "researchFields": researcher.get("research_fields") if isinstance(researcher.get("research_fields"), list) else [],
                    "totalCitations": researcher.get("total_citations"),
                    "citations5y": researcher.get("citations_5y"),
                    "hIndex": researcher.get("h_index"),
                    "hIndex5y": researcher.get("h_index_5y"),
                    "yearlyCitations": researcher.get("yearly_citations") if isinstance(researcher.get("yearly_citations"), dict) else {},
                    "scholarId": researcher.get("scholar_id"),
                    "avatar": researcher.get("avatar"),
                    "description": researcher.get("description"),
                }
                prefills.append(
                    {
                        "card": "researcherInfo",
                        "data": researcher_info,
                        "meta": {"partial": True, "source": "resource.scholar.page0"},
                    }
                )

            if pub_stats or researcher:
                # Page0 does not run the heavy publication analyzer, so `total_papers` may be missing.
                # Use the real papers loaded on page0 (bounded by max_papers_page0) to avoid showing `0`
                # while the full report is still running.
                total_papers = pub_stats.get("total_papers") if isinstance(pub_stats, dict) else None
                if total_papers is None and isinstance(pub_stats, dict):
                    total_papers = pub_stats.get("papers_loaded")
                if total_papers is None:
                    papers_preview = out.get("papers_preview") if isinstance(out.get("papers_preview"), list) else []
                    if papers_preview:
                        total_papers = len(papers_preview)
                prefills.append(
                    {
                        "card": "publicationStats",
                        "data": {
                            "blockTitle": "Papers",
                            "totalPapers": total_papers,
                            "totalCitations": researcher.get("total_citations"),
                            "hIndex": researcher.get("h_index"),
                            "yearlyCitations": researcher.get("yearly_citations") if isinstance(researcher.get("yearly_citations"), dict) else {},
                            "yearlyPapers": pub_stats.get("year_distribution") if isinstance(pub_stats.get("year_distribution"), dict) else {},
                        },
                        "meta": {"partial": True, "source": "resource.scholar.page0"},
                    }
                )

            if prefills:
                progress("preview.scholar.cards", "Scholar page0 cards prefilled", {"prefill_cards": prefills})
        except Exception:
            pass

    return out


def refresh_scholar_level_cache(
    *,
    user_id: str,
    subject_key: str,
    report: Dict[str, Any],
    options: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Background refresh for Scholar level (juris.* slow path).

    Writes a cross-job cached artifact so the next request can reuse the refined level
    without blocking the current job.
    """

    from server.analyze.cache_policy import cache_ttl_seconds, compute_options_hash, get_pipeline_version, is_cacheable_subject
    from server.analyze.subject import resolve_subject_key
    from server.tasks.analysis_cache_store import AnalysisCacheStore

    src = "scholar"
    sk = str(subject_key or "").strip() or resolve_subject_key(src, {"content": str(((report or {}).get("researcher") or {}).get("scholar_id") or "")})
    if not sk or not is_cacheable_subject(source=src, subject_key=sk):
        return

    opts = options or {}
    pipeline_version = get_pipeline_version()
    options_hash = compute_options_hash(opts)
    ttl_seconds = cache_ttl_seconds(src)

    cache_store = AnalysisCacheStore()
    subject = cache_store.get_or_create_subject(source=src, subject_key=sk, canonical_input={"content": str((opts or {}).get("content") or "")})

    # Slow path: use existing juris.* stack (may call multiple LLMs + web search).
    from server.services.scholar.career_level_service import get_career_level_info

    level = get_career_level_info(dict(report or {}), from_cache=False, callback=None) or {}
    if not isinstance(level, dict) or not level:
        return

    # Mark as refined, but do NOT set _meta.fallback=True (we still want validation to apply).
    meta = level.get("_meta") if isinstance(level, dict) else None
    if isinstance(meta, dict):
        merged_meta = dict(meta)
        merged_meta.update({"level_refined": True, "source": "juris"})
        level["_meta"] = merged_meta
    else:
        level["_meta"] = {"level_refined": True, "source": "juris"}

    try:
        cache_store.save_cached_artifact(
            source=src,
            subject=subject,
            pipeline_version=pipeline_version,
            options_hash=options_hash,
            kind="card:level",
            payload=level,
            ttl_seconds=ttl_seconds,
            meta={"cache": "bg_refresh", "kind": "card:level", "user_id": str(user_id or "")},
        )
    except Exception:
        pass

    # Best-effort: also patch the latest cached full_report (if any) so future cache-hits include the refined level.
    try:
        cached = cache_store.get_latest_cached_full_report(
            subject_id=int(subject.id),
            pipeline_version=pipeline_version,
            options_hash=options_hash,
        )
    except Exception:
        cached = None

    if cached and isinstance(cached.payload, dict) and cached.payload:
        merged_full = dict(cached.payload)
        merged_full["level_info"] = level
        try:
            from server.analyze.fingerprint import fingerprint_from_payload

            fp = fingerprint_from_payload(source=src, payload=merged_full)
        except Exception:
            fp = None
        try:
            cache_store.save_full_report(
                source=src,
                subject=subject,
                pipeline_version=pipeline_version,
                options_hash=options_hash,
                fingerprint=fp,
                payload=merged_full,
                ttl_seconds=ttl_seconds,
                meta={"cache": "bg_refresh", "kind": "full_report", "reason": "scholar_level_refined"},
            )
        except Exception:
            pass


def run_scholar_full(
    *,
    scholar_id: Optional[str],
    researcher_name: Optional[str],
    user_id: Optional[str],
    progress: Optional[ProgressFn] = None,
) -> Dict[str, Any]:
    """
    Fetch a fuller Scholar base report (more pages/papers) in the background.

    This is intended to run *after* the fast-first `run_scholar_base()` job and can be used
    to incrementally append more papers and populate cache for future jobs.
    """

    cache_max_age_days = max(0, min(_int_env("DINQ_SCHOLAR_CACHE_MAX_AGE_DAYS", 3), 30))
    cb = _make_callback(progress)
    deps = _build_deps(use_cache=True, cache_max_age_days=cache_max_age_days, enable_enrich=False, enable_cache_save=True)
    report = run_scholar_pipeline(
        deps=deps,
        researcher_name=researcher_name,
        scholar_id=scholar_id,
        user_id=user_id,
        max_papers=max(0, _int_env("DINQ_SCHOLAR_MAX_PAPERS_FULL", 500)),
        callback=cb,
        cancel_event=None,
        status_sender=None,
    )
    report = report or {}

    # Phase-2 UX: best-effort append more papers in the background.
    if progress and isinstance(report, dict) and report:
        try:
            papers = report.get("papers_preview") if isinstance(report.get("papers_preview"), list) else []
            if papers:
                progress(
                    "preview.scholar.papers_full",
                    "Scholar papers full batch ready",
                    {
                        "append": {
                            "card": "papers",
                            "path": "items",
                            "items": papers,
                            "dedup_key": "id",
                            "partial": False,
                        }
                    },
                )
        except Exception:
            pass

    return report


def run_scholar_enrich(
    *,
    base_report: Dict[str, Any],
    user_id: Optional[str],
    progress: Optional[ProgressFn] = None,
) -> Dict[str, Any]:
    """
    Enrich an existing scholar base report (LLM/news/role_model/level/etc) without refetching profile.
    """

    report = dict(base_report or {})
    if not report:
        return {}

    # If cached report already contains enrich fields, keep it as-is.
    if report.get("critical_evaluation") and report.get("level_info"):
        return report

    cache_max_age_days = max(0, min(_int_env("DINQ_SCHOLAR_CACHE_MAX_AGE_DAYS", 3), 30))
    cb = _make_callback(progress)
    deps = _build_deps(use_cache=True, cache_max_age_days=cache_max_age_days, enable_enrich=True, enable_cache_save=True)

    researcher = report.get("researcher") if isinstance(report, dict) else {}
    scholar_id = None
    if isinstance(researcher, dict):
        scholar_id = researcher.get("scholar_id")

    ctx = ScholarPipelineContext(callback=cb, cancel_event=None, status_sender=None)
    state = ScholarPipelineState(
        researcher_name=(researcher or {}).get("name") if isinstance(researcher, dict) else None,
        scholar_id=scholar_id,
        user_id=user_id,
    )
    state.report = report
    state.pub_stats = report.get("publication_stats") if isinstance(report.get("publication_stats"), dict) else {}
    state.coauthor_stats = report.get("coauthor_stats") if isinstance(report.get("coauthor_stats"), dict) else {}
    state.rating = report.get("rating")
    state.from_cache = False

    stage_enrich(ctx, deps, state)
    stage_persist(ctx, deps, state)
    final = stage_render(ctx, deps, state)
    return final or report
