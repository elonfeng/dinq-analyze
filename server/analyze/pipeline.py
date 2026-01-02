"""Rule-driven analysis pipeline using existing analyzers."""
from __future__ import annotations

from collections import OrderedDict
from typing import Any, Dict, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
import re
import threading
import time
from urllib.parse import urlparse
import requests
from datetime import datetime

from server.llm.gateway import openrouter_chat
from server.config.llm_models import get_model
from server.analyze.subject import resolve_subject_key
from server.analyze import rules
from server.analyze.input_resolver import (
    resolve_github_username as resolve_github_input_username,
    resolve_huggingface_username,
    resolve_linkedin_content,
    resolve_openreview_identifier,
    resolve_scholar_identity,
    resolve_twitter_username,
    resolve_youtube_channel_input,
)
from server.tasks.job_store import JobStore
from server.tasks.artifact_store import ArtifactStore
from server.tasks.event_store import EventStore
from server.tasks.output_schema import extract_output_parts
from server.llm.context import llm_stream_context
from server.analyze.resources.github import (
    fetch_github_data,
    fetch_github_profile,
    fetch_github_preview,
    run_github_enrich_bundle,
)
from server.analyze.resources.linkedin import fetch_linkedin_raw_profile, fetch_linkedin_preview, run_linkedin_enrich_bundle
from server.analyze.resources.scholar import (
    estimate_scholar_level_fast,
    run_scholar_base,
    run_scholar_full,
    run_scholar_page0,
)
from server.analyze.card_specs import get_stream_spec
from server.utils.json_clean import prune_empty


_GITHUB_LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37})$")
_DAG_SOURCES = {"github", "linkedin", "scholar"}

_COMMENT_START = "<!--"
_COMMENT_END = "-->"


