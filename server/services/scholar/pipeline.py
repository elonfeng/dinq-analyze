"""
Scholar pipeline (6-stage).

目标：
- 把 Scholar 报告生成逻辑从 ScholarService 中抽离，形成可复用、可单测的 stage pipeline
- 通过显式 deps 注入（data_fetcher/analyzer/cache/LLM enrich 等）降低耦合
- 每个 stage 只依赖 ctx（cancel/progress）与 deps/state，方便复用与单测

Stages:
  search -> fetch_profile -> analyze -> enrich -> persist -> render
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

import hashlib
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from server.services.scholar.cancel import raise_if_cancelled
from server.utils.timing import elapsed_ms, now_perf


StatusSender = Callable[..., None]

def _read_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return int(default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return int(default)


# 0 means "unlimited" (fetch until no more pages).
_MAX_PAPERS_FULL_DEFAULT = 500


def _max_papers_full() -> int:
    return max(0, _read_int_env("DINQ_SCHOLAR_MAX_PAPERS_FULL", _MAX_PAPERS_FULL_DEFAULT))


@dataclass(frozen=True)
class ScholarPipelineDeps:
    data_fetcher: Any
    analyzer: Any

    # Optional external search (e.g. Tavily).
    tvly_client: Optional[Any] = None
    tavily_id_extractor: Optional[Callable[[Dict[str, Any]], Optional[str]]] = None

    # Cache hooks (optional).
    use_cache: bool = False
    cache_max_age_days: int = 3
    cache_get: Optional[Callable[..., Optional[Dict[str, Any]]]] = None
    cache_save: Optional[Callable[[Dict[str, Any], str], None]] = None
    cache_validate: Optional[Callable[..., Dict[str, Any]]] = None

    # Render helpers.
    avatar_provider: Optional[Callable[[], str]] = None
    description_provider: Optional[Callable[[str], str]] = None

    # Enrich helpers (all optional; missing deps -> skip that subtask).
    best_collaborator: Optional[Callable[..., Any]] = None
    arxiv_finder: Optional[Callable[[str], Any]] = None
    news_provider: Optional[Callable[[str], Any]] = None
    role_model_provider: Optional[Callable[..., Any]] = None
    career_level_provider: Optional[Callable[..., Any]] = None
    critical_evaluator: Optional[Callable[..., Any]] = None
    paper_summary_provider: Optional[Callable[..., Any]] = None

    max_enrich_workers: int = 5
    logger: Optional[Any] = None


class ScholarPipelineContext:
    def __init__(
        self,
        *,
        callback: Optional[Callable] = None,
        cancel_event: Optional[Any] = None,
        status_sender: Optional[StatusSender] = None,
    ):
        self.callback = callback
        self.cancel_event = cancel_event
        self._status_sender = status_sender
        self._last_progress: float = 0.0

    @property
    def last_progress(self) -> float:
        return self._last_progress

    def cancelled(self) -> bool:
        return bool(self.cancel_event) and getattr(self.cancel_event, "is_set", lambda: False)()

    def status(self, message: str, progress: Optional[float] = None, **extra_fields) -> None:
        raise_if_cancelled(self.cancel_event)

        clamped: Optional[float] = None
        if progress is not None:
            try:
                clamped = float(progress)
            except (TypeError, ValueError):
                clamped = self._last_progress
            clamped = max(0.0, min(100.0, clamped))
            clamped = max(self._last_progress, clamped)
            self._last_progress = clamped

        if self._status_sender is not None:
            self._status_sender(message, self.callback, progress=clamped, **extra_fields)
            return

        # Fallback: emit structured message to callback if possible.
        if self.callback:
            try:
                self.callback({"message": message, "progress": clamped, **extra_fields})
            except Exception:  # noqa: BLE001
                self.callback(str(message))


@dataclass
class ScholarPipelineState:
    researcher_name: Optional[str] = None
    scholar_id: Optional[str] = None
    user_id: Optional[str] = None

    author_info: Optional[Dict[str, Any]] = None
    author_data: Optional[Dict[str, Any]] = None

    pub_stats: Dict[str, Any] = field(default_factory=dict)
    coauthor_stats: Dict[str, Any] = field(default_factory=dict)
    rating: Any = None

    report: Optional[Dict[str, Any]] = None
    from_cache: bool = False


def _try_load_cache(ctx: ScholarPipelineContext, deps: ScholarPipelineDeps, state: ScholarPipelineState) -> bool:
    if not deps.use_cache or deps.cache_get is None or not state.scholar_id:
        return False

    raise_if_cancelled(ctx.cancel_event)
    cached = deps.cache_get(state.scholar_id, deps.cache_max_age_days, name=state.researcher_name)
    if not cached:
        return False

    ctx.status("Validating cached data...", progress=20.0)
    raise_if_cancelled(ctx.cancel_event)

    validated = (
        deps.cache_validate(
            cached,
            deps.data_fetcher,
            deps.analyzer,
            ctx.callback,
            cancel_event=ctx.cancel_event,
        )
        if deps.cache_validate is not None
        else cached
    )

    if isinstance(validated, dict):
        state.report = validated
        state.from_cache = True
        return True

    return False


def stage_search(ctx: ScholarPipelineContext, deps: ScholarPipelineDeps, state: ScholarPipelineState) -> bool:
    if not state.researcher_name and not state.scholar_id:
        return False

    # If scholar_id is already known, try cache first.
    if state.scholar_id and _try_load_cache(ctx, deps, state):
        return True

    if state.scholar_id:
        state.author_info = {"scholar_id": state.scholar_id}
        return True

    researcher_name = state.researcher_name or ""
    ctx.status(f"Getting scholar ID for: {researcher_name}", progress=5.0)

    # External search (Tavily) if available.
    if deps.tvly_client is not None and deps.tavily_id_extractor is not None:
        raise_if_cancelled(ctx.cancel_event)
        response = deps.tvly_client.search(query=researcher_name)
        raise_if_cancelled(ctx.cancel_event)
        resolved = deps.tavily_id_extractor(response)
        if resolved:
            state.scholar_id = resolved
            # Second chance cache lookup after resolving scholar_id (效率优化).
            if _try_load_cache(ctx, deps, state):
                return True
            state.author_info = {"scholar_id": state.scholar_id}
            return True

    # Fallback: search via data_fetcher.
    author_info = deps.data_fetcher.search_researcher(name=researcher_name, scholar_id=None, user_id=state.user_id)
    if not author_info:
        ctx.status("No scholar ID found. Please manually input the scholar ID!", progress=100.0)
        return False

    state.author_info = author_info
    state.scholar_id = author_info.get("scholar_id") or state.scholar_id
    if state.scholar_id and _try_load_cache(ctx, deps, state):
        return True

    return True


def stage_fetch_profile(ctx: ScholarPipelineContext, deps: ScholarPipelineDeps, state: ScholarPipelineState, *, max_papers: int) -> bool:
    if state.from_cache:
        return True

    if not state.author_info:
        return False

    ctx.status("Retrieving full profile...", progress=20.0)
    raise_if_cancelled(ctx.cancel_event)
    author_data = deps.data_fetcher.get_full_profile(
        state.author_info,
        max_papers=max_papers,
        cancel_event=ctx.cancel_event,
        user_id=state.user_id,
        progress_callback=ctx.callback,
    )
    if not author_data:
        ctx.status("Could not retrieve full profile", progress=100.0)
        return False

    state.author_data = author_data
    state.researcher_name = author_data.get("name") or state.researcher_name
    ctx.status(f"Found researcher: {state.researcher_name or ''}", progress=25.0)
    return True


def stage_analyze(ctx: ScholarPipelineContext, deps: ScholarPipelineDeps, state: ScholarPipelineState) -> bool:
    if state.from_cache:
        return True

    if not state.author_data:
        return False

    ctx.status("Analyzing publications...", progress=35.0)
    raise_if_cancelled(ctx.cancel_event)
    state.pub_stats = deps.analyzer.analyze_publications(state.author_data, cancel_event=ctx.cancel_event) or {}

    ctx.status("Analyzing co-authors...", progress=45.0)
    raise_if_cancelled(ctx.cancel_event)
    state.coauthor_stats = deps.analyzer.analyze_coauthors(state.author_data, cancel_event=ctx.cancel_event) or {}
    state.coauthor_stats["main_author"] = state.author_data.get("name", "")

    ctx.status("Calculating researcher rating...", progress=50.0)
    raise_if_cancelled(ctx.cancel_event)
    state.rating = deps.analyzer.calculate_researcher_rating(state.author_data, state.pub_stats)
    return True


def _build_base_report(deps: ScholarPipelineDeps, state: ScholarPipelineState) -> Dict[str, Any]:
    if state.author_data is None:
        return state.report or {}

    name = state.author_data.get("name", "")
    avatar_url = deps.avatar_provider() if deps.avatar_provider is not None else ""
    description = (
        deps.description_provider(name) if deps.description_provider is not None else ""
    )

    preview_max = max(0, min(_read_int_env("DINQ_SCHOLAR_PREVIEW_MAX_PAPERS", 30), 200))
    papers_preview = []
    try:
        sid = str(state.scholar_id or state.author_data.get("scholar_id") or "").strip()
    except Exception:
        sid = ""
    if preview_max > 0 and isinstance(state.author_data, dict):
        papers = state.author_data.get("papers")
        if isinstance(papers, list):
            for paper in papers[:preview_max]:
                if not isinstance(paper, dict):
                    continue
                title = str(paper.get("title") or "").strip()
                if not title:
                    continue
                year_raw = str(paper.get("year") or "").strip()
                year = int(year_raw) if year_raw.isdigit() else None
                venue = str(paper.get("venue") or "").strip() or None
                citations_raw = str(paper.get("citations") or "").strip()
                try:
                    citations = int(citations_raw) if citations_raw else 0
                except Exception:  # noqa: BLE001
                    citations = 0
                authors = paper.get("authors")
                if isinstance(authors, list):
                    authors = [str(a) for a in authors if str(a).strip()][:8]
                else:
                    authors = None

                raw_id = f"{sid}|{title}|{year_raw}|{venue or ''}".encode("utf-8", errors="ignore")
                pid = hashlib.sha1(raw_id).hexdigest()[:16]
                item: Dict[str, Any] = {"id": f"scholar:{sid}:{pid}", "title": title, "citations": citations}
                if year is not None:
                    item["year"] = year
                if venue is not None:
                    item["venue"] = venue
                if authors is not None:
                    item["authors"] = authors
                if paper.get("author_position") is not None:
                    item["author_position"] = paper.get("author_position")
                papers_preview.append(item)

    report: Dict[str, Any] = {
        "researcher": {
            "name": name,
            "abbreviated_name": state.author_data.get("abbreviated_name", ""),
            "affiliation": state.author_data.get("affiliation", ""),
            "email": state.author_data.get("email", ""),
            "research_fields": state.author_data.get("research_fields", []),
            "total_citations": state.author_data.get("total_citations", 0),
            "citations_5y": state.author_data.get("citations_5y", 0),
            "h_index": state.author_data.get("h_index", 0),
            "h_index_5y": state.author_data.get("h_index_5y", 0),
            "yearly_citations": state.author_data.get("yearly_citations", {}),
            "scholar_id": state.scholar_id or state.author_data.get("scholar_id", ""),
            "avatar": avatar_url,
            "description": description,
        },
        "publication_stats": state.pub_stats,
        "papers_preview": papers_preview,
        "coauthor_stats": state.coauthor_stats,
        "rating": state.rating,
        "most_frequent_collaborator": None,
        "paper_news": state.pub_stats.get("paper_news", {}),
    }
    return report


def stage_enrich(ctx: ScholarPipelineContext, deps: ScholarPipelineDeps, state: ScholarPipelineState) -> bool:
    if state.from_cache:
        return True

    # Always build report skeleton; enrich subtasks may be skipped by flags/deps.
    if state.report is None:
        if state.author_data is not None:
            ctx.status("Generating avatar and description...", progress=70.0)
            ctx.status("Compiling report...", progress=75.0)
        state.report = _build_base_report(deps, state)

    if deps.logger is not None:
        deps.logger.info("Starting enrichment stage (parallel)")

    # Some enrich helpers require the report dict.
    report = state.report

    tasks = []
    if deps.best_collaborator is not None and state.coauthor_stats:
        tasks.append(("best_collaborator", deps.best_collaborator, (deps.data_fetcher, state.coauthor_stats, ctx.callback, deps.analyzer)))

    most_cited = state.pub_stats.get("most_cited_paper") if isinstance(state.pub_stats, dict) else None
    title = most_cited.get("title") if isinstance(most_cited, dict) else None
    if title:
        if deps.arxiv_finder is not None:
            tasks.append(("arxiv", deps.arxiv_finder, (title,)))
        if deps.news_provider is not None:
            tasks.append(("news", deps.news_provider, (title,)))

    if deps.role_model_provider is not None:
        tasks.append(("role_model", deps.role_model_provider, (report, ctx.callback)))

    if deps.career_level_provider is not None:
        tasks.append(("career_level", deps.career_level_provider, (report, False, ctx.callback)))

    if deps.critical_evaluator is not None:
        tasks.append(("critical_evaluation", deps.critical_evaluator, (report,)))

    paper_of_year = state.pub_stats.get("paper_of_year") if isinstance(state.pub_stats, dict) else None
    if paper_of_year and deps.paper_summary_provider is not None:
        tasks.append(("paper_of_year_summary", deps.paper_summary_provider, (paper_of_year,)))

    if not tasks:
        return True

    progress_start = max(ctx.last_progress, 80.0)
    progress_end = 92.0
    ctx.status("Running enrichment tasks...", progress=progress_start)

    executor = ThreadPoolExecutor(max_workers=max(1, int(deps.max_enrich_workers)))
    future_to_name = {}
    started_at = time.time()
    try:
        for name, func, args in tasks:
            raise_if_cancelled(ctx.cancel_event)
            future_to_name[executor.submit(func, *args)] = name

        total = len(future_to_name) or 1
        completed = 0
        results: Dict[str, Any] = {}

        for fut in as_completed(future_to_name):
            raise_if_cancelled(ctx.cancel_event)
            name = future_to_name[fut]
            try:
                results[name] = fut.result()
                if deps.logger is not None:
                    deps.logger.info("Enrich task %s completed", name)
            except Exception as exc:  # noqa: BLE001
                if deps.logger is not None:
                    deps.logger.error("Enrich task %s failed: %s", name, exc)
                results[name] = None
            finally:
                completed += 1
                progress = progress_start + (completed / total) * (progress_end - progress_start)
                ctx.status(f"{name} completed", progress=progress)

        # Merge results back into report/pub_stats
        collaborator = results.get("best_collaborator")
        if collaborator:
            report["most_frequent_collaborator"] = collaborator

        arxiv = results.get("arxiv")
        if arxiv:
            state.pub_stats["most_cited_ai_paper"] = arxiv

        news = results.get("news")
        if news:
            state.pub_stats["paper_news"] = news

        role_model = results.get("role_model")
        if role_model:
            report["role_model"] = role_model

        critical = results.get("critical_evaluation")
        if critical:
            report["critical_evaluation"] = critical

        summary = results.get("paper_of_year_summary")
        if summary and isinstance(paper_of_year, dict):
            paper_of_year["summary"] = summary

        # Keep report.paper_news in sync.
        report["paper_news"] = state.pub_stats.get("paper_news", {})

        return True
    finally:
        if ctx.cancelled():
            for fut in future_to_name:
                fut.cancel()
            executor.shutdown(wait=False)
        else:
            executor.shutdown(wait=True)

        if deps.logger is not None:
            deps.logger.info("[Timing] Enrichment elapsed: %.2fs", time.time() - started_at)


def stage_persist(ctx: ScholarPipelineContext, deps: ScholarPipelineDeps, state: ScholarPipelineState) -> bool:
    if state.from_cache:
        return True

    if not deps.use_cache or deps.cache_save is None:
        return True

    if state.report is None:
        state.report = _build_base_report(deps, state)

    cache_id = state.scholar_id
    if not cache_id and isinstance(state.author_data, dict):
        cache_id = state.author_data.get("scholar_id")
    if not cache_id:
        return True

    ctx.status("Saving data to cache...", progress=95.0)
    raise_if_cancelled(ctx.cancel_event)
    deps.cache_save(state.report, cache_id)
    return True


def stage_render(ctx: ScholarPipelineContext, deps: ScholarPipelineDeps, state: ScholarPipelineState) -> Optional[Dict[str, Any]]:
    if state.report is None:
        state.report = _build_base_report(deps, state)

    if not state.report:
        return None

    # Ensure scholar_id is present in researcher payload (handles older cache payloads).
    if isinstance(state.report, dict):
        researcher = state.report.get("researcher")
        if isinstance(researcher, dict) and state.scholar_id and not researcher.get("scholar_id"):
            researcher["scholar_id"] = state.scholar_id

    # Best effort: remove internal marker if present in older cached payloads.
    if isinstance(state.report, dict) and "_from_cache" in state.report:
        state.report.pop("_from_cache", None)

    ctx.status(
        "Analysis completed (from cache)" if state.from_cache else "Analysis complete!",
        progress=100.0,
    )
    return state.report


def run_scholar_pipeline(
    *,
    deps: ScholarPipelineDeps,
    researcher_name: Optional[str] = None,
    scholar_id: Optional[str] = None,
    user_id: Optional[str] = None,
    max_papers: Optional[int] = None,
    callback: Optional[Callable] = None,
    cancel_event: Optional[Any] = None,
    status_sender: Optional[StatusSender] = None,
) -> Optional[Dict[str, Any]]:
    """
    Execute the 6-stage Scholar pipeline and return the final report dict.
    """

    ctx = ScholarPipelineContext(
        callback=callback,
        cancel_event=cancel_event,
        status_sender=status_sender,
    )

    state = ScholarPipelineState(
        researcher_name=researcher_name,
        scholar_id=scholar_id,
        user_id=user_id,
    )

    # Initial status (monotonic progress is enforced by ctx).
    if researcher_name:
        ctx.status(f"Searching for author: {researcher_name}", progress=5.0)
    if scholar_id:
        ctx.status(f"Generating report for ID: {scholar_id}...", progress=10.0)

    t_search = now_perf()
    if not stage_search(ctx, deps, state):
        ctx.status("Stage search failed", progress=ctx.last_progress, kind="timing", stage="search", duration_ms=elapsed_ms(t_search))
        return None
    ctx.status("Stage search completed", progress=ctx.last_progress, kind="timing", stage="search", duration_ms=elapsed_ms(t_search))
    if state.from_cache:
        t_render = now_perf()
        out = stage_render(ctx, deps, state)
        ctx.status("Stage render completed", progress=ctx.last_progress, kind="timing", stage="render", duration_ms=elapsed_ms(t_render))
        return out

    try:
        effective_max_papers = int(max_papers) if max_papers is not None else _max_papers_full()
    except (TypeError, ValueError):
        effective_max_papers = _max_papers_full()
    effective_max_papers = max(0, effective_max_papers)

    t_fetch = now_perf()
    if not stage_fetch_profile(ctx, deps, state, max_papers=effective_max_papers):
        ctx.status("Stage fetch_profile failed", progress=ctx.last_progress, kind="timing", stage="fetch_profile", duration_ms=elapsed_ms(t_fetch))
        return None
    ctx.status("Stage fetch_profile completed", progress=ctx.last_progress, kind="timing", stage="fetch_profile", duration_ms=elapsed_ms(t_fetch))

    t_analyze = now_perf()
    if not stage_analyze(ctx, deps, state):
        ctx.status("Stage analyze failed", progress=ctx.last_progress, kind="timing", stage="analyze", duration_ms=elapsed_ms(t_analyze))
        return None
    ctx.status("Stage analyze completed", progress=ctx.last_progress, kind="timing", stage="analyze", duration_ms=elapsed_ms(t_analyze))

    t_enrich = now_perf()
    if not stage_enrich(ctx, deps, state):
        ctx.status("Stage enrich failed", progress=ctx.last_progress, kind="timing", stage="enrich", duration_ms=elapsed_ms(t_enrich))
        return None
    ctx.status("Stage enrich completed", progress=ctx.last_progress, kind="timing", stage="enrich", duration_ms=elapsed_ms(t_enrich))

    t_persist = now_perf()
    if not stage_persist(ctx, deps, state):
        ctx.status("Stage persist failed", progress=ctx.last_progress, kind="timing", stage="persist", duration_ms=elapsed_ms(t_persist))
        return None
    ctx.status("Stage persist completed", progress=ctx.last_progress, kind="timing", stage="persist", duration_ms=elapsed_ms(t_persist))

    t_render = now_perf()
    out = stage_render(ctx, deps, state)
    ctx.status("Stage render completed", progress=ctx.last_progress, kind="timing", stage="render", duration_ms=elapsed_ms(t_render))
    return out
