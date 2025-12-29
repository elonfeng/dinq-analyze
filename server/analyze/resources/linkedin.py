from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, Optional, Tuple

import requests

from server.utils.timing import elapsed_ms, now_perf
from server.llm.gateway import openrouter_chat


ProgressFn = Callable[[str, str, Optional[Dict[str, Any]]], None]


def _emit(progress: Optional[ProgressFn], step: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
    if progress:
        progress(step, message, data)


def _resolve_url_and_name(analyzer, content: str, progress: Optional[ProgressFn]) -> Tuple[str, str]:
    raw = (content or "").strip()
    if not raw:
        raise ValueError("missing linkedin input")

    if "linkedin.com" in raw:
        return raw, raw

    person_name = raw
    _emit(progress, "searching", f"Searching LinkedIn URL for {person_name}...", None)
    results = analyzer.search_linkedin_url(person_name)
    if not results:
        raise ValueError(f'No LinkedIn profile found for "{person_name}"')
    url = str(results[0].get("url") or "").strip()
    if not url:
        raise ValueError(f'No LinkedIn URL found for "{person_name}"')
    return url, person_name


def fetch_linkedin_preview(*, content: str, progress: Optional[ProgressFn] = None) -> Dict[str, Any]:
    """
    Fast-first LinkedIn preview:
      - resolves the profile URL
      - emits a degraded `profile` prefill immediately

    Does NOT perform the long-tail raw scraping step.
    """

    from server.api.linkedin_analyzer_api import get_linkedin_analyzer  # local import (heavy)

    analyzer = get_linkedin_analyzer()
    t0 = now_perf()
    linkedin_url, person_name = _resolve_url_and_name(analyzer, content, progress)
    _emit(progress, "timing.linkedin.resolve", "Resolved LinkedIn identity", {"duration_ms": elapsed_ms(t0)})

    try:
        _emit(
            progress,
            "preview.linkedin.profile",
            "LinkedIn profile preview ready (fetching raw profile in background)",
            {
                "prefill_cards": [
                    {
                        "card": "profile",
                        "data": {
                            "avatar": "",
                            "name": person_name,
                            "about": "",
                            "work_experience": [],
                            "education": [],
                        },
                        "meta": {
                            "partial": True,
                            "degraded": True,
                            "reason": "fetching_raw_profile",
                            "candidate_url": linkedin_url,
                        },
                    }
                ]
            },
        )
    except Exception:
        pass

    linkedin_id = analyzer.generate_linkedin_id(person_name, linkedin_url)
    return {
        "_linkedin_url": linkedin_url,
        "_linkedin_id": linkedin_id,
        "profile_data": {
            "avatar": "",
            "name": person_name,
            "about": "",
            "work_experience": [],
            "education": [],
        },
    }


def fetch_linkedin_raw_profile(
    *,
    content: str,
    progress: Optional[ProgressFn] = None,
    linkedin_url: Optional[str] = None,
    person_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fetch raw LinkedIn profile data and return a partial full_report-like dict.

    The returned object is shaped so that `extract_card_payload("linkedin", report, "profile")`
    works immediately (even before AI enrichments).
    """

    from server.api.linkedin_analyzer_api import get_linkedin_analyzer  # local import (heavy)

    analyzer = get_linkedin_analyzer()
    t0 = now_perf()
    resolved_url = str(linkedin_url or "").strip() if linkedin_url else ""
    resolved_name = str(person_name or "").strip() if person_name else ""
    if not resolved_url:
        resolved_url, resolved_name = _resolve_url_and_name(analyzer, content, progress)
    if not resolved_name:
        resolved_name = resolved_url if "linkedin.com" in resolved_url else (content or "").strip() or "Unknown"
    _emit(progress, "timing.linkedin.resolve", "Resolved LinkedIn identity", {"duration_ms": elapsed_ms(t0)})
    try:
        _emit(
            progress,
            "preview.linkedin.profile",
            "LinkedIn profile preview ready (fetching raw profile in background)",
            {
                "prefill_cards": [
                    {
                        "card": "profile",
                        "data": {
                            "avatar": "",
                            "name": resolved_name,
                            "about": "",
                            "work_experience": [],
                            "education": [],
                        },
                        "meta": {
                            "partial": True,
                            "degraded": True,
                            "reason": "fetching_raw_profile",
                            "candidate_url": resolved_url,
                        },
                    }
                ]
            },
        )
    except Exception:
        pass

    _emit(progress, "fetching", "Fetching LinkedIn profile details...", None)
    t1 = now_perf()
    raw_profile = analyzer.get_linkedin_profile(resolved_url)
    _emit(progress, "timing.linkedin.raw_profile", "Fetched LinkedIn raw profile", {"duration_ms": elapsed_ms(t1)})
    if not raw_profile:
        raise ValueError("Failed to fetch LinkedIn profile; please verify the URL or try again")

    resolved_name = raw_profile.get("fullName") or resolved_name
    linkedin_id = analyzer.generate_linkedin_id(resolved_name, resolved_url)

    # NOTE: The Apify blob can be large and is not required by the frontend contract.
    # Keep the UI-facing lists in `work_experience`/`education`, and store a pruned raw_profile
    # without duplicating experiences/educations.
    work_experience = raw_profile.get("experiences", []) or []
    education = raw_profile.get("educations", []) or []

    def _prune_for_storage(profile: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(profile, dict) or not profile:
            return {}
        keep_keys = {
            # Identity + UI hints
            "fullName",
            "name",
            "profilePic",
            "headline",
            "occupation",
            "jobTitle",
            "location",
            "addressWithCountry",
            "companyName",
            "companyIndustry",
            "connections",
            "followers",
            "about",
            # Useful for LLM compaction (small-ish)
            "skills",
            "languages",
        }
        out: Dict[str, Any] = {}
        for k in keep_keys:
            if profile.get(k) is not None:
                out[k] = profile.get(k)
        # Safety fallback: if the whitelist misses everything, still drop the biggest duplicated lists.
        if not out:
            out = {k: v for k, v in profile.items() if k not in ("experiences", "educations")}
        return out

    raw_profile_store = _prune_for_storage(raw_profile)

    report = {
        "_linkedin_url": resolved_url,
        "_linkedin_id": linkedin_id,
        "profile_data": {
            "avatar": raw_profile.get("profilePic"),
            "name": resolved_name,
            "about": raw_profile.get("about") or "",
            "work_experience": work_experience,
            "education": education,
            "raw_profile": raw_profile_store,
        },
    }
    return report


def run_linkedin_ai_enrich(*, raw_report: Dict[str, Any], progress: Optional[ProgressFn] = None) -> Dict[str, Any]:
    """
    Run AI enrichments for LinkedIn based on an already fetched raw profile.

    Returns a full_report-like dict compatible with the legacy schema.
    """

    from server.api.linkedin_analyzer_api import get_linkedin_analyzer  # local import (heavy)

    analyzer = get_linkedin_analyzer()
    raw_profile = ((raw_report or {}).get("profile_data") or {}).get("raw_profile") or {}
    if not isinstance(raw_profile, dict) or not raw_profile:
        raise ValueError("missing raw_profile for linkedin ai enrich")

    linkedin_url = str((raw_report or {}).get("_linkedin_url") or "").strip() or None
    person_name = raw_profile.get("fullName") or ((raw_report or {}).get("profile_data") or {}).get("name") or ""
    if not person_name:
        person_name = "Unknown"

    linkedin_id = str((raw_report or {}).get("_linkedin_id") or "").strip()
    if not linkedin_id:
        linkedin_id = analyzer.generate_linkedin_id(person_name, linkedin_url or "")

    _emit(progress, "analyzing", "Analyzing LinkedIn profile data...", None)
    analysis_result = analyzer.process_linkedin_data(raw_profile, person_name, linkedin_url, linkedin_id) or {}
    if not isinstance(analysis_result, dict):
        analysis_result = {}

    # Parallel AI tasks (best-effort with fallbacks; matches legacy analyzer behavior)
    tasks = []

    def _task(name: str, fn, args, fallback):
        def run():
            try:
                return name, fn(*args)
            except Exception:
                return name, fallback
        return run

    from server.linkedin_analyzer.role_model_service import get_linkedin_role_model
    from server.linkedin_analyzer.money_service import get_linkedin_money_analysis
    from server.linkedin_analyzer.roast_service import get_linkedin_roast
    from server.linkedin_analyzer.industry_knowledge_service import get_linkedin_industry_knowledge
    from server.linkedin_analyzer.tools_technologies_service import get_linkedin_tools_technologies
    from server.linkedin_analyzer.interpersonal_skills_service import get_linkedin_interpersonal_skills
    from server.linkedin_analyzer.language_service import get_linkedin_languages
    from server.linkedin_analyzer.colleagues_view_service import get_linkedin_colleagues_view
    from server.linkedin_analyzer.career_service import get_linkedin_career
    from server.linkedin_analyzer.life_well_being_service import get_linkedin_life_well_being

    tasks.append(_task("role_model", get_linkedin_role_model, (raw_profile, person_name), None))
    tasks.append(_task("money_analysis", get_linkedin_money_analysis, (raw_profile, person_name), None))
    tasks.append(_task("roast", get_linkedin_roast, (raw_profile, person_name), "No roast available"))
    tasks.append(_task("industry_knowledge", get_linkedin_industry_knowledge, (raw_profile, person_name), []))
    tasks.append(_task("tools_technologies", get_linkedin_tools_technologies, (raw_profile, person_name), []))
    tasks.append(_task("interpersonal_skills", get_linkedin_interpersonal_skills, (raw_profile, person_name), []))
    tasks.append(_task("language", get_linkedin_languages, (raw_profile, person_name), []))
    tasks.append(_task("colleagues_view", get_linkedin_colleagues_view, (raw_profile, person_name), {"highlights": [], "areas_for_improvement": []}))
    tasks.append(_task("career", get_linkedin_career, (raw_profile, person_name), {"future_development_potential": "", "development_advice": {"past_evaluation": "", "future_advice": ""}}))
    tasks.append(_task("life_well_being", get_linkedin_life_well_being, (raw_profile, person_name), {"life_suggestion": "", "health": ""}))

    results: Dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=max(4, len(tasks))) as executor:
        future_to_name = {executor.submit(t): i for i, t in enumerate(tasks)}
        total = max(1, len(future_to_name))
        completed = 0
        for fut in as_completed(future_to_name):
            try:
                name, value = fut.result()
                results[name] = value
            except Exception:
                pass
            completed += 1
            _emit(progress, "ai_step", f"LinkedIn AI step {completed}/{total} completed", {"completed": completed, "total": total})

    personal_tags = analyzer.extract_personal_tags(raw_profile)
    work_summary = analyzer.generate_work_experience_summary(raw_profile.get("experiences", []) or [])
    education_summary = analyzer.generate_education_summary(raw_profile.get("educations", []) or [])

    about_content = raw_profile.get("about")
    if not about_content or not str(about_content).strip():
        about_content = analyzer.generate_ai_about_section(raw_profile, person_name)

    profile_data = analysis_result.get("profile_data") if isinstance(analysis_result.get("profile_data"), dict) else {}
    profile_data.update(
        {
            "role_model": results.get("role_model"),
            "money_analysis": results.get("money_analysis"),
            "roast": results.get("roast"),
            "skills": {
                "industry_knowledge": results.get("industry_knowledge", []),
                "tools_technologies": results.get("tools_technologies", []),
                "interpersonal_skills": results.get("interpersonal_skills", []),
                "language": results.get("language", []),
            },
            "colleagues_view": results.get("colleagues_view"),
            "career": results.get("career"),
            "life_well_being": results.get("life_well_being"),
            "about": about_content,
            "personal_tags": personal_tags,
            "work_experience": raw_profile.get("experiences", []) or [],
            "work_experience_summary": work_summary,
            "education": raw_profile.get("educations", []) or [],
            "education_summary": education_summary,
            "avatar": raw_profile.get("profilePic"),
            "name": raw_profile.get("fullName") or person_name,
            "raw_profile": raw_profile,
        }
    )

    analysis_result["profile_data"] = profile_data
    return analysis_result


def _compact_linkedin_profile_for_llm(raw_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compact raw LinkedIn profile payload for LLM consumption.

    Apify raw profiles can be large; keep only stable, high-signal fields to control token/latency.
    """

    def _take_list(value: Any, *, limit: int) -> list:
        if not isinstance(value, list):
            return []
        return [v for v in value[: max(0, int(limit))] if v is not None]

    def _norm_text(value: Any, *, limit: int = 260) -> str:
        if value is None:
            return ""
        s = str(value).strip()
        if not s:
            return ""
        # Collapse whitespace and hard-trim long descriptions to keep prompts small.
        s = " ".join(s.split())
        if len(s) > int(limit):
            return s[: max(0, int(limit) - 1)].rstrip() + "…"
        return s

    def _compact_experience(exp: Any) -> Dict[str, Any]:
        if not isinstance(exp, dict):
            return {}
        return {
            "title": _norm_text(exp.get("title") or exp.get("position") or exp.get("jobTitle"), limit=80),
            "company": _norm_text(exp.get("companyName") or exp.get("company") or exp.get("companyNameText"), limit=80),
            "dateRange": _norm_text(exp.get("dateRange") or exp.get("date") or exp.get("timePeriod"), limit=60),
            "location": _norm_text(exp.get("location"), limit=80),
            "description": _norm_text(exp.get("description") or exp.get("summary") or exp.get("details"), limit=260),
        }

    def _compact_education(ed: Any) -> Dict[str, Any]:
        if not isinstance(ed, dict):
            return {}
        return {
            "school": _norm_text(ed.get("school") or ed.get("schoolName"), limit=100),
            "degree": _norm_text(ed.get("degree") or ed.get("degreeName"), limit=80),
            "field": _norm_text(ed.get("fieldOfStudy") or ed.get("field"), limit=80),
            "dateRange": _norm_text(ed.get("dateRange") or ed.get("date") or ed.get("timePeriod"), limit=60),
            "description": _norm_text(ed.get("description") or ed.get("activities"), limit=200),
        }

    def _compact_skill(x: Any) -> str:
        if x is None:
            return ""
        if isinstance(x, str):
            return _norm_text(x, limit=40)
        if isinstance(x, dict):
            for k in ("name", "title", "skill"):
                if x.get(k):
                    return _norm_text(x.get(k), limit=40)
        return _norm_text(x, limit=40)

    def _compact_language(x: Any) -> str:
        if x is None:
            return ""
        if isinstance(x, str):
            return _norm_text(x, limit=40)
        if isinstance(x, dict):
            for k in ("name", "title", "language"):
                if x.get(k):
                    return _norm_text(x.get(k), limit=40)
        return _norm_text(x, limit=40)

    profile = raw_profile if isinstance(raw_profile, dict) else {}

    return {
        "fullName": profile.get("fullName") or profile.get("name"),
        "headline": profile.get("headline") or profile.get("occupation") or profile.get("jobTitle"),
        "location": profile.get("addressWithCountry") or profile.get("location"),
        "companyName": profile.get("companyName"),
        "companyIndustry": profile.get("companyIndustry"),
        "connections": profile.get("connections"),
        "followers": profile.get("followers"),
        "about": _norm_text(profile.get("about"), limit=420),
        "experiences": [_compact_experience(e) for e in _take_list(profile.get("experiences"), limit=8)],
        "educations": [_compact_education(e) for e in _take_list(profile.get("educations"), limit=4)],
        "skills": [s for s in (_compact_skill(x) for x in _take_list(profile.get("skills"), limit=30)) if s],
        "languages": [s for s in (_compact_language(x) for x in _take_list(profile.get("languages"), limit=12)) if s],
    }


def run_linkedin_enrich_bundle(*, raw_report: Dict[str, Any], progress: Optional[ProgressFn] = None) -> Dict[str, Any]:
    """
    Run a single fused LLM call to generate all LinkedIn non-roast enrich outputs.

    Output is stored as an internal artifact (`resource.linkedin.enrich`) and then sliced by UI cards:
      - skills / career / money / summary / role_model

    Roast is intentionally handled separately (user-facing, optional-fail).
    """

    def emit(step: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        _emit(progress, step, message, data)

    profile_data = raw_report.get("profile_data") if isinstance(raw_report, dict) else None
    if not isinstance(profile_data, dict):
        raise ValueError("missing profile_data for linkedin enrich bundle")

    raw_profile = profile_data.get("raw_profile")
    if not isinstance(raw_profile, dict) or not raw_profile:
        raise ValueError("missing raw_profile for linkedin enrich bundle")

    # raw_profile may be pruned for storage; reconstruct required lists for downstream heuristics + LLM.
    work_experience = profile_data.get("work_experience") if isinstance(profile_data.get("work_experience"), list) else []
    education = profile_data.get("education") if isinstance(profile_data.get("education"), list) else []
    if work_experience and (not isinstance(raw_profile.get("experiences"), list) or not raw_profile.get("experiences")):
        raw_profile = dict(raw_profile)
        raw_profile["experiences"] = work_experience
    if education and (not isinstance(raw_profile.get("educations"), list) or not raw_profile.get("educations")):
        raw_profile = dict(raw_profile)
        raw_profile["educations"] = education

    person_name = str(profile_data.get("name") or raw_profile.get("fullName") or "Unknown").strip() or "Unknown"

    # Deterministic role_model (no LLM): reduces call fan-out and avoids huge celebrity-list prompts.
    role_model: Dict[str, Any] = {}
    try:
        from server.linkedin_analyzer.role_model_service import (
            fallback_celebrity_check,
            find_celebrity_with_rules,
            create_enhanced_self_role_model,
            create_self_role_model,
        )

        celebrity = fallback_celebrity_check(raw_profile, person_name)
        if celebrity:
            role_model = create_enhanced_self_role_model(raw_profile, person_name, "Heuristic celebrity indicators")
            role_model["is_celebrity"] = True
            role_model["celebrity_reasoning"] = "Heuristic celebrity indicators"
        else:
            rm = find_celebrity_with_rules(raw_profile, person_name)
            if isinstance(rm, dict) and rm:
                role_model = rm
                role_model["is_celebrity"] = False
                role_model["celebrity_reasoning"] = "Heuristic non-celebrity profile"
            else:
                role_model = create_self_role_model(raw_profile, person_name)
                role_model["is_celebrity"] = False
                role_model["celebrity_reasoning"] = "No strong match; using self role model"
    except Exception:
        role_model = {"name": person_name, "similarity_reason": "Self role model", "is_celebrity": False}

    compact = _compact_linkedin_profile_for_llm(raw_profile)

    system = (
        "You are an expert LinkedIn profile analyst.\n"
        "Return ONLY valid JSON. Do not wrap in markdown.\n"
        "All text must be in English.\n"
        "Never output 'No data' placeholders. If data is missing, infer a reasonable, conservative answer.\n"
    )

    user = json.dumps(
        {
            "person_name": person_name,
            "profile": compact,
            "instructions": {
                "skills": "Return 3-6 items per list; use concise noun phrases.",
                "career": "Keep advice specific and actionable; avoid generic clichés.",
                "summaries": "work_experience_summary 40-60 words; education_summary 30-50 words.",
                "about": "If profile.about is empty, generate a 40-60 word first-person about section.",
                "tags": "Return 4-6 personal_tags (Title Case).",
            },
            "output_schema": {
                "skills": {
                    "industry_knowledge": ["string"],
                    "tools_technologies": ["string"],
                    "interpersonal_skills": ["string"],
                    "language": ["string"],
                },
                "career": {
                    "future_development_potential": "string",
                    "simplified_future_development_potential": "string",
                    "development_advice": {
                        "past_evaluation": "string",
                        "simplified_past_evaluation": "string",
                        "future_advice": "string",
                    },
                },
                "work_experience_summary": "string",
                "education_summary": "string",
                "summary": {"about": "string", "personal_tags": ["string"]},
            },
        },
        ensure_ascii=False,
    )

    try:
        timeout_s = float(os.getenv("DINQ_LINKEDIN_ENRICH_TIMEOUT_SECONDS", "40") or "40")
    except Exception:
        timeout_s = 40.0
    timeout_s = max(5.0, min(float(timeout_s), 120.0))

    emit("ai_bundle", "Generating fused LinkedIn enrich bundle...", {"timeout_seconds": timeout_s})
    t0 = now_perf()
    out: Any = None
    try:
        out = openrouter_chat(
            task="linkedin_enrich_bundle",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.3,
            max_tokens=1400,
            expect_json=True,
            stream=False,
            cache=False,
            timeout_seconds=timeout_s,
        )
    except requests.exceptions.Timeout:
        out = None
    except Exception:
        out = None
    emit("timing.linkedin.enrich_bundle", "LinkedIn enrich bundle completed", {"duration_ms": elapsed_ms(t0)})

    payload = out if isinstance(out, dict) else {}

    skills = payload.get("skills") if isinstance(payload.get("skills"), dict) else {}
    career = payload.get("career") if isinstance(payload.get("career"), dict) else {}
    money = payload.get("money") if isinstance(payload.get("money"), dict) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}

    # Ensure required non-empty about for quality gate.
    about = str(summary.get("about") or raw_profile.get("about") or "").strip()
    if not about:
        about = f"I am a {str(compact.get('headline') or 'professional').strip() or 'professional'} focused on delivering impact through my work."
    personal_tags = summary.get("personal_tags") if isinstance(summary.get("personal_tags"), list) else []

    # Deterministic money fallback if model output is empty/invalid.
    if not money:
        try:
            from server.linkedin_analyzer.money_service import create_default_money_analysis

            money = create_default_money_analysis(raw_profile, person_name)
        except Exception:
            money = {"estimated_salary": "Unknown", "explanation": "Unavailable"}

    # Best-effort: if model fails to produce any skills lists, provide a minimal placeholder list
    # so the card completes (quality gate accepts fallback meta if needed downstream).
    if not any(isinstance(v, list) and v for v in skills.values()):
        raw_skills = compact.get("skills") if isinstance(compact.get("skills"), list) else []
        raw_langs = compact.get("languages") if isinstance(compact.get("languages"), list) else []

        def _dedup(items: list[Any], *, limit: int) -> list[str]:
            out: list[str] = []
            seen: set[str] = set()
            for x in items:
                s = str(x or "").strip()
                if not s:
                    continue
                k = s.lower()
                if k in seen:
                    continue
                seen.add(k)
                out.append(s)
                if len(out) >= int(limit):
                    break
            return out

        tool_keywords = (
            "excel",
            "powerpoint",
            "word",
            "google",
            "workspace",
            "slack",
            "jira",
            "confluence",
            "sql",
            "python",
            "java",
            "c++",
            "aws",
            "gcp",
            "azure",
            "tableau",
            "power bi",
            "snowflake",
            "databricks",
            "kubernetes",
            "docker",
            "git",
            "github",
        )

        tools: list[str] = []
        industry: list[str] = []
        for s in _dedup(raw_skills, limit=24):
            low = s.lower()
            if any(k in low for k in tool_keywords):
                tools.append(s)
            else:
                industry.append(s)

        headline = str(compact.get("headline") or "").strip()
        company_industry = str(compact.get("companyIndustry") or "").strip()
        if headline:
            industry = _dedup([headline] + industry, limit=10)
        if company_industry:
            industry = _dedup([company_industry] + industry, limit=10)

        if not tools:
            tools = ["Microsoft Excel", "PowerPoint", "Google Workspace"]
        if not industry:
            industry = ["Domain Expertise", "Strategy", "Market Analysis"]

        interpersonal = [
            "Leadership" if any(x in headline.lower() for x in ("director", "head", "manager", "lead", "vp")) else "Team Collaboration",
            "Stakeholder Management",
            "Communication",
            "Problem Solving",
        ]

        languages = _dedup(raw_langs, limit=6) or ["English"]

        skills = {
            "industry_knowledge": _dedup(industry, limit=6),
            "tools_technologies": _dedup(tools, limit=6),
            "interpersonal_skills": _dedup(interpersonal, limit=6),
            "language": languages,
        }

    # Ensure summaries are non-empty strings.
    work_summary = str(payload.get("work_experience_summary") or "").strip()
    if not work_summary:
        exps = compact.get("experiences") if isinstance(compact.get("experiences"), list) else []
        picks = []
        for e in exps[:3]:
            if not isinstance(e, dict):
                continue
            title = str(e.get("title") or "").strip()
            company = str(e.get("company") or "").strip()
            if title and company:
                picks.append(f"{title} at {company}")
            elif title:
                picks.append(title)
            elif company:
                picks.append(company)
        if picks:
            joined = ", ".join(picks[:2]) + (f", and {picks[2]}" if len(picks) >= 3 else "")
            work_summary = f"Career includes roles such as {joined}. Demonstrates steady progression and impact through strategic ownership, domain expertise, and cross-functional collaboration."
        else:
            work_summary = "Experienced professional with a track record across multiple roles and organizations."
    edu_summary = str(payload.get("education_summary") or "").strip()
    if not edu_summary:
        edus = compact.get("educations") if isinstance(compact.get("educations"), list) else []
        picks = []
        for e in edus[:2]:
            if not isinstance(e, dict):
                continue
            school = str(e.get("school") or "").strip()
            degree = str(e.get("degree") or "").strip()
            field = str(e.get("field") or "").strip()
            parts = []
            if degree:
                parts.append(degree)
            if field:
                parts.append(field)
            left = ", ".join(parts).strip()
            if left and school:
                picks.append(f"{left} at {school}")
            elif school:
                picks.append(school)
        if picks:
            edu_summary = f"Education background includes {', '.join(picks)}. This foundation supports continued growth through applied learning and real-world execution."
        else:
            edu_summary = "Education background supports a strong foundation for continued professional growth."

    if not personal_tags:
        pools: list[str] = []
        for k in ("industry_knowledge", "tools_technologies", "interpersonal_skills", "language"):
            v = skills.get(k) if isinstance(skills, dict) else None
            if isinstance(v, list):
                pools.extend(v)
        personal_tags = pools[:6]

    return {
        "skills": skills,
        "career": career,
        "work_experience_summary": work_summary,
        "education_summary": edu_summary,
        "money": money,
        "summary": {"about": about, "personal_tags": personal_tags},
        "role_model": role_model,
    }