def _build_scholar_summary_input(report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a compact scholar context for LLM summarization.

    The raw report can be very large (papers list); keep only key signals.
    """

    researcher = report.get("researcher") if isinstance(report.get("researcher"), dict) else {}
    pub_stats = report.get("publication_stats") if isinstance(report.get("publication_stats"), dict) else {}
    rating = report.get("rating") if isinstance(report.get("rating"), dict) else {}
    coauthors = report.get("coauthor_stats") if isinstance(report.get("coauthor_stats"), dict) else {}

    def _pick_paper(p: Any) -> Dict[str, Any]:
        if not isinstance(p, dict):
            return {}
        out = {}
        for k in ("title", "year", "venue", "citations", "url"):
            if p.get(k) is not None:
                out[k] = p.get(k)
        return out

    most_cited = _pick_paper(pub_stats.get("most_cited_paper"))
    paper_of_year = _pick_paper(pub_stats.get("paper_of_year"))

    year_dist = pub_stats.get("year_distribution") if isinstance(pub_stats.get("year_distribution"), dict) else {}
    recent_years = sorted([str(y) for y in year_dist.keys()], reverse=True)[:6]
    recent_year_dist = {y: year_dist.get(y) for y in recent_years}

    top_fields = researcher.get("research_fields") or researcher.get("fields") or []
    if isinstance(top_fields, str):
        top_fields = [top_fields]
    if not isinstance(top_fields, list):
        top_fields = []

    return {
        "name": researcher.get("name"),
        "affiliation": researcher.get("affiliation"),
        "research_fields": [str(x) for x in top_fields[:8] if str(x).strip()],
        "metrics": {
            "total_citations": researcher.get("total_citations"),
            "citations_5y": researcher.get("citations_5y"),
            "h_index": researcher.get("h_index"),
            "h_index_5y": researcher.get("h_index_5y"),
            "total_papers": pub_stats.get("total_papers"),
            "top_tier_papers": pub_stats.get("top_tier_papers") or pub_stats.get("top_tier_publications"),
        },
        "highlights": {
            "most_cited_paper": most_cited,
            "paper_of_year": paper_of_year,
            "recent_year_distribution": recent_year_dist,
            "coauthors": {
                "total": coauthors.get("total_coauthors"),
                "top": (coauthors.get("top_coauthors") or [])[:5],
            },
            "rating": rating,
        },
    }


def _generate_scholar_sectioned_evaluation(report: Dict[str, Any]) -> str:
    """
    Generate a sectioned markdown evaluation for the Scholar 'summary' card.

    IMPORTANT: The output must contain section markers on their own line:
      <!--section:overview-->
      <!--section:strengths-->
      <!--section:risks-->
      <!--section:questions-->
    """

    payload = _build_scholar_summary_input(report or {})
    markers = [
        "<!--section:overview-->",
        "<!--section:strengths-->",
        "<!--section:risks-->",
        "<!--section:questions-->",
    ]

    system = (
        "You are a rigorous but fair talent evaluator.\n"
        "Write in Markdown. Keep it concise, specific, and actionable.\n\n"
        "Output format rules (STRICT):\n"
        "1) Use EXACTLY these section markers, each on its own line, in this order:\n"
        + "\n".join(markers)
        + "\n"
        "2) After each marker, write that section's content (Markdown paragraphs/bullets).\n"
        "3) Do NOT add any other headings or section titles outside the markers.\n"
        "4) Do NOT repeat the markers.\n"
    )
    user = f"Scholar profile signals (JSON):\n{payload}"

    text = openrouter_chat(
        task="scholar_summary",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        model="google/gemini-2.5-flash-lite",
        temperature=0.4,
        max_tokens=900,
    )
    return str(text or "").strip()


def _run_coro(coro) -> Any:  # type: ignore[no-untyped-def]
    """
    Run an async coroutine from sync code.

    Most of the pipeline is synchronous, but some analyzers expose async AI helpers.
    """

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    # Fallback: if we're already inside an event loop (rare in this codepath), run in a
    # dedicated thread so we can safely create a new loop.
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(coro)).result()


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _extract_github_username(value: str) -> str:
    if not value:
        return ""
    lowered = value.strip()
    if "github.com" in lowered:
        try:
            parsed = urlparse(lowered)
            parts = [p for p in parsed.path.split("/") if p]
            if parts:
                return parts[0]
        except Exception:
            return ""
    return lowered.strip()


def _github_repo_from_url(url: str) -> str:
    try:
        parsed = urlparse(str(url or ""))
        parts = [p for p in (parsed.path or "").split("/") if p]
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
    except Exception:
        return ""
    return ""


def _github_pr_candidates(pr_nodes: Any, *, max_candidates: int) -> list[Dict[str, Any]]:
    """
    Build a compact PR candidate list for LLM and heuristics.

    Notes:
    - GitHub PR nodes are already ordered by COMMENTS desc (see PullRequestsQuery); we preserve that as `comment_rank`.
    - We intentionally keep payload tiny to reduce LLM latency/cost.
    """

    if not isinstance(pr_nodes, list) or not pr_nodes:
        return []

    out: list[Dict[str, Any]] = []
    for idx, pr in enumerate(pr_nodes):
        if not isinstance(pr, dict):
            continue
        url = str(pr.get("url") or "").strip()
        title = str(pr.get("title") or "").strip()
        if not url or not title:
            continue
        try:
            additions = int(pr.get("additions") or 0)
        except Exception:
            additions = 0
        try:
            deletions = int(pr.get("deletions") or 0)
        except Exception:
            deletions = 0
        repo = _github_repo_from_url(url)

        out.append(
            {
                "repository": repo,
                "url": url,
                "title": title,
                "additions": additions,
                "deletions": deletions,
                # Smaller is "more commented" due to upstream ordering.
                "comment_rank": int(idx),
            }
        )

    if not out:
        return []

    def score(p: Dict[str, Any]) -> tuple[int, int]:
        impact = int(p.get("additions") or 0) + int(p.get("deletions") or 0)
        comment_rank = int(p.get("comment_rank") or 0)
        # Prefer higher impact; and for ties, prefer more-discussed (smaller rank).
        return (impact, -comment_rank)

    # Select top-N by heuristic score, then re-sort by original (comment) order for the model.
    k = max(1, min(int(max_candidates or 1), 50))
    selected = sorted(out, key=score, reverse=True)[:k]
    selected.sort(key=lambda p: int(p.get("comment_rank") or 0))
    return selected


def _github_best_pr_fallback(prs: list[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not prs:
        return None

    def score(p: Dict[str, Any]) -> tuple[int, int]:
        impact = int(p.get("additions") or 0) + int(p.get("deletions") or 0)
        comment_rank = int(p.get("comment_rank") or 0)
        return (impact, -comment_rank)

    best = max(prs, key=score)
    impact = int(best.get("additions") or 0) + int(best.get("deletions") or 0)
    return {
        "repository": best.get("repository") or "",
        "url": best.get("url") or "",
        "title": best.get("title") or "",
        "additions": int(best.get("additions") or 0),
        "deletions": int(best.get("deletions") or 0),
        "reason": "Selected by heuristic (high impact + most discussed among top candidates).",
        "impact": f"{impact} lines changed",
    }


def _github_best_pr_llm(
    prs: list[Dict[str, Any]],
    *,
    timeout_seconds: float,
) -> tuple[Optional[Dict[str, Any]], str]:
    if not prs:
        return None, "empty"

    system = (
        "You are an expert GitHub analyst.\n"
        "You are given a list of pull requests (PRs) for a developer.\n"
        "The PR list is ordered by comment count DESC (most discussed first).\n\n"
        "Return ONLY valid JSON. Do not wrap in markdown (no ``` fences).\n\n"
        "Pick the single most valuable PR.\n"
        "Return ONLY valid JSON with keys:\n"
        "repository, url, title, additions, deletions, reason, impact.\n"
        "- reason: 1-2 short sentences.\n"
        "- impact: <= 20 words.\n"
    )
    user = json.dumps(prs, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

    try:
        out = openrouter_chat(
            task="github_best_pr",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            model=get_model("fast", task="github_best_pr"),
            temperature=0.2,
            max_tokens=260,
            expect_json=True,
            stream=False,
            timeout_seconds=float(timeout_seconds or 0) or None,
        )
    except requests.exceptions.Timeout:
        return None, "timeout"
    except Exception:
        return None, "error"

    if not isinstance(out, dict):
        return None, "invalid"
    url = str(out.get("url") or "").strip()
    title = str(out.get("title") or "").strip()
    if not url or not title:
        return None, "invalid"
    repo = str(out.get("repository") or "").strip()
    if not repo:
        repo = _github_repo_from_url(url)

    try:
        additions = int(out.get("additions") or 0)
    except Exception:
        additions = 0
    try:
        deletions = int(out.get("deletions") or 0)
    except Exception:
        deletions = 0

    return (
        {
        "repository": repo,
        "url": url,
        "title": title,
        "additions": additions,
        "deletions": deletions,
        "reason": str(out.get("reason") or "").strip()[:400] or "Selected by model.",
        "impact": str(out.get("impact") or "").strip()[:200],
        },
        "ok",
    )


def _resolve_github_username(query: str) -> str:
    username = _extract_github_username(query)
    if not username:
        return ""

    if _GITHUB_LOGIN_RE.match(username):
        return username

    # Heuristic: name input (contains spaces or invalid characters); search GitHub users.
    try:
        headers = {"Accept": "application/vnd.github+json"}
        token = os.getenv("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        resp = requests.get(
            "https://api.github.com/search/users",
            params={"q": username, "per_page": 1},
            headers=headers,
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json() or {}
            items = data.get("items") or []
            if items:
                login = items[0].get("login") or ""
                if login:
                    return login
    except Exception:
        return ""

    return ""


class _CardDeltaEmitter:
    def __init__(
        self,
        event_store: EventStore,
        job_id: str,
        card_id: int,
        card_type: str,
        *,
        field: str,
        format: str,
        section: Optional[str] = None,
        sections: Optional[list[str]] = None,
        route: str = "fixed",
        flush_chars: int = 160,
    ) -> None:
        self._event_store = event_store
        self._job_id = job_id
        self._card_id = card_id
        self._card_type = card_type
        self._field = str(field or "content")
        self._format = str(format or "markdown")
        self._sections = [str(s) for s in (sections or []) if str(s).strip()]
        self._allowed_sections = {s.lower(): s for s in self._sections}
        self._section = str(section or (self._sections[0] if self._sections else "main"))
        self._route = str(route or "fixed").strip().lower()
        self._route_markers = bool(self._route == "marker" and len(self._sections) > 1)
        self._carry = ""
        self._buffer: list[str] = []
        self._size = 0
        self._flush_chars = max(40, int(flush_chars or 160))

    def on_delta(self, chunk: str) -> None:
        if not chunk:
            return
        if not self._route_markers:
            self._append(chunk)
            return

        pieces, final_section = self._split_by_markers(chunk)
        for section, text in pieces:
            if not text:
                continue
            if section != self._section:
                self.flush()
                self._section = section
            self._append(text)
        if final_section != self._section:
            # Section marker at chunk boundary (no content yet): flush current buffer to avoid mixing.
            self.flush()
            self._section = final_section

    def _append(self, text: str) -> None:
        if not text:
            return
        self._buffer.append(text)
        self._size += len(text)
        if "\n\n" in text or self._size >= self._flush_chars:
            self.flush()

    def _split_by_markers(self, chunk: str) -> tuple[list[tuple[str, str]], str]:
        buf = (self._carry or "") + chunk
        self._carry = ""

        cur = self._section
        pieces: list[tuple[str, str]] = []

        pos = 0
        while True:
            idx = buf.find(_COMMENT_START, pos)
            if idx == -1:
                break

            if idx > pos:
                pieces.append((cur, buf[pos:idx]))

            end = buf.find(_COMMENT_END, idx + len(_COMMENT_START))
            if end == -1:
                # Incomplete marker; keep for next chunk.
                self._carry = buf[idx:]
                return pieces, cur

            body = buf[idx + len(_COMMENT_START):end].strip()
            if body.lower().startswith("section:"):
                raw_name = body.split(":", 1)[1].strip()
                canonical = self._allowed_sections.get(raw_name.lower())
                if canonical:
                    cur = canonical
                else:
                    # Unknown section marker -> keep as literal text.
                    pieces.append((cur, buf[idx:end + len(_COMMENT_END)]))
            else:
                # Not a section marker -> keep as literal text.
                pieces.append((cur, buf[idx:end + len(_COMMENT_END)]))

            pos = end + len(_COMMENT_END)

        tail = buf[pos:]
        # Handle partial marker prefix split across chunks.
        carry = ""
        max_check = min(len(_COMMENT_START) - 1, len(tail))
        for i in range(max_check, 0, -1):
            suffix = tail[-i:]
            if _COMMENT_START.startswith(suffix):
                carry = suffix
                tail = tail[:-i]
                break
        if carry:
            self._carry = carry
        if tail:
            pieces.append((cur, tail))
        return pieces, cur

    def flush(self) -> None:
        if not self._buffer:
            return
        payload = {
            "card": self._card_type,
            "field": self._field,
            "section": self._section,
            "format": self._format,
            "delta": "".join(self._buffer),
        }
        self._buffer = []
        self._size = 0
        self._event_store.append_event(
            job_id=self._job_id,
            card_id=self._card_id,
            event_type="card.delta",
            payload=payload,
        )


def create_job_cards(source: str, requested_cards=None) -> list[dict]:
    return rules.build_plan(source, requested_cards)


def run_full_analysis(source: str, input_payload: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
    if source == "scholar":
        from server.services.scholar.scholar_service import run_scholar_analysis

        scholar_id, query = resolve_scholar_identity(input_payload)

        # Crawlbase + cache strategy are server-side concerns; do not take tokens/tuning from client input.
        api_token = os.getenv("CRAWLBASE_API_TOKEN") or os.getenv("CRAWLBASE_TOKEN") or ""
        use_crawlbase = _bool_env("DINQ_SCHOLAR_USE_CRAWLBASE", default=bool(api_token))

        try:
            cache_max_age_days = int(os.getenv("DINQ_SCHOLAR_CACHE_MAX_AGE_DAYS", "3") or "3")
        except ValueError:
            cache_max_age_days = 3
        cache_max_age_days = max(0, min(cache_max_age_days, 30))

        return run_scholar_analysis(
            researcher_name=query if not scholar_id else None,
            scholar_id=scholar_id,
            use_crawlbase=use_crawlbase,
            api_token=api_token or None,
            callback=None,
            use_cache=True,
            cache_max_age_days=cache_max_age_days,
            cancel_event=None,
            user_id=user_id,
        ) or {}

    if source == "github":
        from server.api.github_analyzer_api import get_analyzer
        analyzer = get_analyzer()
        username = resolve_github_input_username(input_payload)
        username = _resolve_github_username(username)
        if not username:
            raise ValueError("unable to resolve GitHub username; please provide a valid login")
        result = analyzer.get_result_with_progress(username, progress_callback=None, cancel_event=None)
        if not result:
            raise ValueError(f'GitHub user "{username}" not found or inaccessible')
        if isinstance(result, dict) and not result.get("description"):
            tags = result.get("user", {}).get("tags") or []
            tag_line = f" Focus: {', '.join(tags[:3])}." if tags else ""
            result["description"] = f"GitHub profile summary for {username}.{tag_line}"
        return result

    if source == "linkedin":
        from server.api.linkedin_analyzer_api import get_linkedin_analyzer
        analyzer = get_linkedin_analyzer()
        content = resolve_linkedin_content(input_payload)
        if not content:
            raise ValueError("missing linkedin name or url")
        linkedin_url = content if "linkedin.com" in content else None
        person_name = input_payload.get("name") or input_payload.get("person_name") or content
        result = analyzer.get_result_with_progress(person_name, progress_callback=None, linkedin_url=linkedin_url, cancel_event=None)
        if not result:
            raise ValueError(f'LinkedIn profile "{person_name}" not found or inaccessible')
        return result

    if source == "huggingface":
        from server.huggingface_analyzer.analyzer import HuggingFaceAnalyzer
        username = resolve_huggingface_username(input_payload)
        return HuggingFaceAnalyzer().analyze_profile(username) or {}

    if source == "twitter":
        from server.twitter_analyzer.analyzer import TwitterAnalyzer
        username = resolve_twitter_username(input_payload)
        return TwitterAnalyzer().analyze_profile(username) or {}

    if source == "openreview":
        from server.openreview_analyzer.analyzer import analyze_openreview_profile
        _, value = resolve_openreview_identifier(input_payload)
        return analyze_openreview_profile(value) or {}

    if source == "youtube":
        from server.youtube_analyzer.analyzer import YouTubeAnalyzer
        channel = resolve_youtube_channel_input(input_payload)
        return YouTubeAnalyzer({"youtube": {}}).get_result(channel) or {}

    return {}


def extract_card_payload(source: str, full_report: Dict[str, Any], card_type: str) -> Any:
    if source == "scholar":
        if isinstance(full_report, dict) and isinstance(full_report.get("researcherProfile"), dict):
            profile = full_report.get("researcherProfile") if isinstance(full_report.get("researcherProfile"), dict) else {}
            researcher_info = profile.get("researcherInfo") if isinstance(profile.get("researcherInfo"), dict) else {}
            blocks = profile.get("dataBlocks") if isinstance(profile.get("dataBlocks"), dict) else {}

            if card_type == "researcherInfo":
                return researcher_info

            if card_type in (
                "publicationStats",
                "publicationInsight",
                "roleModel",
                "closestCollaborator",
                "estimatedSalary",
                "researcherCharacter",
                "paperOfYear",
                "representativePaper",
                "criticalReview",
            ):
                payload = blocks.get(card_type)
                return payload if isinstance(payload, dict) else {}

            return full_report

        # Legacy (pre-refactor) scholar shapes (best-effort).
        researcher = full_report.get("researcher", {}) if isinstance(full_report, dict) else {}
        pub_stats = full_report.get("publication_stats", {}) if isinstance(full_report, dict) else {}
        if card_type == "profile":
            return researcher
        if card_type == "metrics":
            return pub_stats
        if card_type == "citations":
            return {
                "total_citations": researcher.get("total_citations"),
                "citations_5y": researcher.get("citations_5y"),
                "h_index": researcher.get("h_index"),
                "h_index_5y": researcher.get("h_index_5y"),
                "yearly_citations": researcher.get("yearly_citations"),
            }
        return full_report

    if source == "github":
        if card_type == "profile":
            return full_report.get("user", {})
        if card_type in ("stats", "activity"):
            return {
                "overview": full_report.get("overview"),
                "activity": full_report.get("activity"),
                "code_contribution": full_report.get("code_contribution"),
            }
        if card_type == "repos":
            return {
                "feature_project": full_report.get("feature_project"),
                "top_projects": full_report.get("top_projects"),
                "most_valuable_pull_request": full_report.get("most_valuable_pull_request"),
            }
        if card_type == "role_model":
            return full_report.get("role_model", {})
        if card_type == "roast":
            return full_report.get("roast")
        if card_type == "summary":
            return full_report.get("valuation_and_level") or {}
        return full_report

    if source == "linkedin":
        profile = full_report.get("profile_data", {}) if isinstance(full_report, dict) else {}
        if card_type == "profile":
            if not isinstance(profile, dict) or not profile:
                return {}
            # Keep the business card payload small/stable for DB persistence & caching.
            # raw_profile is a large scrape blob and is not required by the frontend contract.
            out = dict(profile)
            out.pop("raw_profile", None)
            return out
        if card_type == "skills":
            return profile.get("skills", {})
        if card_type == "career":
            return {
                "career": profile.get("career"),
                "work_experience": profile.get("work_experience"),
                "education": profile.get("education"),
                "work_experience_summary": profile.get("work_experience_summary"),
                "education_summary": profile.get("education_summary"),
            }
        if card_type == "role_model":
            return profile.get("role_model", {})
        if card_type == "money":
            return profile.get("money_analysis", {})
        if card_type == "roast":
            return profile.get("roast")
        if card_type == "summary":
            return {
                "about": profile.get("about"),
                "personal_tags": profile.get("personal_tags"),
            }
        return full_report

    if source == "twitter":
        if card_type == "profile":
            return {
                "username": full_report.get("username"),
                "followers_count": full_report.get("followers_count"),
                "followings_count": full_report.get("followings_count"),
            }
        if card_type == "stats":
            return {
                "followers_count": full_report.get("followers_count"),
                "followings_count": full_report.get("followings_count"),
                "verified_followers_count": full_report.get("verified_followers_count"),
            }
        if card_type == "network":
            return {"top_followers": full_report.get("top_followers")}
        if card_type == "summary":
            return {"summary": full_report.get("summary")}
        return full_report

    if source == "openreview":
        if card_type == "profile":
            return {
                "name": full_report.get("name"),
                "expertise_areas": full_report.get("expertise_areas") or [],
            }
        if card_type == "papers":
            return {
                "total_papers": full_report.get("total_papers"),
                "papers_last_year": full_report.get("papers_last_year"),
                "representative_work": full_report.get("representative_work"),
            }
        if card_type == "summary":
            name = full_report.get("name") or ""
            total = int(full_report.get("total_papers") or 0)
            last_year = int(full_report.get("papers_last_year") or 0)
            areas = full_report.get("expertise_areas") or []
            area_text = ", ".join([str(a) for a in areas[:3] if a]) if isinstance(areas, list) else ""
            summary = f"{name} has {total} accepted papers on OpenReview; {last_year} in the last year."
            if area_text:
                summary = f"{summary} Expertise: {area_text}."
            return {"summary": summary}
        return full_report

    if source == "huggingface":
        if card_type == "profile":
            return full_report
        if card_type == "summary":
            return {
                "fullname": full_report.get("fullname"),
                "numFollowers": full_report.get("numFollowers"),
                "representative_work": full_report.get("representative_work"),
            }
        return full_report

    if source == "youtube":
        if card_type == "profile":
            return {
                "channel_id": full_report.get("channel_id"),
                "channel_name": full_report.get("channel_name"),
                "channel_url": full_report.get("channel_url"),
                "subscriber_count": full_report.get("subscriber_count"),
                "total_view_count": full_report.get("total_view_count"),
                "video_count": full_report.get("video_count"),
            }
        if card_type == "summary":
            return {
                "content_summary": full_report.get("content_summary"),
                "representative_video": full_report.get("representative_video"),
                "analysis_date": full_report.get("analysis_date"),
            }
        return full_report

    return full_report


class PipelineExecutor:
    def __init__(self, job_store: JobStore, artifact_store: ArtifactStore, event_store: Optional[EventStore] = None):
        self._job_store = job_store
        self._artifact_store = artifact_store
        self._event_store = event_store
        self._job_cache_max = max(0, self._read_int_env("DINQ_JOB_CACHE_MAX", 256))
        self._job_cache: "OrderedDict[str, object]" = OrderedDict()
        self._job_cache_lock = threading.Lock()

    def _read_int_env(self, name: str, default: int) -> int:
        raw = os.getenv(name)
        if raw is None:
            return int(default)
        try:
            return int(raw)
        except Exception:
            return int(default)

    def _get_job_cached(self, job_id: str):  # type: ignore[no-untyped-def]
        if not job_id or self._job_cache_max <= 0:
            return self._job_store.get_job(job_id)

        try:
            with self._job_cache_lock:
                cached = self._job_cache.get(str(job_id))
                if cached is not None:
                    self._job_cache.move_to_end(str(job_id))
                    return cached
        except Exception:
            cached = None

        job = self._job_store.get_job(job_id)
        if job is None:
            return None

        try:
            with self._job_cache_lock:
                self._job_cache[str(job_id)] = job
                self._job_cache.move_to_end(str(job_id))
                while len(self._job_cache) > int(self._job_cache_max):
                    try:
                        self._job_cache.popitem(last=False)
                    except Exception:
                        break
        except Exception:
            pass
        return job

    def execute_card(self, card, emit_deltas: bool = True) -> Dict[str, Any]:  # type: ignore[no-untyped-def]
        job = self._get_job_cached(card.job_id)
        if job is None:
            raise ValueError("job not found")

        source = job.source
        delta_emitter = None
        stream_spec = get_stream_spec(str(source or ""), str(card.card_type))
        if emit_deltas and self._event_store and card.id is not None and stream_spec:
            delta_emitter = _CardDeltaEmitter(
                self._event_store,
                job.id,
                card.id,
                str(card.card_type),
                field=str(stream_spec.get("field") or "content"),
                format=str(stream_spec.get("format") or "markdown"),
                section=str((stream_spec.get("sections") or ["main"])[0] or "main"),
                sections=list(stream_spec.get("sections") or ["main"]),
                route=str(stream_spec.get("route") or "fixed"),
            )

        card_ids_by_type: Optional[Dict[str, int]] = None

        def _lookup_card_id(card_type: str) -> Optional[int]:
            nonlocal card_ids_by_type
            ct = str(card_type or "").strip()
            if not ct:
                return None
            if card_ids_by_type is None:
                try:
                    cards = self._job_store.list_cards_for_job(job.id)
                    card_ids_by_type = {
                        str(getattr(c, "card_type", "") or ""): int(getattr(c, "id"))
                        for c in cards
                        if getattr(c, "id", None) is not None
                    }
                except Exception:
                    card_ids_by_type = {}
            return card_ids_by_type.get(ct)

        def _emit_card_append(append: Dict[str, Any]) -> None:
            if not self._event_store:
                return
            to_card = str(append.get("card") or append.get("to_card") or append.get("card_type") or "").strip()
            if not to_card:
                return
            items = append.get("items")
            if not isinstance(items, list) or not items:
                return
            target_id = append.get("card_id")
            if target_id is not None:
                try:
                    card_id_int = int(target_id)
                except Exception:
                    card_id_int = None
            else:
                card_id_int = _lookup_card_id(to_card)
            if not card_id_int:
                return
            payload: Dict[str, Any] = {
                "card": to_card,
                "path": append.get("path") or "items",
                "items": items,
                "dedup_key": append.get("dedup_key") or "id",
            }
            if "cursor" in append:
                payload["cursor"] = append.get("cursor")
            if "partial" in append:
                payload["partial"] = append.get("partial")
            try:
                self._event_store.append_event(
                    job_id=job.id,
                    card_id=card_id_int,
                    event_type="card.append",
                    payload=payload,
                )
            except Exception:
                return

        def _emit_prefill_cards(prefills: Any) -> None:
            """
            Prefill/complete other cards during execution of a dependency card (e.g. Scholar page0 early profile/metrics).

            Input schema (best-effort):
              [{"card": "<card_type>", "data": {...}, "meta": {...}}]
            """

            if not self._event_store or not isinstance(prefills, list) or not prefills:
                return

            for item in prefills:
                if not isinstance(item, dict):
                    continue
                to_card = str(item.get("card") or item.get("to_card") or item.get("card_type") or "").strip()
                if not to_card:
                    continue
                data = item.get("data")
                if not isinstance(data, dict) or not data:
                    continue

                meta = item.get("meta")
                if isinstance(meta, dict) and meta:
                    merged = dict(data)
                    existing_meta = merged.get("_meta")
                    if isinstance(existing_meta, dict):
                        out_meta = dict(existing_meta)
                        out_meta.update(meta)
                        merged["_meta"] = out_meta
                    else:
                        merged["_meta"] = dict(meta)
                    data = merged

                try:
                    cleaned = prune_empty(data)
                    if cleaned is not None:
                        data = cleaned
                except Exception:
                    pass

                target_id = item.get("card_id")
                if target_id is not None:
                    try:
                        card_id_int = int(target_id)
                    except Exception:
                        card_id_int = None
                else:
                    card_id_int = _lookup_card_id(to_card)
                if not card_id_int:
                    continue

                # Emit event first to preserve lock ordering (job row lock happens inside EventStore.append_event).
                try:
                    self._event_store.append_event(
                        job_id=job.id,
                        card_id=card_id_int,
                        event_type="card.prefill",
                        payload={
                            "card": to_card,
                            "payload": {"data": data, "stream": {}},
                            "internal": False,
                            "timing": {"duration_ms": 0},
                        },
                    )
                except Exception:
                    pass

        def progress(step: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
            if not self._event_store or card.id is None:
                return
            safe_data = data
            if isinstance(data, dict):
                append = data.get("append")
                if isinstance(append, dict):
                    _emit_card_append(append)
                    # Avoid duplicating potentially-large items in card.progress; keep only a compact summary.
                    compact = dict(append)
                    try:
                        count = len(append.get("items") or [])
                    except Exception:
                        count = 0
                    compact.pop("items", None)
                    compact["count"] = int(count)
                    safe_data = dict(data)
                    safe_data["append"] = compact

                prefills = data.get("prefill_cards")
                if isinstance(prefills, list) and prefills:
                    _emit_prefill_cards(prefills)
                    compact_prefills = []
                    for item in prefills:
                        if not isinstance(item, dict):
                            continue
                        card_name = str(item.get("card") or item.get("to_card") or item.get("card_type") or "").strip()
                        keys = []
                        payload = item.get("data")
                        if isinstance(payload, dict):
                            keys = sorted([str(k) for k in payload.keys()])[:20]
                        compact_prefills.append({"card": card_name, "keys": keys})
                    safe_data = dict(safe_data or {})
                    safe_data["prefill_cards"] = {"count": len(prefills), "cards": compact_prefills}

            payload: Dict[str, Any] = {
                "card": str(card.card_type),
                "step": str(step),
                "message": str(message),
            }
            if isinstance(safe_data, dict) and safe_data:
                payload["data"] = safe_data
            try:
                self._event_store.append_event(job_id=job.id, card_id=card.id, event_type="card.progress", payload=payload)
            except Exception:
                pass

        def run() -> Dict[str, Any]:
            input_payload = job.input or {}
            options = job.options or {}
            subject_key = getattr(job, "subject_key", None) or resolve_subject_key(source, input_payload)

            # Resource DAG cards (GitHub/Scholar/LinkedIn).
            if str(card.card_type).startswith("resource."):
                card_type = str(card.card_type)
                if source == "github" and card_type == "resource.github.profile":
                    username = _resolve_github_username(resolve_github_input_username(input_payload))
                    if not username:
                        raise ValueError("unable to resolve GitHub username; please provide a valid login")
                    payload = fetch_github_profile(login=username, progress=progress)
                    self._artifact_store.save_artifact(job_id=job.id, card_id=card.id, type=card_type, payload=payload)
                    return payload
                if source == "github" and card_type == "resource.github.preview":
                    username = _resolve_github_username(resolve_github_input_username(input_payload))
                    if not username:
                        raise ValueError("unable to resolve GitHub username; please provide a valid login")
                    profile_art = self._artifact_store.get_artifact(job.id, "resource.github.profile")
                    user = None
                    if profile_art is not None and isinstance(profile_art.payload, dict):
                        user = (profile_art.payload or {}).get("user") if isinstance((profile_art.payload or {}).get("user"), dict) else None
                    payload = fetch_github_preview(login=username, progress=progress, user=user)
                    self._artifact_store.save_artifact(job_id=job.id, card_id=card.id, type=card_type, payload=payload)
                    return payload
                if source == "github" and card_type == "resource.github.data":
                    username = _resolve_github_username(resolve_github_input_username(input_payload))
                    if not username:
                        raise ValueError("unable to resolve GitHub username; please provide a valid login")
                    profile_art = self._artifact_store.get_artifact(job.id, "resource.github.profile")
                    user = None
                    if profile_art is not None and isinstance(profile_art.payload, dict):
                        user = (profile_art.payload or {}).get("user") if isinstance((profile_art.payload or {}).get("user"), dict) else None
                    payload = fetch_github_data(login=username, progress=progress, user=user)
                    self._artifact_store.save_artifact(job_id=job.id, card_id=card.id, type=card_type, payload=payload)
                    return payload

                if source == "github" and card_type == "resource.github.enrich":
                    username = _resolve_github_username(resolve_github_input_username(input_payload))
                    if not username:
                        raise ValueError("unable to resolve GitHub username; please provide a valid login")
                    data_art = self._artifact_store.get_artifact(job.id, "resource.github.data")
                    if data_art is None or not isinstance(data_art.payload, dict):
                        raise ValueError("missing resource.github.data")
                    base_payload = dict(data_art.payload or {})

                    payload = run_github_enrich_bundle(login=username, base=base_payload, progress=progress, mode="fast")
                    self._artifact_store.save_artifact(job_id=job.id, card_id=card.id, type=card_type, payload=payload)
                    return payload

                if source == "github" and card_type == "resource.github.best_pr":
                    # Background refine for repos.most_valuable_pull_request (queued on timeout).
                    data_art = self._artifact_store.get_artifact(job.id, "resource.github.data")
                    if data_art is None or not isinstance(data_art.payload, dict):
                        raise ValueError("missing resource.github.data")

                    pr_nodes = ((data_art.payload or {}).get("_pull_requests") or {}).get("nodes") or []
                    if not isinstance(pr_nodes, list) or not pr_nodes:
                        return {"skipped": True, "reason": "no_prs"}

                    # Candidate size can be larger for background refine, but still cap for cost.
                    max_candidates = None
                    try:
                        if isinstance(card.input, dict) and card.input.get("max_candidates") is not None:
                            max_candidates = int(card.input.get("max_candidates") or 0)
                    except Exception:
                        max_candidates = None
                    if not max_candidates:
                        try:
                            max_candidates = int(os.getenv("DINQ_GITHUB_BEST_PR_BG_MAX_CANDIDATES", "50") or "50")
                        except Exception:
                            max_candidates = 50

                    candidates = _github_pr_candidates(pr_nodes, max_candidates=int(max_candidates))
                    if not candidates:
                        return {"skipped": True, "reason": "no_candidates"}

                    try:
                        bg_timeout = float(os.getenv("DINQ_GITHUB_BEST_PR_BACKGROUND_TIMEOUT_SECONDS", "60") or "60")
                    except Exception:
                        bg_timeout = 60.0

                    progress("ai_best_pr_refine", "Refining best PR in background...", {"candidates": len(candidates), "timeout_seconds": bg_timeout})
                    best_pr, status = _github_best_pr_llm(candidates, timeout_seconds=bg_timeout)
                    if best_pr is None:
                        best_pr = _github_best_pr_fallback(candidates)
                        status = "fallback"

                    if not isinstance(best_pr, dict) or not best_pr.get("url"):
                        return {"skipped": True, "reason": "no_best_pr"}

                    # Update the user-facing repos card snapshot + emit an update event.
                    repos_id = None
                    try:
                        cards = self._job_store.list_cards_for_job(job.id)
                        for c in cards:
                            if str(getattr(c, "card_type", "") or "") == "repos" and getattr(c, "id", None) is not None:
                                repos_id = int(getattr(c, "id"))
                                break
                    except Exception:
                        repos_id = None

                    if repos_id is not None and self._event_store is not None:
                        try:
                            merged = self._job_store.update_card_status(
                                card_id=repos_id,
                                status="completed",
                                output={"most_valuable_pull_request": best_pr},
                            )
                            payload_env = merged or {"data": {"most_valuable_pull_request": best_pr}, "stream": {}}
                            self._event_store.append_event(
                                job_id=job.id,
                                card_id=repos_id,
                                event_type="card.completed",
                                payload={
                                    "card": "repos",
                                    "payload": payload_env,
                                    "internal": False,
                                    "timing": {"duration_ms": 0},
                                    "meta": {"source": status},
                                },
                            )
                        except Exception:
                            pass

                    return {"best_pr": best_pr, "status": status}

                if source == "scholar" and card_type == "resource.scholar.base":
                    scholar_id, query = resolve_scholar_identity(input_payload)
                    payload = run_scholar_base(scholar_id=scholar_id, researcher_name=query, user_id=job.user_id, progress=progress)
                    self._artifact_store.save_artifact(job_id=job.id, card_id=card.id, type=card_type, payload=payload)
                    return payload

                if source == "scholar" and card_type == "resource.scholar.page0":
                    scholar_id, query = resolve_scholar_identity(input_payload)
                    payload = run_scholar_page0(scholar_id=scholar_id, researcher_name=query, user_id=job.user_id, progress=progress)
                    self._artifact_store.save_artifact(job_id=job.id, card_id=card.id, type=card_type, payload=payload)
                    return payload

                if source == "scholar" and card_type == "resource.scholar.full":
                    # Background full fetch (more pages) for incremental paper append + cache warm-up.
                    scholar_id, query = resolve_scholar_identity(input_payload)
                    payload = run_scholar_full(scholar_id=scholar_id, researcher_name=query, user_id=job.user_id, progress=progress)
                    self._artifact_store.save_artifact(job_id=job.id, card_id=card.id, type=card_type, payload=payload)
                    return payload

                if source == "scholar" and card_type == "resource.scholar.level":
                    base_art = self._artifact_store.get_artifact(job.id, "resource.scholar.full")
                    if base_art is None or not isinstance(base_art.payload, dict):
                        base_art = self._artifact_store.get_artifact(job.id, "resource.scholar.page0")
                    if base_art is None or not isinstance(base_art.payload, dict):
                        base_art = self._artifact_store.get_artifact(job.id, "resource.scholar.base")
                    if base_art is None or not isinstance(base_art.payload, dict):
                        raise ValueError("missing resource.scholar.page0")
                    report = dict(base_art.payload or {})

                    progress("ai_level", "Generating career level (fast)...", None)
                    level_fast = estimate_scholar_level_fast(report=report) or {}
                    if not isinstance(level_fast, dict):
                        level_fast = {}
                    self._artifact_store.save_artifact(job_id=job.id, card_id=card.id, type=card_type, payload=level_fast)
                    return level_fast

                if source == "linkedin" and card_type == "resource.linkedin.raw_profile":
                    content = resolve_linkedin_content(input_payload)
                    preview_art = self._artifact_store.get_artifact(job.id, "resource.linkedin.preview")
                    linkedin_url = None
                    person_name = None
                    apify_full_run_id = None
                    apify_full_dataset_id = None
                    apify_lite_run_id = None
                    apify_lite_dataset_id = None
                    if preview_art is not None and isinstance(preview_art.payload, dict):
                        linkedin_url = preview_art.payload.get("_linkedin_url")
                        profile_data = preview_art.payload.get("profile_data")
                        if isinstance(profile_data, dict):
                            person_name = profile_data.get("name")
                        apify = preview_art.payload.get("_apify")
                        if isinstance(apify, dict):
                            lite = apify.get("lite")
                            full = apify.get("full")
                            if isinstance(lite, dict):
                                apify_lite_run_id = lite.get("run_id")
                                apify_lite_dataset_id = lite.get("dataset_id")
                            if isinstance(full, dict):
                                apify_full_run_id = full.get("run_id")
                                apify_full_dataset_id = full.get("dataset_id")
                    payload = fetch_linkedin_raw_profile(
                        content=content,
                        progress=progress,
                        linkedin_url=linkedin_url,
                        person_name=person_name,
                        apify_full_run_id=apify_full_run_id,
                        apify_full_dataset_id=apify_full_dataset_id,
                        apify_lite_run_id=apify_lite_run_id,
                        apify_lite_dataset_id=apify_lite_dataset_id,
                    )
                    self._artifact_store.save_artifact(job_id=job.id, card_id=card.id, type=card_type, payload=payload)
                    return payload

                if source == "linkedin" and card_type == "resource.linkedin.enrich":
                    raw_art = self._artifact_store.get_artifact(job.id, "resource.linkedin.raw_profile")
                    if raw_art is None or not isinstance(raw_art.payload, dict):
                        raise ValueError("missing resource.linkedin.raw_profile")
                    payload = run_linkedin_enrich_bundle(raw_report=raw_art.payload, progress=progress)
                    self._artifact_store.save_artifact(job_id=job.id, card_id=card.id, type=card_type, payload=payload)
                    return payload

                if source == "linkedin" and card_type == "resource.linkedin.preview":
                    content = resolve_linkedin_content(input_payload)
                    payload = fetch_linkedin_preview(content=content, progress=progress)
                    self._artifact_store.save_artifact(job_id=job.id, card_id=card.id, type=card_type, payload=payload)
                    return payload

                raise ValueError(f"unknown resource card: {card_type}")

            if card.card_type == "full_report":
                full_report: Dict[str, Any] = {}

                # DAG sources: assemble from resources (and persist cross-job cache).
                if source in _DAG_SOURCES:
                    cards = self._job_store.list_cards_for_job(job.id)
                    outputs_by_type: Dict[str, Any] = {}
                    for c in cards:
                        data, _ = extract_output_parts(getattr(c, "output", None))
                        if data is None:
                            continue
                        outputs_by_type[str(c.card_type)] = data

                    if source == "github":
                        data_art = self._artifact_store.get_artifact(job.id, "resource.github.data")
                        if data_art is None or not isinstance(data_art.payload, dict):
                            raise ValueError("missing resource.github.data")
                        full_report = dict(data_art.payload or {})
                        full_report.pop("_pull_requests", None)

                        if isinstance(outputs_by_type.get("profile"), dict):
                            full_report["user"] = outputs_by_type["profile"]

                        activity_payload = outputs_by_type.get("activity") or outputs_by_type.get("stats")
                        if isinstance(activity_payload, dict):
                            if "overview" in activity_payload:
                                full_report["overview"] = activity_payload.get("overview")
                            if "activity" in activity_payload:
                                full_report["activity"] = activity_payload.get("activity")
                            if "code_contribution" in activity_payload:
                                full_report["code_contribution"] = activity_payload.get("code_contribution")

                        repos_payload = outputs_by_type.get("repos")
                        if isinstance(repos_payload, dict):
                            if repos_payload.get("feature_project") is not None:
                                full_report["feature_project"] = repos_payload.get("feature_project")
                            if repos_payload.get("top_projects") is not None:
                                full_report["top_projects"] = repos_payload.get("top_projects")
                            if repos_payload.get("most_valuable_pull_request") is not None:
                                full_report["most_valuable_pull_request"] = repos_payload.get("most_valuable_pull_request")

                        if isinstance(outputs_by_type.get("role_model"), dict):
                            full_report["role_model"] = outputs_by_type["role_model"]

                        roast_payload = outputs_by_type.get("roast")
                        if roast_payload is not None:
                            full_report["roast"] = roast_payload

                        summary_payload = outputs_by_type.get("summary")
                        if isinstance(summary_payload, dict) and summary_payload:
                            full_report["valuation_and_level"] = summary_payload

                    elif source == "scholar":
                        researcher_info = outputs_by_type.get("researcherInfo")
                        if not isinstance(researcher_info, dict):
                            researcher_info = {}

                        blocks: Dict[str, Any] = {}
                        for k in (
                            "publicationStats",
                            "publicationInsight",
                            "roleModel",
                            "closestCollaborator",
                            "estimatedSalary",
                            "researcherCharacter",
                            "paperOfYear",
                            "representativePaper",
                            "criticalReview",
                        ):
                            v = outputs_by_type.get(k)
                            blocks[k] = v if isinstance(v, dict) else {}

                        full_report = {
                            "researcherProfile": {
                                "researcherInfo": researcher_info,
                                "dataBlocks": blocks,
                                "configInfo": {"comment": "Generated by unified analysis pipeline"},
                            }
                        }

                    elif source == "linkedin":
                        raw_art = self._artifact_store.get_artifact(job.id, "resource.linkedin.raw_profile")
                        if raw_art is None or not isinstance(raw_art.payload, dict):
                            raise ValueError("missing resource.linkedin.raw_profile")
                        full_report = dict(raw_art.payload or {})

                        base_profile = full_report.get("profile_data", {})
                        if not isinstance(base_profile, dict):
                            base_profile = {}
                        merged_profile: Dict[str, Any] = dict(base_profile)

                        if isinstance(outputs_by_type.get("skills"), dict):
                            merged_profile["skills"] = outputs_by_type["skills"]

                        career_payload = outputs_by_type.get("career")
                        if isinstance(career_payload, dict):
                            for key in ("career", "work_experience", "education", "work_experience_summary", "education_summary"):
                                if career_payload.get(key) is not None:
                                    merged_profile[key] = career_payload.get(key)

                        if isinstance(outputs_by_type.get("role_model"), dict):
                            merged_profile["role_model"] = outputs_by_type["role_model"]

                        if isinstance(outputs_by_type.get("money"), dict):
                            merged_profile["money_analysis"] = outputs_by_type["money"]

                        roast_payload = outputs_by_type.get("roast")
                        if roast_payload is not None:
                            merged_profile["roast"] = roast_payload

                        summary_payload = outputs_by_type.get("summary")
                        if isinstance(summary_payload, dict):
                            if summary_payload.get("about") is not None:
                                merged_profile["about"] = summary_payload.get("about")
                            if summary_payload.get("personal_tags") is not None:
                                merged_profile["personal_tags"] = summary_payload.get("personal_tags")

                        full_report["profile_data"] = merged_profile

                    self._artifact_store.save_artifact(job_id=job.id, card_id=card.id, type="full_report", payload=full_report)
                    return full_report if isinstance(full_report, dict) else {"report": full_report}

                full_report = run_full_analysis(source, input_payload, user_id=job.user_id) or {}
                self._artifact_store.save_artifact(
                    job_id=job.id,
                    card_id=card.id,
                    type="full_report",
                    payload=full_report,
                )

                if isinstance(full_report, dict):
                    return full_report
                return {"generated_at": datetime.utcnow().isoformat(), "report": full_report}

            # Non-full cards
            if source in _DAG_SOURCES:
                ct = str(card.card_type)
                if source == "github":
                    if ct == "profile":
                        profile_art = self._artifact_store.get_artifact(job.id, "resource.github.profile")
                        if profile_art is not None and isinstance(profile_art.payload, dict):
                            payload = dict(profile_art.payload or {})
                            # If available, merge GraphQL counts from the bundle into the profile payload.
                            # This keeps `issues/pullRequests/repositories.totalCount` non-empty even when the
                            # profile fetch used REST for fast-first UX.
                            data_art = self._artifact_store.get_artifact(job.id, "resource.github.data")
                            if data_art is not None and isinstance(data_art.payload, dict):
                                p_user = payload.get("user") if isinstance(payload.get("user"), dict) else {}
                                d_user = data_art.payload.get("user") if isinstance(data_art.payload.get("user"), dict) else {}
                                for k in ("issues", "pullRequests", "repositories"):
                                    pv = p_user.get(k) if isinstance(p_user.get(k), dict) else {}
                                    dv = d_user.get(k) if isinstance(d_user.get(k), dict) else {}
                                    if pv.get("totalCount") is None and dv.get("totalCount") is not None:
                                        p_user[k] = dv
                                if not str(p_user.get("id") or "").strip() and str(d_user.get("id") or "").strip():
                                    p_user["id"] = d_user.get("id")
                                if not str(p_user.get("name") or "").strip() and str(d_user.get("name") or "").strip():
                                    p_user["name"] = d_user.get("name")
                                payload["user"] = p_user
                            return extract_card_payload(source, payload, ct)
                        # Backward compat (older jobs): profile can be derived from resource.github.data.
                        data_art = self._artifact_store.get_artifact(job.id, "resource.github.data")
                        if data_art is not None and isinstance(data_art.payload, dict):
                            return extract_card_payload(source, data_art.payload, ct)
                        raise ValueError("missing resource.github.profile")

                    preview_art = self._artifact_store.get_artifact(job.id, "resource.github.preview")
                    preview = preview_art.payload if (preview_art is not None and isinstance(preview_art.payload, dict)) else {}

                    data_art = self._artifact_store.get_artifact(job.id, "resource.github.data")
                    data = data_art.payload if (data_art is not None and isinstance(data_art.payload, dict)) else None

                    # Fast cards (data-only)
                    if ct in ("activity", "stats"):
                        if not isinstance(data, dict):
                            raise ValueError("missing resource.github.data")
                        return extract_card_payload(source, data, ct)

                    # Derived cards (no per-card LLM): read from the fused enrich artifact.
                    if ct in ("repos", "role_model", "roast", "summary"):
                        enrich_art = self._artifact_store.get_artifact(job.id, "resource.github.enrich")
                        if enrich_art is not None and isinstance(enrich_art.payload, dict):
                            return extract_card_payload(source, enrich_art.payload, ct)

                    from server.api.github_analyzer_api import get_analyzer  # local import (heavy)

                    analyzer = get_analyzer()

                    # Avoid sending huge PR node list to general LLM tasks.
                    ai_input: Dict[str, Any] = dict(data if isinstance(data, dict) else preview)
                    ai_input.pop("_pull_requests", None)

                    if ct == "repos":
                        base = data if isinstance(data, dict) else preview
                        if not isinstance(base, dict) or not base:
                            raise ValueError("missing GitHub preview/data")

                        feature_project = base.get("feature_project")
                        top_projects = base.get("top_projects") or []
                        pr_nodes = ((data or {}).get("_pull_requests") or {}).get("nodes") or []

                        try:
                            budget_s = float(os.getenv("DINQ_GITHUB_REPOS_AI_BUDGET_SECONDS", "10") or "10")
                        except Exception:
                            budget_s = 10.0
                        budget_s = max(0.0, min(float(budget_s), 60.0))
                        t_budget = time.monotonic()

                        def remaining_s() -> float:
                            if budget_s <= 0:
                                return 0.0
                            return max(0.0, float(budget_s) - (time.monotonic() - t_budget))

                        feature_out = dict(feature_project or {}) if isinstance(feature_project, dict) else feature_project
                        if isinstance(feature_out, dict) and feature_out:
                            remaining = remaining_s()
                            try:
                                tags_timeout = float(os.getenv("DINQ_GITHUB_REPO_TAGS_TIMEOUT_SECONDS", "3") or "3")
                            except Exception:
                                tags_timeout = 3.0
                            tags_timeout = max(0.0, min(float(tags_timeout), float(remaining)))
                            if tags_timeout >= 0.5:
                                progress("ai_repo_tags", "Generating repository tags...", {"timeout_seconds": tags_timeout})
                                repo_tags = _run_coro(
                                    analyzer.safe_ai_call(
                                        asyncio.wait_for(analyzer.ai_repository_tags(feature_out), timeout=float(tags_timeout)),
                                        "repository_tags",
                                        [],
                                    )
                                )
                                if repo_tags:
                                    feature_out["tags"] = repo_tags

                        most_pr = None
                        best_pr_status = "skipped"
                        should_queue_bg_best_pr = False
                        if pr_nodes and remaining_s() >= 0.5:
                            try:
                                max_candidates = int(os.getenv("DINQ_GITHUB_BEST_PR_MAX_CANDIDATES", "10") or "10")
                            except Exception:
                                max_candidates = 10
                            candidates = _github_pr_candidates(pr_nodes, max_candidates=max_candidates)
                            if candidates:
                                try:
                                    soft_timeout = float(os.getenv("DINQ_GITHUB_BEST_PR_SOFT_TIMEOUT_SECONDS", "10") or "10")
                                except Exception:
                                    soft_timeout = 10.0
                                soft_timeout = max(0.0, min(float(soft_timeout), float(remaining_s())))
                                progress(
                                    "ai_best_pr",
                                    "Finding most valuable pull request...",
                                    {"candidates": len(candidates), "timeout_seconds": soft_timeout},
                                )
                                if soft_timeout >= 0.5:
                                    most_pr, best_pr_status = _github_best_pr_llm(candidates, timeout_seconds=soft_timeout)
                                else:
                                    most_pr, best_pr_status = None, "budget_exhausted"
                                if most_pr is None:
                                    most_pr = _github_best_pr_fallback(candidates)
                            else:
                                # No usable PR candidates; keep None.
                                most_pr = None
                        else:
                            if not pr_nodes:
                                best_pr_status = "missing_pr_data"
                            else:
                                best_pr_status = "budget_exhausted"
                            should_queue_bg_best_pr = True

                        if best_pr_status == "timeout":
                            # Keep UX fast: return heuristic best_pr, but queue a background refine that can run later.
                            should_queue_bg_best_pr = True
                            try:
                                cards = self._job_store.list_cards_for_job(job.id)
                                exists = any(str(getattr(c, "card_type", "") or "") == "resource.github.best_pr" for c in cards)
                                if not exists:
                                    self._job_store.create_cards(
                                        job.id,
                                        [
                                            {
                                                "card_type": "resource.github.best_pr",
                                                "status": "pending",
                                                "depends_on": ["resource.github.data"],
                                                # Background refine should not preempt user-facing cards.
                                                "priority": 1,
                                                "concurrency_group": "llm",
                                                "input": {"reason": "ai_best_pr_timeout", "max_candidates": 50},
                                            }
                                        ],
                                    )
                                    progress("ai_best_pr_deferred", "Queued best PR refinement in background", {"reason": "timeout"})
                            except Exception:
                                pass
                        elif should_queue_bg_best_pr and best_pr_status in ("missing_pr_data", "budget_exhausted"):
                            # If the PR list isn't available yet (or we ran out of 10s budget), queue background refine anyway.
                            try:
                                cards = self._job_store.list_cards_for_job(job.id)
                                exists = any(str(getattr(c, "card_type", "") or "") == "resource.github.best_pr" for c in cards)
                                if not exists:
                                    self._job_store.create_cards(
                                        job.id,
                                        [
                                            {
                                                "card_type": "resource.github.best_pr",
                                                "status": "pending",
                                                "depends_on": ["resource.github.data"],
                                                "priority": 1,
                                                "concurrency_group": "llm",
                                                "input": {"reason": best_pr_status, "max_candidates": 50},
                                            }
                                        ],
                                    )
                                    progress("ai_best_pr_deferred", "Queued best PR refinement in background", {"reason": best_pr_status})
                            except Exception:
                                pass

                        return {
                            "feature_project": feature_out,
                            "top_projects": top_projects,
                            "most_valuable_pull_request": most_pr,
                        }

                    if ct == "role_model":
                        progress("ai_role_model", "Generating role model...", None)
                        role_model = _run_coro(
                            analyzer.safe_ai_call(
                                analyzer.ai_role_model(ai_input),
                                "role_model",
                                {},
                            )
                        )
                        return role_model or {}

                    if ct == "roast":
                        progress("ai_roast", "Generating roast...", None)
                        roast = _run_coro(
                            analyzer.safe_ai_call(
                                analyzer.ai_roast(ai_input),
                                "roast",
                                "No roast available",
                            )
                        )
                        return roast

                    if ct == "summary":
                        progress("ai_valuation", "Generating valuation and level...", None)
                        valuation = _run_coro(
                            analyzer.safe_ai_call(
                                analyzer.ai_valuation_and_level(ai_input),
                                "valuation_and_level",
                                {"level": "Unknown", "salary_range": "Unknown", "total_compensation": "Unknown"},
                            )
                        )
                        return valuation if isinstance(valuation, dict) else {}

                    # Fallback: if needed, try aggregated full_report.
                    artifact = self._artifact_store.get_artifact(job.id, "full_report")
                    if artifact is not None and isinstance(artifact.payload, dict):
                        return extract_card_payload(source, artifact.payload, ct)
                    raise ValueError(f"unsupported github card: {ct}")

                if source == "scholar":
                    base_art = self._artifact_store.get_artifact(job.id, "resource.scholar.full")
                    if base_art is None or not isinstance(base_art.payload, dict):
                        base_art = self._artifact_store.get_artifact(job.id, "resource.scholar.page0")
                    if base_art is None or not isinstance(base_art.payload, dict):
                        base_art = self._artifact_store.get_artifact(job.id, "resource.scholar.base")
                    if base_art is None or not isinstance(base_art.payload, dict):
                        raise ValueError("missing resource.scholar.page0")
                    report = dict(base_art.payload or {})

                    # Attach level info (used by estimatedSalary/researcherCharacter) when available.
                    level_art = self._artifact_store.get_artifact(job.id, "resource.scholar.level")
                    if level_art is not None and isinstance(level_art.payload, dict) and level_art.payload:
                        report["level_info"] = dict(level_art.payload or {})

                    if ct == "criticalReview":
                        from server.prompts.researcher_evaluator import generate_critical_evaluation

                        progress("ai_critical_review", "Generating critical review...", None)
                        text = generate_critical_evaluation(report) or ""
                        return {"blockTitle": "Roast", "evaluation": str(text).strip() or None}

                    # Scholar role model is derived from an external reference set (top_ai_talents.csv).
                    # Compute it on-demand for the `roleModel` card to avoid slowing down other cards.
                    if ct == "roleModel":
                        try:
                            existing = report.get("role_model")
                            if not (isinstance(existing, dict) and existing.get("name")):
                                from server.services.scholar.role_model_service import get_role_model as _get_role_model

                                role_model = _get_role_model(report, callback=None)
                                if isinstance(role_model, dict) and role_model.get("name"):
                                    report["role_model"] = role_model
                        except Exception:
                            pass

                    from server.transform_profile import transform_data

                    transformed = transform_data(report) if isinstance(report, dict) else {}
                    if not isinstance(transformed, dict):
                        transformed = {}
                    profile = transformed.get("researcherProfile") if isinstance(transformed.get("researcherProfile"), dict) else {}
                    researcher_info = profile.get("researcherInfo") if isinstance(profile.get("researcherInfo"), dict) else {}
                    blocks = profile.get("dataBlocks") if isinstance(profile.get("dataBlocks"), dict) else {}

                    def _parse_usd(value: Any) -> Optional[int]:
                        if value is None:
                            return None
                        if isinstance(value, (int, float)) and not isinstance(value, bool):
                            return int(value)
                        s = str(value).strip().lower()
                        if not s:
                            return None
                        s = s.replace(",", "")
                        s = s.replace("$", "").replace("usd", "").strip()
                        s = s.replace("–", "-").replace("—", "-").replace("~", "-").replace("〜", "-").replace("～", "-")
                        s = re.sub(r"\\s+to\\s+", "-", s)
                        # Range: "200k-300k", "200000-300000"
                        if "-" in s and not s.startswith("-"):
                            parts = [p.strip() for p in s.split("-") if p.strip()]
                            if len(parts) == 2:
                                a = _parse_usd(parts[0])
                                b = _parse_usd(parts[1])
                                if a is not None and b is not None:
                                    return int((a + b) / 2)
                        # Single: "250k"
                        if s.endswith("k"):
                            try:
                                return int(float(s[:-1]) * 1000)
                            except Exception:
                                return None
                        m = re.search(r"(\\d+(?:\\.\\d+)?)", s)
                        if not m:
                            return None
                        try:
                            return int(float(m.group(1)))
                        except Exception:
                            return None

                    if ct == "researcherInfo":
                        return researcher_info

                    payload = blocks.get(ct) if isinstance(blocks.get(ct), dict) else {}
                    if ct == "estimatedSalary":
                        out = dict(payload or {})
                        earnings_usd = _parse_usd(out.get("earningsPerYearUSD"))
                        if earnings_usd is None or int(earnings_usd or 0) <= 0 or int(earnings_usd or 0) < 10_000:
                            lvl = ""
                            level_eq = out.get("levelEquivalency") if isinstance(out.get("levelEquivalency"), dict) else {}
                            if isinstance(level_eq, dict):
                                lvl = str(level_eq.get("us") or "").strip().upper()
                            by_level = {
                                "L3": 150_000,
                                "L4": 220_000,
                                "L5": 310_000,
                                "L6": 440_000,
                                "L7": 640_000,
                                "L8": 905_000,
                            }
                            earnings_usd = int(by_level.get(lvl) or 300_000)
                        out["earningsPerYearUSD"] = int(earnings_usd) if earnings_usd is not None else None
                        return out

                    return payload

                if source == "linkedin":
                    raw_art = self._artifact_store.get_artifact(job.id, "resource.linkedin.raw_profile")
                    if raw_art is None or not isinstance(raw_art.payload, dict):
                        raise ValueError("missing resource.linkedin.raw_profile")
                    raw_report = dict(raw_art.payload or {})

                    enrich_art = self._artifact_store.get_artifact(job.id, "resource.linkedin.enrich")
                    enrich = enrich_art.payload if (enrich_art is not None and isinstance(enrich_art.payload, dict)) else {}

                    if ct == "profile":
                        profile_data = raw_report.get("profile_data") if isinstance(raw_report.get("profile_data"), dict) else {}
                        merged_profile: Dict[str, Any] = dict(profile_data)

                        if isinstance(enrich.get("skills"), dict):
                            merged_profile["skills"] = enrich.get("skills")
                        if isinstance(enrich.get("career"), dict):
                            merged_profile["career"] = enrich.get("career")
                        if isinstance(enrich.get("role_model"), dict):
                            merged_profile["role_model"] = enrich.get("role_model")

                        money_payload = enrich.get("money") if isinstance(enrich.get("money"), dict) else None
                        if money_payload is None and isinstance(enrich.get("money_analysis"), dict):
                            money_payload = enrich.get("money_analysis")
                        if isinstance(money_payload, dict):
                            merged_profile["money_analysis"] = money_payload

                        if isinstance(enrich.get("colleagues_view"), dict):
                            merged_profile["colleagues_view"] = enrich.get("colleagues_view")
                        if isinstance(enrich.get("life_well_being"), dict):
                            merged_profile["life_well_being"] = enrich.get("life_well_being")

                        work_summary = enrich.get("work_experience_summary")
                        if isinstance(work_summary, str) and work_summary.strip():
                            merged_profile["work_experience_summary"] = work_summary.strip()
                        edu_summary = enrich.get("education_summary")
                        if isinstance(edu_summary, str) and edu_summary.strip():
                            merged_profile["education_summary"] = edu_summary.strip()

                        summary_payload = enrich.get("summary") if isinstance(enrich.get("summary"), dict) else {}
                        about = summary_payload.get("about")
                        if about is not None:
                            merged_profile["about"] = about
                        tags = summary_payload.get("personal_tags")
                        if tags is not None:
                            merged_profile["personal_tags"] = tags

                        raw_report["profile_data"] = merged_profile
                        return extract_card_payload(source, raw_report, ct)

                    profile_data = raw_report.get("profile_data") if isinstance(raw_report.get("profile_data"), dict) else {}
                    raw_profile = profile_data.get("raw_profile") if isinstance(profile_data.get("raw_profile"), dict) else {}
                    person_name = str(profile_data.get("name") or raw_profile.get("fullName") or "Unknown").strip() or "Unknown"

                    if ct == "skills":
                        payload = enrich.get("skills") if isinstance(enrich.get("skills"), dict) else {}
                        industry = payload.get("industry_knowledge") or []
                        tools = payload.get("tools_technologies") or []
                        interpersonal = payload.get("interpersonal_skills") or []
                        languages = payload.get("language") or []
                        return {
                            "industry_knowledge": industry,
                            "tools_technologies": tools,
                            "interpersonal_skills": interpersonal,
                            "language": languages,
                        }

                    if ct == "career":
                        career = enrich.get("career") if isinstance(enrich.get("career"), dict) else {}
                        experiences = profile_data.get("work_experience") or raw_profile.get("experiences") or []
                        educations = profile_data.get("education") or raw_profile.get("educations") or []
                        work_summary = str(enrich.get("work_experience_summary") or "").strip()
                        edu_summary = str(enrich.get("education_summary") or "").strip()
                        if not career:
                            headline = str(raw_profile.get("headline") or raw_profile.get("occupation") or "").strip()
                            career = {
                                "future_development_potential": (
                                    f"{person_name} shows strong growth potential"
                                    + (f" as a {headline}." if headline else ".")
                                    + " Focus on deepening domain expertise and expanding leadership impact."
                                ),
                                "development_advice": {
                                    "past_evaluation": "Track record indicates consistent delivery; continue to strengthen strategic ownership and cross-functional influence.",
                                    "future_advice": "Prioritize high-leverage projects, build a clear specialization narrative, and invest in communication and mentoring to unlock the next level.",
                                },
                            }
                        return {
                            "career": career,
                            "work_experience": experiences,
                            "education": educations,
                            "work_experience_summary": work_summary,
                            "education_summary": edu_summary,
                        }

                    if ct == "role_model":
                        role_model = enrich.get("role_model") if isinstance(enrich.get("role_model"), dict) else {}
                        return role_model if isinstance(role_model, dict) else {}

                    if ct == "money":
                        money = enrich.get("money") if isinstance(enrich.get("money"), dict) else {}
                        return money if isinstance(money, dict) else {}

                    if ct == "roast":
                        from server.linkedin_analyzer.roast_service import get_linkedin_roast

                        progress("ai_roast", "Generating roast...", None)
                        roast_profile = raw_profile
                        # raw_profile may be pruned for storage; restore experience/education lists for the roast prompt.
                        exp = profile_data.get("work_experience") if isinstance(profile_data.get("work_experience"), list) else []
                        edu = profile_data.get("education") if isinstance(profile_data.get("education"), list) else []
                        if exp and (not isinstance(roast_profile.get("experiences"), list) or not roast_profile.get("experiences")):
                            roast_profile = dict(roast_profile)
                            roast_profile["experiences"] = exp
                        if edu and (not isinstance(roast_profile.get("educations"), list) or not roast_profile.get("educations")):
                            roast_profile = dict(roast_profile)
                            roast_profile["educations"] = edu
                        roast = get_linkedin_roast(roast_profile, person_name)
                        return roast

                    if ct == "summary":
                        payload = enrich.get("summary") if isinstance(enrich.get("summary"), dict) else {}
                        about = str(payload.get("about") or "").strip()
                        tags = payload.get("personal_tags") if isinstance(payload.get("personal_tags"), list) else []
                        if not about:
                            about = str(profile_data.get("about") or raw_profile.get("about") or "").strip()
                        if not tags:
                            skills_payload = enrich.get("skills") if isinstance(enrich.get("skills"), dict) else {}
                            pools = []
                            for k in ("industry_knowledge", "tools_technologies", "interpersonal_skills", "language"):
                                v = skills_payload.get(k)
                                if isinstance(v, list):
                                    pools.extend([str(x).strip() for x in v if str(x).strip()])
                            seen = set()
                            dedup = []
                            for x in pools:
                                key = x.lower()
                                if key in seen:
                                    continue
                                seen.add(key)
                                # Title-case tokens for UI consistency.
                                dedup.append(" ".join([p.capitalize() for p in x.split()]))
                            tags = dedup[:6]
                        return {"about": about, "personal_tags": tags}

                    artifact = self._artifact_store.get_artifact(job.id, "full_report")
                    if artifact is not None and isinstance(artifact.payload, dict):
                        return extract_card_payload(source, artifact.payload, ct)
                    raise ValueError(f"unsupported linkedin card: {ct}")

            artifact = self._artifact_store.get_artifact(job.id, "full_report")
            if artifact is None or not isinstance(artifact.payload, dict):
                    raise ValueError("full report not available")
            return extract_card_payload(source, artifact.payload, card.card_type)

        def _emit_final_text_deltas(text: Any) -> None:
            if not delta_emitter:
                return
            if not isinstance(text, str):
                return
            t = str(text or "")
            if not t.strip():
                return
            chunk = 120
            for i in range(0, len(t), chunk):
                delta_emitter.on_delta(t[i : i + chunk])
            delta_emitter.flush()

        try:
            if delta_emitter:
                # LinkedIn roast uses a strict-JSON LLM call internally; avoid streaming raw JSON.
                # Stream the finalized roast text instead.
                if source == "linkedin" and str(card.card_type) == "roast":
                    out = run()
                    _emit_final_text_deltas(out)
                    return out

                # Prefer "pseudo-streaming" (non-stream request + chunked deltas) for stability.
                # Provider streaming can have large/unstable TTFB in production.
                with llm_stream_context(delta_emitter.on_delta, force_stream=False):
                    return run()
            return run()
        finally:
            if delta_emitter:
                delta_emitter.flush()
