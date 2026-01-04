"""Quality gates for unified analysis card outputs.

Goals:
- Keep frontend simple by ensuring `internal=false` cards always complete with a usable payload.
- Prevent silent `{}` / `null` payloads from being marked as completed (unless explicitly UNAVAILABLE).
- Provide a single place to normalize/validate/fallback for each business card.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Literal, Optional, Tuple


GateAction = Literal["accept", "retry", "fallback"]


@dataclass(frozen=True)
class GateIssue:
    code: str
    message: str
    retryable: bool = True
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GateDecision:
    action: GateAction
    normalized: Any
    issue: Optional[GateIssue] = None


@dataclass(frozen=True)
class GateContext:
    source: str
    card_type: str
    job_id: Optional[str] = None
    user_id: Optional[str] = None
    full_report: Optional[Dict[str, Any]] = None
    # Optional dependency inputs for cross-checking (e.g. resource artifacts)
    artifacts: Dict[str, Any] = field(default_factory=dict)


ValidatorFn = Callable[[Any, GateContext], GateDecision]


def _is_nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _default_validator(data: Any, ctx: GateContext) -> GateDecision:
    # Conservative default: accept dict payloads; retry on empty/None.
    if data is None:
        return GateDecision(action="retry", normalized={}, issue=GateIssue(code="empty_payload", message="Empty payload", retryable=True))
    if isinstance(data, dict):
        if not data:
            return GateDecision(action="retry", normalized={}, issue=GateIssue(code="empty_payload", message="Empty payload", retryable=True))
        return GateDecision(action="accept", normalized=data)
    # Unexpected types: coerce into a dict to keep output stable, but retry once.
    return GateDecision(
        action="retry",
        normalized={"value": data},
        issue=GateIssue(code="invalid_type", message=f"Unexpected payload type: {type(data).__name__}", retryable=True),
    )


_VALIDATORS: Dict[Tuple[str, str], ValidatorFn] = {}


def register_validator(source: str, card_type: str, fn: ValidatorFn) -> None:
    key = (str(source or "").strip().lower(), str(card_type or "").strip())
    if not key[0] or not key[1]:
        raise ValueError("register_validator requires non-empty source and card_type")
    _VALIDATORS[key] = fn


def validate_card_output(*, source: str, card_type: str, data: Any, ctx: Optional[GateContext] = None) -> GateDecision:
    src = str(source or "").strip().lower()
    ct = str(card_type or "").strip()
    context = ctx or GateContext(source=src, card_type=ct)
    # If a payload is already a declared fallback, treat it as acceptable to avoid
    # thrashing (e.g., repeatedly recomputing a card that reliably fails upstream).
    if isinstance(data, dict):
        meta = data.get("_meta")
        if isinstance(meta, dict) and meta.get("fallback") is True:
            return GateDecision(action="accept", normalized=data)
    fn = _VALIDATORS.get((src, ct), _default_validator)
    try:
        return fn(data, context)
    except Exception as exc:  # noqa: BLE001
        # Safety: never crash the pipeline due to validation code.
        return GateDecision(
            action="accept",
            normalized=_as_dict(data),
            issue=GateIssue(code="validator_error", message=str(exc), retryable=False),
        )


def merge_meta(payload: Any, meta: Dict[str, Any]) -> Any:
    """Attach non-breaking debug meta into dict payloads."""
    if not isinstance(meta, dict) or not meta:
        return payload
    if not isinstance(payload, dict):
        return payload
    merged = dict(payload)
    existing = merged.get("_meta")
    if isinstance(existing, dict):
        out = dict(existing)
        out.update(meta)
        merged["_meta"] = out
    else:
        merged["_meta"] = dict(meta)
    return merged


def fallback_card_output(
    *,
    source: str,
    card_type: str,
    ctx: GateContext,
    last_decision: Optional[GateDecision] = None,
    error: Optional[Exception] = None,
) -> Any:
    """
    Deterministic, no-network fallback payloads.

    This is used only after retry budgets are exhausted. The goal is:
    - Avoid `{}` / `null` for business cards
    - Provide a user-facing hint that data is unavailable
    """

    src = str(source or "").strip().lower()
    ct = str(card_type or "").strip()

    # Try to preserve any partially-computed structure.
    base = _as_dict(getattr(last_decision, "normalized", None)) if last_decision else {}
    err_text = str(error) if error else (last_decision.issue.message if last_decision and last_decision.issue else "")

    def _meta(code: str) -> Dict[str, Any]:
        out: Dict[str, Any] = {"fallback": True, "code": code, "preserve_empty": True}
        if err_text:
            out["error"] = err_text[:500]
        return out

    if src == "github":
        if ct == "role_model":
            payload = base if base else {"reason": "暂时无法生成 role model（稍后可重试）"}
            return merge_meta(payload, _meta("fallback_role_model"))
        if ct == "roast":
            roast = str(base.get("roast") or "").strip()
            if not roast:
                roast = "暂时无法生成 Roast（可能是模型/网络异常），建议稍后重试。"
            return merge_meta({"roast": roast}, _meta("fallback_roast"))
        if ct == "repos":
            payload = {
                "feature_project": base.get("feature_project"),
                "top_projects": _as_list(base.get("top_projects")),
                "most_valuable_pull_request": base.get("most_valuable_pull_request"),
            }
            # If validator requires MVP PR (user has PRs) but we couldn't compute it, return an explicit placeholder.
            if payload.get("most_valuable_pull_request") is None:
                payload["most_valuable_pull_request"] = {
                    "reason": "暂时无法提取 most valuable pull request（可能是 GitHub API/限流），建议稍后重试。",
                    "impact": "Unavailable",
                }
            return merge_meta(payload, _meta("fallback_repos"))
        if ct == "summary":
            valuation = base.get("valuation_and_level")
            if not isinstance(valuation, dict):
                valuation = {}
            normalized_val = dict(valuation)
            normalized_val.setdefault("level", "")
            normalized_val.setdefault("salary_range", [None, None])
            normalized_val.setdefault("industry_ranking", None)
            normalized_val.setdefault("growth_potential", "")
            normalized_val.setdefault("reasoning", "")

            desc = str(base.get("description") or "").strip()
            if not desc:
                login = ""
                if isinstance(ctx.full_report, dict):
                    user = ctx.full_report.get("user")
                    if isinstance(user, dict):
                        login = str(user.get("login") or "").strip()
                desc = f"GitHub profile summary{(' for ' + login) if login else ''}."
            return merge_meta({"valuation_and_level": normalized_val, "description": desc}, _meta("fallback_summary"))

    if src == "scholar":
        if ct == "coauthors":
            return merge_meta(_accept_with_defaults(base, {"main_author": None, "total_coauthors": 0, "collaboration_index": 0, "top_coauthors": [], "most_frequent_collaborator": None}).normalized, _meta("fallback_coauthors"))
        if ct == "papers":
            payload = base if base else {}
            payload.setdefault("most_cited_paper", None)
            payload.setdefault("paper_of_year", None)
            payload.setdefault("top_tier_publications", {"conferences": [], "journals": []})
            payload.setdefault("year_distribution", {})
            return merge_meta(payload, _meta("fallback_papers"))
        if ct == "role_model":
            payload = base if base else {"name": "", "similarity_reason": "暂时无法生成 role model（稍后可重试）"}
            return merge_meta(payload, _meta("fallback_role_model"))
        if ct == "news":
            payload = base if base else {}
            payload.setdefault("news", "暂无相关新闻")
            payload.setdefault("date", "")
            payload.setdefault("description", "未能获取相关新闻（可能无可用来源或数据不足）。")
            payload.setdefault("url", None)
            payload["is_fallback"] = True
            return merge_meta(payload, _meta("fallback_news"))
        if ct == "level":
            payload = base if base else {}
            payload.setdefault("level_cn", "")
            payload.setdefault("level_us", "")
            payload.setdefault("earnings", "")
            payload.setdefault("justification", "暂时无法评估 level（数据不足或模型异常），建议稍后重试。")
            payload["is_fallback"] = True
            return merge_meta(payload, _meta("fallback_level"))
        if ct == "summary":
            ce = str(base.get("critical_evaluation") or "").strip()
            if not ce:
                ce = "暂时无法生成总结（可能是模型/网络异常），建议稍后重试。"
            return merge_meta({"critical_evaluation": ce}, _meta("fallback_summary"))

    if src == "linkedin":
        if ct == "skills":
            payload = {
                "industry_knowledge": _as_list(base.get("industry_knowledge")),
                "tools_technologies": _as_list(base.get("tools_technologies")),
                "interpersonal_skills": _as_list(base.get("interpersonal_skills")),
                "language": _as_list(base.get("language")),
            }
            return merge_meta(payload, _meta("fallback_skills"))
        if ct == "career":
            payload = {
                "career": _as_dict(base.get("career")),
                "work_experience": _as_list(base.get("work_experience")),
                "education": _as_list(base.get("education")),
                "work_experience_summary": str(base.get("work_experience_summary") or "").strip()
                or "暂时无法生成工作经历总结（可能是抓取/解析失败），建议稍后重试。",
                "education_summary": str(base.get("education_summary") or "").strip()
                or "暂时无法生成教育经历总结（可能是抓取/解析失败），建议稍后重试。",
            }
            return merge_meta(payload, _meta("fallback_career"))
        if ct == "colleagues_view":
            payload = {
                "highlights": _as_list(base.get("highlights")),
                "areas_for_improvement": _as_list(base.get("areas_for_improvement")),
            }
            return merge_meta(payload, _meta("fallback_colleagues_view"))
        if ct == "life_well_being":
            payload = {
                "life_suggestion": str(base.get("life_suggestion") or "").strip(),
                "health": str(base.get("health") or "").strip(),
            }
            return merge_meta(payload, _meta("fallback_life_well_being"))
        if ct == "role_model":
            payload = base if base else {"reason": "暂时无法生成 role model（稍后可重试）"}
            return merge_meta(payload, _meta("fallback_role_model"))
        if ct == "money":
            payload = base if base else {}
            normalized = {
                "years_of_experience": payload.get("years_of_experience") if isinstance(payload.get("years_of_experience"), dict) else {},
                "level_us": payload.get("level_us"),
                "level_cn": payload.get("level_cn"),
                "estimated_salary": str(payload.get("estimated_salary") or "").replace(",", "").replace("$", "").strip(),
                "explanation": str(payload.get("explanation") or "").strip(),
            }
            return merge_meta(normalized, _meta("fallback_money"))
        if ct == "roast":
            roast = str(base.get("roast") or "").strip()
            if not roast:
                roast = "暂时无法生成 Roast（可能是模型/网络异常），建议稍后重试。"
            return merge_meta({"roast": roast}, _meta("fallback_roast"))
        if ct == "summary":
            about = str(base.get("about") or "").strip()
            if not about:
                about = "暂时无法生成 About（可能是模型/网络异常），建议稍后重试。"
            payload = {"about": about, "personal_tags": _as_list(base.get("personal_tags"))}
            return merge_meta(payload, _meta("fallback_summary"))

    if src == "twitter" and ct == "summary":
        summary = str(base.get("summary") or "").strip() or "暂时无法生成总结（稍后可重试）。"
        return merge_meta({"summary": summary}, _meta("fallback_summary"))

    if src == "openreview" and ct == "summary":
        summary = str(base.get("summary") or "").strip() or "暂时无法生成总结（稍后可重试）。"
        return merge_meta({"summary": summary}, _meta("fallback_summary"))

    if src == "youtube" and ct == "summary":
        payload = _as_dict(base)
        if not _is_nonempty_str(payload.get("content_summary")):
            payload["content_summary"] = "暂时无法生成频道内容总结（稍后可重试）。"
        return merge_meta(payload, _meta("fallback_summary"))

    # Generic fallback: ensure a non-empty dict so the UI won't see `{}`.
    payload = base if base else {"reason": "暂时无法生成该卡片内容，建议稍后重试。"}
    return merge_meta(payload, _meta("fallback_generic"))


def _accept_with_defaults(data: Any, defaults: Dict[str, Any]) -> GateDecision:
    payload = dict(defaults)
    if isinstance(data, dict):
        payload.update(data)
    return GateDecision(action="accept", normalized=payload)


def _retry_empty_dict(data: Any, *, code: str, message: str) -> GateDecision:
    if not isinstance(data, dict) or not data:
        return GateDecision(action="retry", normalized=_as_dict(data), issue=GateIssue(code=code, message=message, retryable=True))
    return GateDecision(action="accept", normalized=data)


def _scholar_profile(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)
    name = payload.get("name")
    scholar_id = payload.get("scholar_id")
    if _is_nonempty_str(name) or _is_nonempty_str(scholar_id):
        return GateDecision(action="accept", normalized=payload)
    return GateDecision(
        action="retry",
        normalized=payload,
        issue=GateIssue(code="missing_identity", message="Missing scholar name/id", retryable=True),
    )


def _scholar_metrics(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)
    total_papers = payload.get("total_papers")
    year_dist = payload.get("year_distribution")
    try:
        papers = int(total_papers or 0)
    except Exception:
        papers = 0
    if papers > 0 or isinstance(year_dist, dict):
        return GateDecision(action="accept", normalized=payload)
    return GateDecision(action="retry", normalized=payload, issue=GateIssue(code="missing_metrics", message="Missing scholar metrics", retryable=True))


def _scholar_papers(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)
    items = payload.get("items")
    if not isinstance(items, list):
        items = []
    # Keep payload bounded; UI only needs a preview list here.
    try:
        max_items = int(os.getenv("DINQ_SCHOLAR_PAPERS_MAX_ITEMS", "200") or "200")
    except Exception:
        max_items = 200
    max_items = max(0, min(int(max_items), 1000))
    if max_items and len(items) > max_items:
        items = list(items[:max_items])

    normalized = {
        "most_cited_paper": payload.get("most_cited_paper"),
        "paper_of_year": payload.get("paper_of_year"),
        "top_tier_publications": payload.get("top_tier_publications"),
        "year_distribution": payload.get("year_distribution"),
        "items": items,
    }
    if items or any(v for k, v in normalized.items() if k != "items" and v not in (None, "", [], {})):
        return GateDecision(action="accept", normalized=normalized)
    return GateDecision(action="retry", normalized=normalized, issue=GateIssue(code="missing_papers", message="Missing paper highlights", retryable=True))


def _scholar_coauthors(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)
    defaults = {
        "main_author": None,
        "total_coauthors": 0,
        "collaboration_index": 0,
        "top_coauthors": [],
        "most_frequent_collaborator": None,
    }
    return _accept_with_defaults(payload, defaults)


def _scholar_role_model(data: Any, ctx: GateContext) -> GateDecision:
    return _retry_empty_dict(data, code="empty_role_model", message="Missing role model analysis")


def _scholar_news(data: Any, ctx: GateContext) -> GateDecision:
    return _retry_empty_dict(data, code="empty_news", message="Missing news analysis")


def _scholar_level(data: Any, ctx: GateContext) -> GateDecision:
    return _retry_empty_dict(data, code="empty_level", message="Missing level analysis")


def _scholar_citations(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)
    for key in ("total_citations", "h_index", "citations_5y", "h_index_5y"):
        if payload.get(key) is not None:
            return GateDecision(action="accept", normalized=payload)
    return GateDecision(action="retry", normalized=payload, issue=GateIssue(code="missing_citations", message="Missing citation stats", retryable=True))


def _scholar_summary(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)
    ce = payload.get("critical_evaluation")
    if isinstance(ce, dict) and ce:
        return GateDecision(action="accept", normalized=payload)
    if _is_nonempty_str(ce):
        return GateDecision(action="accept", normalized=payload)
    return GateDecision(action="retry", normalized=payload, issue=GateIssue(code="empty_summary", message="Missing critical evaluation", retryable=True))


def _scholar_researcher_info(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)
    name = payload.get("name")
    scholar_id = payload.get("scholarId") or payload.get("scholar_id")
    if _is_nonempty_str(name) or _is_nonempty_str(scholar_id):
        return GateDecision(action="accept", normalized=payload)
    return GateDecision(action="retry", normalized=payload, issue=GateIssue(code="missing_identity", message="Missing scholar researcherInfo", retryable=True))


def _scholar_block(data: Any, ctx: GateContext) -> GateDecision:
    return _retry_empty_dict(data, code="empty_block", message="Missing scholar formatted block")


def _scholar_estimated_salary(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)
    earnings = payload.get("earningsPerYearUSD")
    try:
        earnings_i = int(earnings) if earnings is not None and not isinstance(earnings, bool) else None
    except Exception:
        earnings_i = None
    if earnings_i is not None and earnings_i > 0:
        return GateDecision(action="accept", normalized=payload)
    # Keep blockTitle so the UI sees a stable shape while retrying.
    normalized = dict(payload) if payload else {"blockTitle": "Estimated Salary"}
    return GateDecision(
        action="retry",
        normalized=normalized,
        issue=GateIssue(code="missing_salary", message="Missing scholar estimated salary", retryable=True),
    )


def _scholar_critical_review(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)
    evaluation = payload.get("evaluation")
    if _is_nonempty_str(evaluation):
        return GateDecision(action="accept", normalized=payload)
    # Keep blockTitle so the UI doesn't see `{}` even while retrying.
    normalized = dict(payload) if payload else {"blockTitle": "Roast", "evaluation": None}
    return GateDecision(action="retry", normalized=normalized, issue=GateIssue(code="empty_evaluation", message="Missing critical review evaluation", retryable=True))


def _github_profile(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)
    login = payload.get("login") or payload.get("username")
    name = payload.get("name")
    if _is_nonempty_str(login) or _is_nonempty_str(name):
        return GateDecision(action="accept", normalized=payload)
    return GateDecision(action="retry", normalized=payload, issue=GateIssue(code="missing_identity", message="Missing GitHub login/name", retryable=True))


def _github_activity(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)
    overview = payload.get("overview")
    activity = payload.get("activity")
    if isinstance(overview, dict) and overview:
        return GateDecision(action="accept", normalized=payload)
    if isinstance(activity, dict) and activity:
        return GateDecision(action="accept", normalized=payload)
    # Normalize expected keys to avoid UI shape drift.
    normalized = {"overview": overview if isinstance(overview, dict) else {}, "activity": activity if isinstance(activity, dict) else {}, "code_contribution": payload.get("code_contribution")}
    return GateDecision(action="retry", normalized=normalized, issue=GateIssue(code="missing_activity", message="Missing GitHub activity overview", retryable=True))


def _github_repos(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)
    normalized = {
        "feature_project": payload.get("feature_project"),
        "top_projects": _as_list(payload.get("top_projects")),
        "most_valuable_pull_request": payload.get("most_valuable_pull_request"),
    }

    # Accept if we at least have some repos data.
    has_any_repo = bool(normalized["feature_project"]) or bool(normalized["top_projects"])
    repo_total = None
    if isinstance(ctx.full_report, dict):
        overview = ctx.full_report.get("overview")
        if isinstance(overview, dict):
            repo_total = overview.get("repositories")
        if repo_total is None:
            user = ctx.full_report.get("user")
            if isinstance(user, dict):
                repos = user.get("repositories")
                if isinstance(repos, dict):
                    repo_total = repos.get("totalCount")
    if repo_total is None and isinstance(ctx.artifacts.get("resource.github.data"), dict):
        overview = ctx.artifacts.get("resource.github.data", {}).get("overview")
        if isinstance(overview, dict):
            repo_total = overview.get("repositories")
    try:
        repo_total_int = int(repo_total or 0)
    except Exception:
        repo_total_int = 0

    if repo_total_int <= 0:
        return GateDecision(action="accept", normalized=normalized)

    if not has_any_repo:
        return GateDecision(action="retry", normalized=normalized, issue=GateIssue(code="missing_repos", message="Missing GitHub repos summary", retryable=True))

    # MVP PR is optional (upstream allows null); never fail the repos card because it's missing.
    # Instead, attach meta so the UI/debugging can see why it's empty.
    if not normalized.get("most_valuable_pull_request"):
        pr_total = 0
        user = None
        if isinstance(ctx.full_report, dict):
            user = ctx.full_report.get("user")
        if not isinstance(user, dict):
            user = _as_dict(ctx.artifacts.get("resource.github.data")).get("user") if isinstance(ctx.artifacts.get("resource.github.data"), dict) else None
        if isinstance(user, dict):
            prs = user.get("pullRequests")
            if isinstance(prs, dict):
                try:
                    pr_total = int(prs.get("totalCount") or 0)
                except Exception:
                    pr_total = 0

        meta_existing = normalized.get("_meta")
        meta: Dict[str, Any] = meta_existing if isinstance(meta_existing, dict) else {}
        meta = dict(meta)
        meta.update(
            {
                "fallback": True,
                "code": "missing_mvp_pr",
                "missing": ["most_valuable_pull_request"],
                "details": {"pull_requests_total": pr_total},
            }
        )
        normalized["_meta"] = meta

    return GateDecision(action="accept", normalized=normalized)


def _github_role_model(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)
    name = str(payload.get("name") or "").strip()
    github = str(payload.get("github") or "").strip()

    def _extract_login(value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        lowered = raw.lower()
        if lowered.startswith("http://") or lowered.startswith("https://"):
            parts = lowered.split("github.com/", 1)
            if len(parts) == 2:
                tail = parts[1].split("?", 1)[0].split("#", 1)[0].strip("/")
                if tail:
                    return tail.split("/", 1)[0].strip()
        return raw.strip().lstrip("@").split("/", 1)[0].strip()

    # Prefer non-self role models, but allow self as a last-resort fallback.
    user_login = ""
    user_url = ""
    art = ctx.artifacts.get("resource.github.data")
    if isinstance(art, dict):
        u = art.get("user") if isinstance(art.get("user"), dict) else {}
        user_login = str(u.get("login") or "").strip().lower()
        user_url = str(u.get("url") or "").strip().lower().rstrip("/")

    rm_login = _extract_login(github).lower()
    rm_url = str(github).strip().lower().rstrip("/")
    is_self = bool(user_login and rm_login and rm_login == user_login) or bool(user_url and rm_url and rm_url == user_url)

    missing: list[str] = []
    if not name:
        missing.append("name")
    if not github:
        missing.append("github")
    if is_self:
        missing.append("self_role_model")

    normalized = dict(payload)
    if "name" not in normalized:
        normalized["name"] = name
    if "github" not in normalized:
        normalized["github"] = github
    if missing:
        normalized["_meta"] = {"fallback": True, "code": "unavailable", "preserve_empty": True, "missing": missing}
    return GateDecision(action="accept", normalized=normalized)


def _github_roast(data: Any, ctx: GateContext) -> GateDecision:
    roast_text = ""
    if isinstance(data, dict):
        roast_text = str(data.get("roast") or "").strip()
    else:
        roast_text = str(data or "").strip()

    if roast_text:
        return GateDecision(action="accept", normalized={"roast": roast_text})

    # Keep schema stable while retrying.
    return GateDecision(
        action="retry",
        normalized={"roast": None},
        issue=GateIssue(code="empty_roast", message="Missing roast text", retryable=True),
    )


def _github_summary(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)

    valuation = payload.get("valuation_and_level")
    if not isinstance(valuation, dict):
        # Backward-compat: some older payloads stored only the valuation dict.
        valuation = dict(payload) if payload else {}
        payload = {"valuation_and_level": valuation, "description": ""}

    normalized = {
        "valuation_and_level": valuation,
        "description": str(payload.get("description") or "").strip(),
    }

    level = str(valuation.get("level") or "").strip()
    if level:
        return GateDecision(action="accept", normalized=normalized)

    return GateDecision(
        action="retry",
        normalized=normalized,
        issue=GateIssue(code="missing_level", message="Missing GitHub valuation level", retryable=True),
    )


def _linkedin_profile(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)
    # Try to find an identity hint either in normalized profile_data or raw_profile.
    name = payload.get("name")
    raw_profile = payload.get("raw_profile")
    if isinstance(raw_profile, dict) and not name:
        name = raw_profile.get("fullName") or raw_profile.get("name")
    if _is_nonempty_str(name):
        return GateDecision(action="accept", normalized=payload)
    if payload:
        return GateDecision(action="accept", normalized=payload)
    return GateDecision(action="retry", normalized=payload, issue=GateIssue(code="missing_profile", message="Missing LinkedIn profile", retryable=True))


def _linkedin_skills(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)
    normalized = {
        "industry_knowledge": _as_list(payload.get("industry_knowledge")),
        "tools_technologies": _as_list(payload.get("tools_technologies")),
        "interpersonal_skills": _as_list(payload.get("interpersonal_skills")),
        "language": _as_list(payload.get("language")),
    }
    if any(normalized.values()):
        return GateDecision(action="accept", normalized=normalized)
    return GateDecision(action="retry", normalized=normalized, issue=GateIssue(code="empty_skills", message="Missing LinkedIn skills breakdown", retryable=True))


def _linkedin_career(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)
    normalized = {
        "career": _as_dict(payload.get("career")),
        "work_experience": _as_list(payload.get("work_experience")),
        "education": _as_list(payload.get("education")),
        "work_experience_summary": str(payload.get("work_experience_summary") or "").strip(),
        "education_summary": str(payload.get("education_summary") or "").strip(),
    }

    # Cross-check raw profile when available: if raw contains experiences/educations but output is empty, retry.
    raw_profile: Dict[str, Any] = {}
    prof_for_check: Dict[str, Any] = {}
    if isinstance(ctx.full_report, dict):
        prof = ctx.full_report.get("profile_data")
        if isinstance(prof, dict):
            prof_for_check = prof
            if isinstance(prof.get("raw_profile"), dict):
                raw_profile = prof.get("raw_profile") or {}
    if not prof_for_check:
        art = ctx.artifacts.get("resource.linkedin.raw_profile")
        if isinstance(art, dict):
            prof = art.get("profile_data")
            if isinstance(prof, dict):
                prof_for_check = prof
                if isinstance(prof.get("raw_profile"), dict):
                    raw_profile = prof.get("raw_profile") or {}

    # Prefer the normalized lists from profile_data (raw_profile may be pruned for storage).
    raw_exp = prof_for_check.get("work_experience") if isinstance(prof_for_check.get("work_experience"), list) else []
    raw_edu = prof_for_check.get("education") if isinstance(prof_for_check.get("education"), list) else []
    if not raw_exp:
        raw_exp = raw_profile.get("experiences") if isinstance(raw_profile.get("experiences"), list) else []
    if not raw_edu:
        raw_edu = raw_profile.get("educations") if isinstance(raw_profile.get("educations"), list) else []

    if raw_exp and not normalized["work_experience"]:
        return GateDecision(action="retry", normalized=normalized, issue=GateIssue(code="missing_work_experience", message="Missing work experience extraction", retryable=True, details={"raw_experiences": len(raw_exp)}))
    if raw_edu and not normalized["education"]:
        return GateDecision(action="retry", normalized=normalized, issue=GateIssue(code="missing_education", message="Missing education extraction", retryable=True, details={"raw_educations": len(raw_edu)}))

    # Otherwise accept normalized shape.
    return GateDecision(action="accept", normalized=normalized)


def _linkedin_role_model(data: Any, ctx: GateContext) -> GateDecision:
    return _retry_empty_dict(data, code="empty_role_model", message="Missing LinkedIn role model")


def _linkedin_money(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)

    years = payload.get("years_of_experience")
    if not isinstance(years, dict):
        years = {}

    level_us = str(payload.get("level_us") or "").strip() or None
    level_cn = str(payload.get("level_cn") or "").strip() or None

    est_raw = payload.get("estimated_salary")
    if not est_raw:
        est_raw = payload.get("earnings") or payload.get("salary_range") or payload.get("total_compensation")

    expl_raw = payload.get("explanation")
    if not expl_raw:
        expl_raw = payload.get("justification") or payload.get("reasoning")

    est = str(est_raw or "").strip()
    if est:
        est = est.replace(",", "").replace("$", "").strip()
        est = est.replace("–", "-").replace("—", "-").replace("~", "-").replace("〜", "-").replace("～", "-")
        est = est.replace("USD", "").replace("usd", "").strip()
        est = " ".join(est.split())
        est = est.replace(" to ", "-")

    expl = str(expl_raw or "").strip()

    normalized = {
        "years_of_experience": years,
        "level_us": level_us,
        "level_cn": level_cn,
        "estimated_salary": est,
        "explanation": expl,
    }
    missing: list[str] = []
    if not str(level_us or "").strip():
        missing.append("level_us")
    if not str(level_cn or "").strip():
        missing.append("level_cn")
    if not str(est or "").strip():
        missing.append("estimated_salary")
    if not str(expl or "").strip():
        missing.append("explanation")
    if missing:
        normalized["_meta"] = {"fallback": True, "code": "unavailable", "preserve_empty": True, "missing": missing}
    return GateDecision(action="accept", normalized=normalized)


def _linkedin_colleagues_view(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)
    highlights = _as_list(payload.get("highlights"))
    areas = _as_list(payload.get("areas_for_improvement"))
    has_content = any(_is_nonempty_str(x) for x in highlights + areas)
    normalized = {"highlights": highlights, "areas_for_improvement": areas}
    if has_content:
        return GateDecision(action="accept", normalized=normalized)
    return GateDecision(
        action="retry",
        normalized=normalized,
        issue=GateIssue(code="empty_colleagues_view", message="Empty colleagues_view", retryable=True),
    )


def _linkedin_life_well_being(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)
    life = str(payload.get("life_suggestion") or "").strip()
    health = str(payload.get("health") or "").strip()
    normalized = {"life_suggestion": life, "health": health}
    if life or health:
        return GateDecision(action="accept", normalized=normalized)
    return GateDecision(
        action="retry",
        normalized=normalized,
        issue=GateIssue(code="empty_life_well_being", message="Empty life_well_being", retryable=True),
    )


def _linkedin_roast(data: Any, ctx: GateContext) -> GateDecision:
    if _is_nonempty_str(data):
        return GateDecision(action="accept", normalized=str(data).strip())

    payload = _as_dict(data)
    roast = payload.get("roast")
    if _is_nonempty_str(roast):
        return GateDecision(action="accept", normalized=str(roast).strip())

    return GateDecision(action="retry", normalized=str(roast or "").strip(), issue=GateIssue(code="empty_roast", message="Missing roast text", retryable=True))


def _linkedin_summary(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)
    about = payload.get("about")
    tags = payload.get("personal_tags")
    normalized = {"about": str(about or "").strip(), "personal_tags": _as_list(tags) if isinstance(tags, list) else tags}
    if _is_nonempty_str(about):
        return GateDecision(action="accept", normalized=normalized)
    return GateDecision(action="retry", normalized=normalized, issue=GateIssue(code="empty_about", message="Missing about section", retryable=True))


def _twitter_profile(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)
    if _is_nonempty_str(payload.get("username")):
        return GateDecision(action="accept", normalized=payload)
    return GateDecision(action="retry", normalized=payload, issue=GateIssue(code="missing_username", message="Missing twitter username", retryable=True))


def _twitter_stats(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)
    normalized = {
        "followers_count": payload.get("followers_count"),
        "followings_count": payload.get("followings_count"),
        "verified_followers_count": payload.get("verified_followers_count"),
    }
    if any(v is not None for v in normalized.values()):
        return GateDecision(action="accept", normalized=normalized)
    return GateDecision(action="retry", normalized=normalized, issue=GateIssue(code="missing_stats", message="Missing twitter stats", retryable=True))


def _twitter_network(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)
    normalized = {"top_followers": _as_list(payload.get("top_followers"))}
    return GateDecision(action="accept", normalized=normalized)


def _twitter_summary(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)
    summary = payload.get("summary")
    if _is_nonempty_str(summary):
        return GateDecision(action="accept", normalized={"summary": str(summary)})
    return GateDecision(action="retry", normalized={"summary": str(summary or "").strip()}, issue=GateIssue(code="empty_summary", message="Missing twitter summary", retryable=True))


def _openreview_profile(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)
    if _is_nonempty_str(payload.get("name")):
        return GateDecision(action="accept", normalized=payload)
    return GateDecision(action="retry", normalized=payload, issue=GateIssue(code="missing_name", message="Missing OpenReview name", retryable=True))


def _openreview_papers(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)
    normalized = {
        "total_papers": payload.get("total_papers"),
        "papers_last_year": payload.get("papers_last_year"),
        "representative_work": payload.get("representative_work"),
    }
    if any(v is not None for v in normalized.values()):
        return GateDecision(action="accept", normalized=normalized)
    return GateDecision(action="retry", normalized=normalized, issue=GateIssue(code="missing_papers", message="Missing OpenReview paper stats", retryable=True))


def _openreview_summary(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)
    summary = payload.get("summary")
    if _is_nonempty_str(summary):
        return GateDecision(action="accept", normalized={"summary": str(summary)})
    return GateDecision(action="retry", normalized={"summary": str(summary or "").strip()}, issue=GateIssue(code="empty_summary", message="Missing OpenReview summary", retryable=True))


def _youtube_profile(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)
    if _is_nonempty_str(payload.get("channel_id")) or _is_nonempty_str(payload.get("channel_name")):
        return GateDecision(action="accept", normalized=payload)
    return GateDecision(action="retry", normalized=payload, issue=GateIssue(code="missing_channel", message="Missing YouTube channel id/name", retryable=True))


def _youtube_summary(data: Any, ctx: GateContext) -> GateDecision:
    payload = _as_dict(data)
    summary = payload.get("content_summary")
    if _is_nonempty_str(summary):
        return GateDecision(action="accept", normalized=payload)
    return GateDecision(action="retry", normalized=payload, issue=GateIssue(code="empty_summary", message="Missing YouTube content summary", retryable=True))


def _register_defaults() -> None:
    # Scholar
    register_validator("scholar", "profile", _scholar_profile)
    register_validator("scholar", "metrics", _scholar_metrics)
    register_validator("scholar", "papers", _scholar_papers)
    register_validator("scholar", "citations", _scholar_citations)
    register_validator("scholar", "coauthors", _scholar_coauthors)
    register_validator("scholar", "role_model", _scholar_role_model)
    register_validator("scholar", "news", _scholar_news)
    register_validator("scholar", "level", _scholar_level)
    register_validator("scholar", "summary", _scholar_summary)
    register_validator("scholar", "researcherInfo", _scholar_researcher_info)
    register_validator("scholar", "publicationStats", _scholar_block)
    register_validator("scholar", "publicationInsight", _scholar_block)
    register_validator("scholar", "roleModel", _scholar_block)
    register_validator("scholar", "closestCollaborator", _scholar_block)
    register_validator("scholar", "estimatedSalary", _scholar_estimated_salary)
    register_validator("scholar", "researcherCharacter", _scholar_block)
    register_validator("scholar", "paperOfYear", _scholar_block)
    register_validator("scholar", "representativePaper", _scholar_block)
    register_validator("scholar", "criticalReview", _scholar_critical_review)

    # GitHub
    register_validator("github", "profile", _github_profile)
    register_validator("github", "activity", _github_activity)
    register_validator("github", "stats", _github_activity)
    register_validator("github", "repos", _github_repos)
    register_validator("github", "role_model", _github_role_model)
    register_validator("github", "roast", _github_roast)
    register_validator("github", "summary", _github_summary)

    # LinkedIn
    register_validator("linkedin", "profile", _linkedin_profile)
    register_validator("linkedin", "skills", _linkedin_skills)
    register_validator("linkedin", "career", _linkedin_career)
    register_validator("linkedin", "colleagues_view", _linkedin_colleagues_view)
    register_validator("linkedin", "life_well_being", _linkedin_life_well_being)
    register_validator("linkedin", "role_model", _linkedin_role_model)
    register_validator("linkedin", "money", _linkedin_money)
    register_validator("linkedin", "roast", _linkedin_roast)
    register_validator("linkedin", "summary", _linkedin_summary)

    # Twitter/OpenReview/YouTube
    register_validator("twitter", "profile", _twitter_profile)
    register_validator("twitter", "stats", _twitter_stats)
    register_validator("twitter", "network", _twitter_network)
    register_validator("twitter", "summary", _twitter_summary)
    register_validator("openreview", "profile", _openreview_profile)
    register_validator("openreview", "papers", _openreview_papers)
    register_validator("openreview", "summary", _openreview_summary)
    register_validator("youtube", "profile", _youtube_profile)
    register_validator("youtube", "summary", _youtube_summary)


_register_defaults()
