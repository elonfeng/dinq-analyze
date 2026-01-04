from __future__ import annotations

import asyncio
import json
import math
import os
import random
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional

from dateutil.relativedelta import relativedelta
import requests

from server.github_analyzer.github_client import GithubClient
from server.github_analyzer.analyzer import DESC_PRESETS, parse_github_datetime
from server.github_analyzer.github_queries import MostPullRequestRepositoriesQuery
from server.utils.timing import elapsed_ms, now_perf


ProgressFn = Callable[[str, str, Optional[Dict[str, Any]]], None]


_LEVEL_RE = re.compile(r"^L\\s*(\\d{1,2})$", flags=re.IGNORECASE)


def _coerce_level(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    compact = raw.replace(" ", "").strip()
    m = _LEVEL_RE.match(compact)
    if m:
        try:
            n = int(m.group(1))
        except Exception:
            return ""
        return f"L{n}"

    lowered = raw.lower()
    # Best-effort map from descriptive labels to the internal L-level scale.
    if "distinguished" in lowered or "fellow" in lowered:
        return "L8"
    if "principal" in lowered or "director" in lowered:
        return "L7"
    if "staff" in lowered:
        return "L6"
    if "senior" in lowered:
        return "L5"
    if "mid" in lowered or "intermediate" in lowered:
        return "L4"
    if "junior" in lowered or "entry" in lowered or "intern" in lowered:
        return "L3"
    return ""


def _coerce_industry_ranking(value: Any) -> Optional[float]:
    """
    Normalize industry_ranking into a 0..1 percentile float.

    Accepts:
      - 0.25 (top 25%)
      - 25 (mistaken 25%)
    """

    try:
        if value is None:
            return None
        v = float(value)
    except Exception:
        return None

    if 1.0 < v <= 100.0:
        v = v / 100.0

    if not (0.0 < v <= 1.0):
        return None
    return float(v)


def _rest_profile(*, login: str, token: str, timeout_s: float) -> Optional[Dict[str, Any]]:
    url = f"https://api.github.com/users/{login}"
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = requests.get(url, headers=headers, timeout=float(timeout_s or 0) or 10.0)
    if resp.status_code != 200:
        return None
    data = resp.json() or {}
    if not isinstance(data, dict) or not data:
        return None

    node_id = str(data.get("node_id") or "").strip()
    if not node_id:
        return None

    try:
        public_repos = int(data.get("public_repos") or 0)
    except Exception:
        public_repos = 0

    # Map REST shape -> existing GraphQL-ish shape used by the unified cards.
    return {
        "id": node_id,
        "name": data.get("name"),
        "login": data.get("login") or login,
        "createdAt": data.get("created_at"),
        "bio": data.get("bio"),
        "avatarUrl": data.get("avatar_url"),
        "url": data.get("html_url") or data.get("url"),
        "repositories": {"totalCount": public_repos},
        # REST doesn't expose total issues/PRs; keep as unknown (not 0).
        "issues": {"totalCount": None},
        "pullRequests": {"totalCount": None},
    }


def fetch_github_profile(*, login: str, progress: Optional[ProgressFn] = None) -> Dict[str, Any]:
    """
    Fetch ONLY the GitHub user profile (fast path).

    This is used to guarantee "profile-first" UX within ~10s even if heavier GitHub
    data/AI cards are still running.
    """

    token = (os.getenv("GITHUB_TOKEN") or "").strip()
    if not token:
        raise ValueError("missing GITHUB_TOKEN")

    def emit(step: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        if progress:
            progress(step, message, data)

    user: Optional[Dict[str, Any]] = None
    status = "unknown"

    # Prefer REST for "profile-first" UX: it's simple, sync, and avoids async client teardown overhead.
    try:
        rest_timeout = float(os.getenv("DINQ_GITHUB_PROFILE_REST_TIMEOUT_SECONDS", "6") or "6")
    except Exception:
        rest_timeout = 6.0
    rest_timeout = max(1.0, min(rest_timeout, 15.0))

    emit("profile_fetch_rest", f"Fetching GitHub REST profile for {login}...", {"timeout_seconds": rest_timeout})
    t0 = now_perf()
    try:
        user = _rest_profile(login=login, token=token, timeout_s=rest_timeout)
    except Exception as exc:  # noqa: BLE001
        user = None
        emit("profile_fetch_rest_failed", "GitHub REST profile failed", {"error": str(exc)[:200]})
    if user:
        status = "rest"
        emit("timing.github.profile_rest", "GitHub profile fetched (REST)", {"duration_ms": elapsed_ms(t0)})

    # Fill missing count fields (issues/PRs) via a small GraphQL query.
    # REST is faster but doesn't expose these totals; the unified frontend schema expects them.
    if user and not _has_counts(user):
        try:
            fill_timeout = float(os.getenv("DINQ_GITHUB_PROFILE_GRAPHQL_FILL_TIMEOUT_SECONDS", "3") or "3")
        except Exception:
            fill_timeout = 3.0
        fill_timeout = max(0.0, min(fill_timeout, 20.0))
        if fill_timeout > 0:
            emit("profile_fetch_graphql_fill", f"Filling GitHub profile counts for {login}...", {"timeout_seconds": fill_timeout})
            t_fill = now_perf()
            gql_user = None
            try:
                async def _run_graphql_fill() -> Optional[Dict[str, Any]]:
                    github = GithubClient({"token": token})
                    try:
                        return await asyncio.wait_for(github.profile(login), timeout=float(fill_timeout or 0) or None)
                    finally:
                        await github.close()

                gql_user = asyncio.run(_run_graphql_fill())
            except Exception as exc:  # noqa: BLE001
                gql_user = None
                emit("profile_fetch_graphql_fill_failed", "GitHub GraphQL fill failed", {"error": str(exc)[:200]})

            if isinstance(gql_user, dict) and gql_user:
                for k in ("issues", "pullRequests", "repositories"):
                    if isinstance(gql_user.get(k), dict) and gql_user.get(k):
                        user[k] = gql_user.get(k)
                if str(gql_user.get("id") or "").strip():
                    user["id"] = gql_user.get("id")
                if str(gql_user.get("name") or "").strip():
                    user["name"] = gql_user.get("name")
                status = "rest+graphql"
                emit("timing.github.profile_graphql_fill", "GitHub profile counts filled (GraphQL)", {"duration_ms": elapsed_ms(t_fill)})

    # Fallback: GraphQL (fills issues/PR counts) if REST fails.
    if not user:
        try:
            graphql_timeout = float(os.getenv("DINQ_GITHUB_PROFILE_TIMEOUT_SECONDS", "8") or "8")
        except Exception:
            graphql_timeout = 8.0
        graphql_timeout = max(1.0, min(graphql_timeout, 20.0))

        emit("profile_fetch", f"Fetching GitHub profile for {login}...", {"timeout_seconds": graphql_timeout})
        t1 = now_perf()
        try:
            async def _run_graphql() -> Optional[Dict[str, Any]]:
                github = GithubClient({"token": token})
                try:
                    return await asyncio.wait_for(github.profile(login), timeout=float(graphql_timeout or 0) or None)
                finally:
                    await github.close()

            user = asyncio.run(_run_graphql())
        except Exception as exc:  # noqa: BLE001
            user = None
            emit("profile_fetch_failed", "GitHub profile fetch failed", {"error": str(exc)[:200]})
        if user:
            status = "graphql"
            emit("timing.github.profile", "GitHub profile fetched", {"duration_ms": elapsed_ms(t1)})

    if not user:
        # Degraded: provide minimal identity so UI can still render something.
        status = "degraded"
        user = {
            "id": "",
            "login": login,
            "name": login,
            "bio": "",
            "avatarUrl": "",
            "url": f"https://github.com/{login}",
            "createdAt": None,
            "issues": {"totalCount": None},
            "pullRequests": {"totalCount": None},
            "repositories": {"totalCount": None},
        }

    # Phase-2 UX: prefill the user-facing profile card ASAP.
    try:
        emit(
            "preview.github.profile",
            "GitHub profile preview ready",
            {
                "prefill_cards": [
                    {
                        "card": "profile",
                        "data": user,
                        "meta": {"partial": True, "source": "resource.github.profile", "status": status},
                    }
                ]
            },
        )
    except Exception:
        pass

    return {"user": user, "status": status}


def _has_counts(u: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(u, dict) or not u:
        return False
    for k in ("issues", "pullRequests", "repositories"):
        v = u.get(k)
        if not isinstance(v, dict) or v.get("totalCount") is None:
            return False
    return True


def _with_item_ids(items: Any) -> list[Dict[str, Any]]:
    if not isinstance(items, list):
        return []
    out: list[Dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        entry = dict(it)
        repo = entry.get("repository")
        if isinstance(repo, dict):
            url = repo.get("url")
            if url and entry.get("id") is None:
                entry["id"] = str(url)
        out.append(entry)
    return out


def _work_experience_years(created_at_str: str) -> int:
    now = datetime.now(timezone.utc)
    sign_up_at = parse_github_datetime(created_at_str)
    if sign_up_at is None:
        sign_up_at = now.replace(year=now.year - 1)
    try:
        return max(0, int(math.ceil((now - sign_up_at).days / 365)))
    except Exception:
        return 0


def fetch_github_preview(*, login: str, progress: Optional[ProgressFn] = None, user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Fast-first GitHub preview for the first screen.

    Goal: emit `card.append` for repos.top_projects ASAP (and optionally feature_project)
    without waiting for heavy/long-tail GitHub queries.
    """

    token = (os.getenv("GITHUB_TOKEN") or "").strip()
    if not token:
        raise ValueError("missing GITHUB_TOKEN")

    def emit(step: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        if progress:
            progress(step, message, data)

    try:
        years = int(os.getenv("DINQ_GITHUB_PREVIEW_PR_REPOS_YEARS", "3") or "3")
    except Exception:
        years = 3
    years = max(1, min(int(years), 10))

    try:
        timeout_seconds = float(os.getenv("DINQ_GITHUB_PREVIEW_TIMEOUT_SECONDS", "8") or "8")
    except Exception:
        timeout_seconds = 8.0
    timeout_seconds = max(1.0, min(float(timeout_seconds), 20.0))

    async def run() -> Dict[str, Any]:
        github = GithubClient({"token": token})
        try:
            user_payload: Optional[Dict[str, Any]] = user if isinstance(user, dict) else None
            user_id = str((user_payload or {}).get("id") or "").strip()

            # Ensure we have at least basic profile fields for work_experience heuristics.
            if not user_id or not _has_counts(user_payload):
                profile_timeout = min(6.0, timeout_seconds)
                emit("preview.github.profile_fetch", f"Fetching GitHub profile (preview) for {login}...", {"timeout_seconds": profile_timeout})
                t_profile = now_perf()
                try:
                    user_payload = await asyncio.wait_for(github.profile(login), timeout=profile_timeout)
                    emit("timing.github.preview.profile", "GitHub preview profile fetched", {"duration_ms": elapsed_ms(t_profile)})
                except Exception as exc:  # noqa: BLE001
                    emit("preview.github.profile_fetch_failed", "GitHub preview profile fetch failed", {"error": str(exc)[:200]})

            created_at_str = str((user_payload or {}).get("createdAt") or "")
            work_exp_years = _work_experience_years(created_at_str)
            pr_years = max(1, min(years, work_exp_years))

            t0 = time.monotonic()
            emit(
                "preview.github.top_projects_fetch",
                "Fetching GitHub top projects (preview)...",
                {"years": pr_years, "timeout_seconds": timeout_seconds},
            )

            most_starred_task = asyncio.create_task(github.most_starred_repositories(login))

            # PR repos: emit the first 2 items as soon as any year query returns,
            # then append the rest as more years finish (better first-screen UX).
            now = datetime.now(timezone.utc)
            pr_tasks: list[asyncio.Task] = []
            for i in range(1, int(pr_years) + 1):
                start = now - relativedelta(years=i)
                pr_tasks.append(asyncio.create_task(github.query(MostPullRequestRepositoriesQuery(login, start))))

            repo_map: Dict[str, Dict[str, Any]] = {}

            def _accumulate(items: Any) -> None:
                if not isinstance(items, list):
                    return
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    repo = item.get("repository") if isinstance(item.get("repository"), dict) else None
                    if not isinstance(repo, dict) or not repo:
                        continue
                    url = str(repo.get("url") or "").strip()
                    if not url:
                        continue
                    contributions = item.get("contributions") if isinstance(item.get("contributions"), dict) else {}
                    try:
                        count = int(contributions.get("totalCount") or 0)
                    except Exception:
                        count = 0
                    if url not in repo_map:
                        repo_out = dict(repo)
                        repo_out["pull_requests"] = 0
                        repo_map[url] = {"pull_requests": 0, "repository": repo_out}
                    total = int(repo_map[url].get("pull_requests") or 0) + int(count)
                    repo_map[url]["pull_requests"] = total
                    repo_obj = repo_map[url].get("repository")
                    if isinstance(repo_obj, dict):
                        repo_obj["pull_requests"] = total

            def _sorted_top_projects() -> list[Dict[str, Any]]:
                items = list(repo_map.values())
                items.sort(key=lambda x: int(x.get("pull_requests") or 0), reverse=True)
                return items[:10]

            try:
                first_timeout = float(os.getenv("DINQ_GITHUB_PREVIEW_TOP_PROJECTS_FIRST_TIMEOUT_SECONDS", "3") or "3")
            except Exception:
                first_timeout = 3.0
            first_timeout = max(0.5, min(float(first_timeout), float(timeout_seconds)))

            try:
                first_batch_size = int(os.getenv("DINQ_GITHUB_PREVIEW_TOP_PROJECTS_FIRST_BATCH_SIZE", "2") or "2")
            except Exception:
                first_batch_size = 2
            first_batch_size = max(1, min(int(first_batch_size), 10))

            pr_repos: list[Dict[str, Any]] = []
            sent_ids: set[str] = set()

            pending_tasks = set(pr_tasks)
            try:
                done, pending_tasks = await asyncio.wait(
                    pending_tasks,
                    timeout=float(first_timeout),
                    return_when=asyncio.FIRST_COMPLETED,
                )
            except Exception:
                done = set()

            for t in done:
                try:
                    _accumulate(t.result())
                except Exception:
                    pass

            first_list = _with_item_ids(_sorted_top_projects())
            first_items = first_list[:first_batch_size]
            if first_items:
                pr_repos = first_list
                sent_ids = {str(it.get("id") or "") for it in first_items if it.get("id") is not None}
                emit(
                    "preview.github.top_projects",
                    "Top projects preview ready (first batch)",
                    {
                        "append": {
                            "card": "repos",
                            "path": "top_projects",
                            "items": first_items,
                            "dedup_key": "id",
                            "partial": True,
                        }
                    },
                )

            # Wait for the rest of the years within the remaining budget.
            remaining_for_pr = max(0.0, float(timeout_seconds) - (time.monotonic() - t0))
            done2: set[asyncio.Task] = set()
            pending2: set[asyncio.Task] = set()
            if pending_tasks:
                if remaining_for_pr > 0:
                    try:
                        done2, pending2 = await asyncio.wait(pending_tasks, timeout=float(remaining_for_pr))
                    except Exception:
                        done2, pending2 = set(), pending_tasks
                else:
                    pending2 = pending_tasks

            for t in done2:
                try:
                    _accumulate(t.result())
                except Exception:
                    pass

            if pending2:
                emit(
                    "preview.github.top_projects_timeout",
                    "GitHub top projects preview timed out",
                    {"timeout_seconds": timeout_seconds, "pending_year_queries": len(pending2)},
                )
                for t in pending2:
                    try:
                        t.cancel()
                    except Exception:
                        pass

            pr_repos = _with_item_ids(_sorted_top_projects())
            remaining_items = []
            for it in pr_repos:
                if not isinstance(it, dict):
                    continue
                id_val = it.get("id")
                key = str(id_val) if id_val is not None else ""
                if key and key in sent_ids:
                    continue
                remaining_items.append(it)

            if remaining_items:
                emit(
                    "preview.github.top_projects",
                    "Top projects preview ready",
                    {
                        "append": {
                            "card": "repos",
                            "path": "top_projects",
                            "items": remaining_items,
                            "dedup_key": "id",
                            "partial": True,
                        }
                    },
                )

            feature_project = None
            remaining = max(0.0, float(timeout_seconds) - (time.monotonic() - t0))
            if remaining >= 0.5 and not most_starred_task.done():
                try:
                    most_starred = await asyncio.wait_for(most_starred_task, timeout=remaining)
                except asyncio.TimeoutError:
                    emit("preview.github.feature_project_timeout", "GitHub feature project preview timed out", {"timeout_seconds": remaining})
                    most_starred_task.cancel()
                    most_starred = []
                except Exception as exc:  # noqa: BLE001
                    emit("preview.github.feature_project_failed", "Failed to fetch feature project (preview)", {"error": str(exc)[:200]})
                    most_starred = []
                if isinstance(most_starred, list) and most_starred:
                    feature_project = most_starred[0]
            else:
                try:
                    if most_starred_task.done():
                        most_starred = most_starred_task.result()
                        if isinstance(most_starred, list) and most_starred:
                            feature_project = most_starred[0]
                except Exception:
                    pass

            out: Dict[str, Any] = {
                "user": user_payload or {"login": login},
                "feature_project": feature_project,
                "top_projects": pr_repos,
                "most_valuable_pull_request": None,
                "status": "preview",
            }
            return out
        finally:
            await github.close()

    return asyncio.run(run())


def _fetch_github_data_bundle(
    *,
    login: str,
    progress: Optional[ProgressFn] = None,
    user: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Fetch non-AI GitHub data and format it into a legacy full_report-like shape (partial).

    Optimized for fewer external calls:
      - 1 GraphQL call for user + top repos + PR candidates + contribution calendar + PR repos.
      - Activity uses contributionCalendar only (no search(...) fan-out).
    """

    token = (os.getenv("GITHUB_TOKEN") or "").strip()
    if not token:
        raise ValueError("missing GITHUB_TOKEN")

    def emit(step: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        if progress:
            progress(step, message, data)

    async def run() -> Dict[str, Any]:
        github = GithubClient({"token": token})
        try:
            try:
                # Frontend calendar view uses a 26-week window by default.
                activity_days = int(os.getenv("DINQ_GITHUB_ACTIVITY_DAYS", "182") or "182")
            except Exception:
                activity_days = 182
            activity_days = max(7, min(int(activity_days), 365))

            end = datetime.now(timezone.utc)
            start = end - timedelta(days=activity_days)

            emit("bundle_fetch", f"Fetching GitHub data bundle for {login}...", {"days": activity_days})
            t0 = now_perf()
            bundle_user = await github.bundle(login, start, end)
            emit("timing.github.bundle", "GitHub bundle fetched", {"duration_ms": elapsed_ms(t0)})
            if not isinstance(bundle_user, dict) or not bundle_user:
                raise ValueError(f'GitHub user "{login}" not found or inaccessible')

            # Keep `user` compact and compatible; stash bundle-only fields separately.
            user_payload: Dict[str, Any] = {
                "id": bundle_user.get("id"),
                "name": bundle_user.get("name") or bundle_user.get("login") or login,
                "login": bundle_user.get("login") or login,
                "createdAt": bundle_user.get("createdAt"),
                "bio": bundle_user.get("bio"),
                "avatarUrl": bundle_user.get("avatarUrl"),
                "url": bundle_user.get("url") or f"https://github.com/{login}",
                "issues": bundle_user.get("issues"),
                "pullRequests": bundle_user.get("pullRequests"),
                "repositories": bundle_user.get("repositories"),
            }

            output: Dict[str, Any] = {"user": user_payload}

            try:
                emit(
                    "preview.github.profile",
                    "GitHub profile ready",
                    {
                        "prefill_cards": [
                            {
                                "card": "profile",
                                "data": user_payload,
                                "meta": {"partial": True, "source": "resource.github.data", "bundle": True},
                            }
                        ]
                    },
                )
            except Exception:
                pass

            created_at_str = str(user_payload.get("createdAt") or "")
            work_exp = _work_experience_years(created_at_str)

            top_repos = ((bundle_user.get("topRepos") or {}) if isinstance(bundle_user.get("topRepos"), dict) else {}).get("nodes") or []
            if not isinstance(top_repos, list):
                top_repos = []

            stars_count = 0
            for repo in top_repos:
                if not isinstance(repo, dict):
                    continue
                try:
                    stars_count += int(repo.get("stargazerCount") or 0)
                except Exception:
                    continue

            output["feature_project"] = top_repos[0] if top_repos else None

            pr_block = (bundle_user.get("pullRequestsTop") or {}) if isinstance(bundle_user.get("pullRequestsTop"), dict) else {}
            pr_nodes = pr_block.get("nodes") if isinstance(pr_block.get("nodes"), list) else []
            try:
                pr_total = int(pr_block.get("totalCount") or 0)
            except Exception:
                pr_total = 0

            def estimate_pr_mutations(prs: list[Dict[str, Any]], total_count: int) -> Dict[str, Any]:
                if not prs or total_count <= 0:
                    return {"additions": 0, "deletions": 0, "languages": {}}
                total_add, total_del = 0, 0
                langs: Dict[str, int] = {}
                for pr in prs:
                    if not isinstance(pr, dict):
                        continue
                    try:
                        additions = int(pr.get("additions") or 0)
                    except Exception:
                        additions = 0
                    try:
                        deletions = int(pr.get("deletions") or 0)
                    except Exception:
                        deletions = 0
                    total_add += additions
                    total_del += deletions
                    total = additions + deletions

                    repo = pr.get("repository") if isinstance(pr.get("repository"), dict) else {}
                    edges = ((repo.get("languages") or {}) if isinstance(repo.get("languages"), dict) else {}).get("edges") or []
                    if not isinstance(edges, list) or not edges or total <= 0:
                        continue
                    size_total = 0
                    for e in edges:
                        if not isinstance(e, dict):
                            continue
                        try:
                            size_total += int(e.get("size") or 0)
                        except Exception:
                            continue
                    if size_total <= 0:
                        continue
                    for e in edges:
                        if not isinstance(e, dict):
                            continue
                        node = e.get("node") if isinstance(e.get("node"), dict) else {}
                        name = str(node.get("name") or "").strip()
                        if not name:
                            continue
                        try:
                            size = int(e.get("size") or 0)
                        except Exception:
                            size = 0
                        if size <= 0:
                            continue
                        portion = round((float(size) / float(size_total)) * float(total))
                        langs[name] = int(langs.get(name) or 0) + int(portion)

                count = len(prs)
                if count <= 0:
                    return {"additions": 0, "deletions": 0, "languages": {}}
                additions_scaled = round((float(total_add) / float(count)) * float(total_count))
                deletions_scaled = round((float(total_del) / float(count)) * float(total_count))
                for name in list(langs.keys()):
                    langs[name] = round((float(langs[name]) / float(count)) * float(total_count))
                return {"additions": int(additions_scaled), "deletions": int(deletions_scaled), "languages": langs}

            pr_payload = estimate_pr_mutations(pr_nodes, pr_total)
            output["_pull_requests"] = {"mutations": pr_payload, "nodes": pr_nodes, "totalCount": pr_total}

            additions = int(pr_payload.get("additions") or 0)
            deletions = int(pr_payload.get("deletions") or 0)
            languages = pr_payload.get("languages") if isinstance(pr_payload.get("languages"), dict) else {}
            output["code_contribution"] = {"total": additions + deletions, "languages": languages}

            contribs = (bundle_user.get("contributionsCollection") or {}) if isinstance(bundle_user.get("contributionsCollection"), dict) else {}

            # Phase-2 UX: emit repos.top_projects as early as possible from the bundle (no extra GitHub requests).
            try:
                def _pr_repo_list(raw: Any) -> list[Dict[str, Any]]:
                    if not isinstance(raw, list):
                        return []
                    return [x for x in raw if isinstance(x, dict)]

                def _has_nonzero_prs(items: list[Dict[str, Any]]) -> bool:
                    for it in items:
                        if not isinstance(it, dict):
                            continue
                        contrib = it.get("contributions") if isinstance(it.get("contributions"), dict) else {}
                        try:
                            c = int(contrib.get("totalCount") or 0)
                        except Exception:
                            c = 0
                        if c > 0:
                            return True
                    return False

                pr_repos_recent = _pr_repo_list(contribs.get("pullRequestContributionsByRepository"))
                pr_repos = pr_repos_recent

                top_projects = []
                for item in pr_repos:
                    if not isinstance(item, dict):
                        continue
                    repo = item.get("repository") if isinstance(item.get("repository"), dict) else None
                    if not isinstance(repo, dict) or not repo:
                        continue
                    contrib = item.get("contributions") if isinstance(item.get("contributions"), dict) else {}
                    try:
                        pr_count = int(contrib.get("totalCount") or 0)
                    except Exception:
                        pr_count = 0
                    repo_out = dict(repo)
                    repo_out["pull_requests"] = int(pr_count)
                    top_projects.append({"pull_requests": int(pr_count), "repository": repo_out})

                # If the recent-window PR repos are empty/zero, fall back to multi-year aggregation using
                # the existing yearly query (GitHub enforces <=1y spans for contributionsCollection).
                if not _has_nonzero_prs(pr_repos_recent):
                    try:
                        fallback_years = int(os.getenv("DINQ_GITHUB_TOP_PROJECTS_FALLBACK_YEARS", "10") or "10")
                    except Exception:
                        fallback_years = 10
                    fallback_years = max(1, min(int(fallback_years), 10))
                    pr_years = max(1, min(int(fallback_years), int(work_exp or 0) or 1))

                    now_dt = datetime.now(timezone.utc)
                    tasks = []
                    for i in range(1, int(pr_years) + 1):
                        start_year = now_dt - relativedelta(years=i)
                        tasks.append(asyncio.create_task(github.query(MostPullRequestRepositoriesQuery(login, start_year))))

                    repo_map: Dict[str, Dict[str, Any]] = {}
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for res in results:
                        if isinstance(res, Exception):
                            continue
                        if not isinstance(res, list):
                            continue
                        for item in res:
                            if not isinstance(item, dict):
                                continue
                            repo = item.get("repository") if isinstance(item.get("repository"), dict) else None
                            if not isinstance(repo, dict) or not repo:
                                continue
                            url = str(repo.get("url") or "").strip()
                            if not url:
                                continue
                            contrib = item.get("contributions") if isinstance(item.get("contributions"), dict) else {}
                            try:
                                pr_count = int(contrib.get("totalCount") or 0)
                            except Exception:
                                pr_count = 0
                            if url not in repo_map:
                                repo_out = dict(repo)
                                repo_out["pull_requests"] = 0
                                repo_map[url] = {"pull_requests": 0, "repository": repo_out}
                            total = int(repo_map[url].get("pull_requests") or 0) + int(pr_count)
                            repo_map[url]["pull_requests"] = total
                            repo_obj = repo_map[url].get("repository")
                            if isinstance(repo_obj, dict):
                                repo_obj["pull_requests"] = total

                    fallback_list = list(repo_map.values())
                    fallback_list.sort(key=lambda x: int(x.get("pull_requests") or 0), reverse=True)
                    if fallback_list:
                        top_projects = fallback_list[:10]
                top_projects.sort(key=lambda x: int(x.get("pull_requests") or 0), reverse=True)
                top_projects = _with_item_ids(top_projects)
                if top_projects:
                    emit(
                        "preview.github.top_projects",
                        "Top projects preview ready (bundle)",
                        {
                            "append": {
                                "card": "repos",
                                "path": "top_projects",
                                "items": top_projects,
                                "dedup_key": "id",
                                "partial": True,
                            }
                        },
                    )
                # If the user has no PR contribution repos, fall back to their own top repos so
                # the UI never sees an empty top_projects list.
                if not top_projects:
                    fallback = []
                    for repo in top_repos[:10]:
                        if not isinstance(repo, dict) or not repo:
                            continue
                        repo_out = dict(repo)
                        repo_out["pull_requests"] = 0
                        fallback.append({"pull_requests": 0, "repository": repo_out})
                    fallback = _with_item_ids(fallback)
                    top_projects = fallback or top_projects
                output["top_projects"] = top_projects
            except Exception:
                output["top_projects"] = []

            calendar = (contribs.get("contributionCalendar") or {}) if isinstance(contribs.get("contributionCalendar"), dict) else {}
            weeks = calendar.get("weeks") if isinstance(calendar.get("weeks"), list) else []

            activity: Dict[str, Any] = {}
            active_days = 0
            for week in weeks:
                if not isinstance(week, dict):
                    continue
                days = week.get("contributionDays") if isinstance(week.get("contributionDays"), list) else []
                for day in days:
                    if not isinstance(day, dict):
                        continue
                    date = str(day.get("date") or "").strip()
                    if not date:
                        continue
                    try:
                        c = int(day.get("contributionCount") or 0)
                    except Exception:
                        c = 0
                    activity[date] = {"pull_requests": 0, "issues": 0, "comments": 0, "contributions": int(c)}
                    if c > 0:
                        active_days += 1
            output["activity"] = activity

            output["overview"] = {
                "work_experience": work_exp,
                "stars": stars_count,
                "issues": (user_payload.get("issues") or {}).get("totalCount"),
                "pull_requests": (user_payload.get("pullRequests") or {}).get("totalCount"),
                "repositories": (user_payload.get("repositories") or {}).get("totalCount"),
                "additions": additions,
                "deletions": deletions,
                "active_days": active_days,
            }

            # Keep legacy key (deterministic; no random output).
            output["description"] = f"GitHub profile summary for {login}."
            return output
        finally:
            await github.close()

    return asyncio.run(run())


def fetch_github_data(
    *,
    login: str,
    progress: Optional[ProgressFn] = None,
    user: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Fetch non-AI GitHub data (upstream-aligned).

    This matches the upstream `GitHubAnalyzer.analyze` non-AI computation so the downstream
    AI prompts receive the same input shape/metrics.
    """

    token = (os.getenv("GITHUB_TOKEN") or "").strip()
    if not token:
        raise ValueError("missing GITHUB_TOKEN")

    def emit(step: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        if progress:
            progress(step, message, data)

    async def run() -> Dict[str, Any]:
        github = GithubClient({"token": token})
        try:
            emit("profile_fetch", f"Fetching GitHub profile for {login}...", None)
            t_profile = now_perf()
            user_payload: Optional[Dict[str, Any]] = None
            try:
                user_payload = await github.profile(login)
            except Exception as exc:  # noqa: BLE001
                emit("profile_fetch_failed", "GitHub profile fetch failed", {"error": str(exc)[:200]})
                user_payload = None
            emit("timing.github.profile", "GitHub profile fetched", {"duration_ms": elapsed_ms(t_profile)})

            if not isinstance(user_payload, dict) or not user_payload:
                user_payload = user if isinstance(user, dict) else None

            if not isinstance(user_payload, dict) or not user_payload:
                raise ValueError(f'GitHub user "{login}" not found or inaccessible')

            try:
                emit(
                    "preview.github.profile",
                    "GitHub profile ready",
                    {
                        "prefill_cards": [
                            {
                                "card": "profile",
                                "data": user_payload,
                                "meta": {"partial": True, "source": "resource.github.data"},
                            }
                        ]
                    },
                )
            except Exception:
                pass

            created_at_str = str(user_payload.get("createdAt") or "")
            work_exp = _work_experience_years(created_at_str)

            now_dt = datetime.now(timezone.utc)
            sign_up_at = parse_github_datetime(created_at_str)
            if sign_up_at is None:
                try:
                    sign_up_at = now_dt.replace(year=now_dt.year - 1)
                except Exception:
                    sign_up_at = now_dt - timedelta(days=365)

            async def safe_github_call(coro: Any, name: str, default_value: Any) -> Any:
                try:
                    return await coro
                except Exception as exc:  # noqa: BLE001
                    emit(f"github.{name}_failed", f"GitHub {name} fetch failed", {"error": str(exc)[:200]})
                    return default_value

            pr_default = {"mutations": {"additions": 0, "deletions": 0, "languages": {}}, "nodes": []}
            mutations_default = {"additions": 0, "deletions": 0, "languages": {}}

            user_id = str(user_payload.get("id") or "").strip()

            async def _mutations_or_default() -> Dict[str, Any]:
                if not user_id:
                    return dict(mutations_default)
                out = await safe_github_call(github.mutations(login, user_id), "mutations", mutations_default)
                return out if isinstance(out, dict) else dict(mutations_default)

            pull_requests_data, mutations, activity, all_time_activity, most_starred_repositories, most_pull_request_repositories = await asyncio.gather(
                safe_github_call(github.pull_requests(login), "pull_requests", pr_default),
                _mutations_or_default(),
                safe_github_call(github.activity(login=login), "activity", {}),
                safe_github_call(github.activity(login=login, start_date=sign_up_at), "all_time_activity", {}),
                safe_github_call(github.most_starred_repositories(login), "most_starred_repositories", []),
                safe_github_call(
                    github.most_pull_request_repositories(login, min(10, int(work_exp or 0) or 0)),
                    "most_pull_request_repositories",
                    [],
                ),
            )

            pull_requests_data = pull_requests_data if isinstance(pull_requests_data, dict) else dict(pr_default)
            mutations = mutations if isinstance(mutations, dict) else dict(mutations_default)
            activity = activity if isinstance(activity, dict) else {}
            all_time_activity = all_time_activity if isinstance(all_time_activity, dict) else {}
            most_starred_repositories = most_starred_repositories if isinstance(most_starred_repositories, list) else []
            most_pull_request_repositories = most_pull_request_repositories if isinstance(most_pull_request_repositories, list) else []

            additions = int(mutations.get("additions") or 0) + int((pull_requests_data.get("mutations") or {}).get("additions") or 0)
            deletions = int(mutations.get("deletions") or 0) + int((pull_requests_data.get("mutations") or {}).get("deletions") or 0)

            languages = mutations.get("languages") if isinstance(mutations.get("languages"), dict) else {}
            pr_langs = (pull_requests_data.get("mutations") or {}).get("languages") if isinstance((pull_requests_data.get("mutations") or {}).get("languages"), dict) else {}
            for name, value in pr_langs.items():
                if name not in languages:
                    languages[name] = 0
                try:
                    languages[name] += int(value or 0)
                except Exception:
                    continue

            stars_count = 0
            for repository in most_starred_repositories:
                if not isinstance(repository, dict):
                    continue
                try:
                    stars_count += int(repository.get("stargazerCount") or 0)
                except Exception:
                    continue

            active_days = 0
            for _, day_data in all_time_activity.items():
                if not isinstance(day_data, dict):
                    continue
                if (
                    int(day_data.get("pull_requests") or 0) > 0
                    or int(day_data.get("issues") or 0) > 0
                    or int(day_data.get("comments") or 0) > 0
                    or int(day_data.get("contributions") or 0) > 0
                ):
                    active_days += 1

            overview = {
                "work_experience": work_exp,
                "stars": stars_count,
                "issues": (user_payload.get("issues") or {}).get("totalCount") if isinstance(user_payload.get("issues"), dict) else None,
                "pull_requests": (user_payload.get("pullRequests") or {}).get("totalCount") if isinstance(user_payload.get("pullRequests"), dict) else None,
                "repositories": (user_payload.get("repositories") or {}).get("totalCount") if isinstance(user_payload.get("repositories"), dict) else None,
                "additions": additions,
                "deletions": deletions,
                "active_days": active_days,
            }

            feature_project = None
            if most_starred_repositories and isinstance(most_starred_repositories[0], dict):
                most_starred_repository = most_starred_repositories[0]
                feature_project = dict(most_starred_repository)
                name_with_owner = str(most_starred_repository.get("nameWithOwner") or "").strip()
                if name_with_owner:
                    try:
                        from server.api.github_analyzer_api import get_analyzer  # local import (heavy)

                        analyzer = get_analyzer()
                        extra = await asyncio.to_thread(analyzer.fetch_repository_extra, name_with_owner)
                        if isinstance(extra, dict) and extra:
                            feature_project = dict(extra)
                            feature_project.update(most_starred_repository)
                    except Exception:
                        pass

            pr_nodes = pull_requests_data.get("nodes") if isinstance(pull_requests_data.get("nodes"), list) else []
            pr_total = (user_payload.get("pullRequests") or {}).get("totalCount") if isinstance(user_payload.get("pullRequests"), dict) else None

            return {
                "user": user_payload,
                "description": random.choices(DESC_PRESETS)[0] if isinstance(DESC_PRESETS, list) and DESC_PRESETS else "",
                "overview": overview,
                "activity": activity,
                "feature_project": feature_project,
                "code_contribution": {"total": additions + deletions, "languages": languages},
                "top_projects": most_pull_request_repositories,
                "_pull_requests": {"mutations": pull_requests_data.get("mutations"), "nodes": pr_nodes, "totalCount": pr_total},
            }
        finally:
            await github.close()

    return asyncio.run(run())


def run_github_ai(*, login: str, data: Dict[str, Any], progress: Optional[ProgressFn] = None) -> Dict[str, Any]:
    """
    Run AI-heavy GitHub enrichments and return a partial full_report-shaped dict.

    Uses the existing GitHubAnalyzer implementation to keep output shape compatible.
    """

    def emit(step: str, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        if progress:
            progress(step, message, extra)

    from server.api.github_analyzer_api import get_analyzer  # local import (heavy)

    analyzer = get_analyzer()
    feature_project = (data or {}).get("feature_project")
    pr_nodes = ((data or {}).get("_pull_requests") or {}).get("nodes") or []

    emit("ai_start", "Running GitHub AI analysis...", None)

    async def run() -> Dict[str, Any]:
        # Basic AI tasks
        user_tags, repo_tags, most_pr = await asyncio.gather(
            analyzer.safe_ai_call(analyzer.ai_user_tags(login), "user_tags", []),
            analyzer.safe_ai_call(analyzer.ai_repository_tags(feature_project), "repository_tags", []),
            analyzer.safe_ai_call(analyzer.ai_most_valuable_pull_request(pr_nodes), "most_valuable_pr", None),
        )

        # Advanced AI tasks (valuation, role model, roast)
        valuation, role_model, roast = await asyncio.gather(
            analyzer.safe_ai_call(analyzer.ai_valuation_and_level(data), "valuation_and_level", {"level": "Unknown", "salary_range": "Unknown"}),
            analyzer.safe_ai_call(analyzer.ai_role_model(data), "role_model", {"name": "Unknown", "similarity_score": 0}),
            analyzer.safe_ai_call(analyzer.ai_roast(data), "roast", "No roast available"),
        )

        out: Dict[str, Any] = {
            "user": {"tags": user_tags or []},
            "feature_project": {"tags": repo_tags or []},
            "most_valuable_pull_request": most_pr,
            "valuation_and_level": valuation,
            "role_model": role_model,
            "roast": roast,
        }
        return out

    return asyncio.run(run())


def _run_github_enrich_bundle_legacy(
    *,
    login: str,
    base: Dict[str, Any],
    progress: Optional[ProgressFn] = None,
    mode: str = "fast",
) -> Dict[str, Any]:
    """
    GitHub enrichment aligned to upstream `GitHubAnalyzer` outputs.

    Output is shaped like a partial full_report so:
      - `extract_card_payload("github", payload, "repos"/"role_model"/"roast"/"summary")` works.
    """

    def emit(step: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        if progress:
            progress(step, message, data)

    def pr_candidates(pr_nodes: Any, *, max_candidates: int) -> list[Dict[str, Any]]:
        if not isinstance(pr_nodes, list):
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
            repo = pr.get("repository") if isinstance(pr.get("repository"), dict) else {}
            repo_name = str(repo.get("nameWithOwner") or "").strip()
            if not repo_name:
                repo_name = str(repo.get("name") or "").strip()
            out.append(
                {
                    "repository": repo_name,
                    "url": url,
                    "title": title,
                    "additions": additions,
                    "deletions": deletions,
                    "comment_rank": int(idx),
                }
            )

        if not out:
            return []

        def score(p: Dict[str, Any]) -> tuple[int, int]:
            impact = int(p.get("additions") or 0) + int(p.get("deletions") or 0)
            comment_rank = int(p.get("comment_rank") or 0)
            return (impact, -comment_rank)

        k = max(1, min(int(max_candidates or 1), 50))
        selected = sorted(out, key=score, reverse=True)[:k]
        selected.sort(key=lambda p: int(p.get("comment_rank") or 0))
        return selected

    def best_pr_fallback(prs: list[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
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

    def _extract_login_from_github(value: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        lowered = raw.lower()
        if lowered.startswith("http://") or lowered.startswith("https://"):
            # https://github.com/<login>[/...]
            parts = lowered.split("github.com/", 1)
            if len(parts) == 2:
                tail = parts[1].split("?", 1)[0].split("#", 1)[0].strip("/")
                if tail:
                    return tail.split("/", 1)[0].strip()
        # Sometimes we store raw login in `github`.
        return raw.strip().lstrip("@").split("/", 1)[0].strip()

    user = base.get("user") if isinstance(base.get("user"), dict) else {}
    overview = base.get("overview") if isinstance(base.get("overview"), dict) else {}
    feature_project = base.get("feature_project") if isinstance(base.get("feature_project"), dict) else {}
    top_projects = base.get("top_projects") if isinstance(base.get("top_projects"), list) else []
    code = base.get("code_contribution") if isinstance(base.get("code_contribution"), dict) else {}

    fast_mode = str(mode or "fast").strip().lower() != "background"

    def _bool_env(name: str, *, default: bool = False) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return bool(default)
        return str(raw).strip().lower() in ("1", "true", "yes", "on")

    try:
        if fast_mode:
            raw = os.getenv("DINQ_GITHUB_ENRICH_FAST_TIMEOUT_SECONDS") or os.getenv("DINQ_GITHUB_ENRICH_TIMEOUT_SECONDS") or "15"
            timeout_seconds = float(raw)
        else:
            timeout_seconds = float(os.getenv("DINQ_GITHUB_ENRICH_BACKGROUND_TIMEOUT_SECONDS", "60") or "60")
    except Exception:
        timeout_seconds = 10.0 if fast_mode else 60.0
    timeout_seconds = max(3.0, min(float(timeout_seconds), 180.0))

    try:
        if fast_mode:
            max_candidates = int(os.getenv("DINQ_GITHUB_ENRICH_PR_MAX_CANDIDATES_FAST", "10") or "10")
        else:
            max_candidates = int(os.getenv("DINQ_GITHUB_ENRICH_PR_MAX_CANDIDATES_BG", "30") or "30")
    except Exception:
        max_candidates = 10 if fast_mode else 30
    max_candidates = max(5, min(int(max_candidates), 50))

    pr_nodes = ((base.get("_pull_requests") or {}) if isinstance(base.get("_pull_requests"), dict) else {}).get("nodes") or []
    candidates = pr_candidates(pr_nodes, max_candidates=max_candidates)
    fallback_pr = best_pr_fallback(candidates)

    pr_total = 0
    prs = user.get("pullRequests") if isinstance(user.get("pullRequests"), dict) else {}
    try:
        pr_total = int(prs.get("totalCount") or 0)
    except Exception:
        pr_total = 0

    from server.api.github_analyzer_api import get_analyzer

    analyzer = get_analyzer()

    # Keep LLM input small/stable: PR node list is huge.
    ai_input: Dict[str, Any] = dict(base or {})
    ai_input.pop("_pull_requests", None)

    # Run upstream analyzer calls (parallel).
    try:
        per_task_timeout = max(3.0, min(float(timeout_seconds), 60.0))
    except Exception:
        per_task_timeout = 10.0 if fast_mode else 60.0

    emit(
        "ai_enrich",
        "Running GitHub AI analysis (upstream-aligned)...",
        {
            "mode": ("fast" if fast_mode else "background"),
            "timeout_seconds": timeout_seconds,
            "per_task_timeout_seconds": per_task_timeout,
            "pr_candidates": len(candidates),
        },
    )

    async def run() -> Dict[str, Any]:
        user_tags_coro = analyzer.safe_ai_call(asyncio.wait_for(analyzer.ai_user_tags(login), timeout=per_task_timeout), "user_tags", [])
        repo_tags_coro = analyzer.safe_ai_call(asyncio.wait_for(analyzer.ai_repository_tags(feature_project), timeout=per_task_timeout), "repository_tags", [])
        most_pr_coro = analyzer.safe_ai_call(asyncio.wait_for(analyzer.ai_most_valuable_pull_request(candidates), timeout=per_task_timeout), "most_valuable_pr", {})
        valuation_coro = analyzer.safe_ai_call(asyncio.wait_for(analyzer.ai_valuation_and_level(ai_input), timeout=per_task_timeout), "valuation_and_level", {})
        role_model_coro = analyzer.safe_ai_call(asyncio.wait_for(analyzer.ai_role_model(ai_input), timeout=per_task_timeout), "role_model", {})
        roast_coro = analyzer.safe_ai_call(asyncio.wait_for(analyzer.ai_roast(ai_input), timeout=per_task_timeout), "roast", "")

        user_tags, repo_tags, most_pr, valuation, role_model, roast = await asyncio.gather(
            user_tags_coro,
            repo_tags_coro,
            most_pr_coro,
            valuation_coro,
            role_model_coro,
            roast_coro,
        )

        return {
            "user_tags": user_tags,
            "repo_tags": repo_tags,
            "most_pr": most_pr,
            "valuation": valuation,
            "role_model": role_model,
            "roast": roast,
        }

    results: Dict[str, Any] = {}
    try:
        results = asyncio.run(run())
    except Exception:
        results = {}

    # Normalize + harden (avoid retries due to missing fields).
    desc = str(ai_input.get("description") or "").strip()
    if not desc:
        try:
            stars = int((overview or {}).get("stars") or 0)
        except Exception:
            stars = 0
        years = overview.get("work_experience")
        ytxt = f"{years}y exp" if isinstance(years, int) and years > 0 else "experienced"
        if pr_total > 0 or stars > 0:
            desc = f"{login}: {ytxt}, {pr_total} PRs, {stars} stars."
        else:
            desc = f"{login}: GitHub profile summary."

    # Tags
    tags: list[str] = []
    tags_raw = results.get("user_tags")
    if isinstance(tags_raw, list):
        for t in tags_raw:
            if isinstance(t, str) and t.strip():
                tags.append(t.strip()[:60])
    tags = tags[:8]

    repo_tags: list[str] = []
    repo_tags_raw = results.get("repo_tags")
    if isinstance(repo_tags_raw, list):
        for t in repo_tags_raw:
            if isinstance(t, str) and t.strip():
                repo_tags.append(t.strip()[:60])
    repo_tags = repo_tags[:8]

    user_login = str(user.get("login") or login).strip()
    user_login_l = user_login.lower()
    user_url_l = str(user.get("url") or f"https://github.com/{user_login_l}").strip().lower().rstrip("/")

    # Valuation (upstream schema): level + numeric salary_range + industry_ranking + growth_potential + reasoning.
    # IMPORTANT: do not fabricate level/salary defaults; mark unavailable when missing.
    valuation = results.get("valuation") if isinstance(results.get("valuation"), dict) else {}
    v_meta = valuation.get("_meta") if isinstance(valuation.get("_meta"), dict) else {}

    level = _coerce_level(valuation.get("level"))
    if level:
        valuation["level"] = level
    else:
        valuation["level"] = ""

    salary_range = valuation.get("salary_range")
    normalized_salary: list[Optional[int]] = [None, None]
    if isinstance(salary_range, list) and len(salary_range) == 2:
        try:
            a = int(salary_range[0]) if salary_range[0] is not None and not isinstance(salary_range[0], bool) else None
        except Exception:
            a = None
        try:
            b = int(salary_range[1]) if salary_range[1] is not None and not isinstance(salary_range[1], bool) else None
        except Exception:
            b = None
        normalized_salary = [a, b]
    valuation["salary_range"] = normalized_salary

    industry_ranking = _coerce_industry_ranking(valuation.get("industry_ranking"))
    valuation["industry_ranking"] = industry_ranking

    growth = str(valuation.get("growth_potential") or "").strip()
    valuation["growth_potential"] = growth

    reasoning = str(valuation.get("reasoning") or "").strip()
    valuation["reasoning"] = reasoning

    missing: list[str] = []
    if not str(valuation.get("level") or "").strip():
        missing.append("level")
    if not (isinstance(valuation.get("salary_range"), list) and len(valuation.get("salary_range")) == 2 and any(v is not None for v in valuation.get("salary_range"))):
        missing.append("salary_range")
    if valuation.get("industry_ranking") is None:
        missing.append("industry_ranking")
    if not str(valuation.get("growth_potential") or "").strip():
        missing.append("growth_potential")
    if not str(valuation.get("reasoning") or "").strip():
        missing.append("reasoning")
    if missing:
        meta_out = dict(v_meta) if isinstance(v_meta, dict) else {}
        meta_out.update({"fallback": True, "code": "unavailable", "preserve_empty": True, "missing": missing})
        valuation["_meta"] = meta_out

    # Role model: prefer LLM output; fallback to a deterministic best-match from dev_pioneers_data (never self).
    role_model = results.get("role_model") if isinstance(results.get("role_model"), dict) else {}
    name = str(role_model.get("name") or "").strip()
    gh = str(role_model.get("github") or "").strip()
    is_self = False
    if gh:
        rm_login_l = _extract_login_from_github(gh).lower()
        if rm_login_l and rm_login_l == user_login_l:
            is_self = True
        if str(gh).strip().lower().rstrip("/") == user_url_l:
            is_self = True
        if str(gh).strip().lower() == user_login_l:
            is_self = True
    if is_self:
        # Some users are included in the pioneers dataset (e.g., asim-shrestha). Never recommend self.
        role_model = {}
        name = ""
        gh = ""

    if not name or not gh:
        pioneers = getattr(analyzer, "dev_pioneers_data", None)
        if isinstance(pioneers, list) and pioneers:
            langs = []
            raw_langs = code.get("languages") if isinstance(code.get("languages"), dict) else {}
            if isinstance(raw_langs, dict):
                for k in raw_langs.keys():
                    if isinstance(k, str) and k.strip():
                        langs.append(k.strip())
            wanted = " ".join(tags + repo_tags + langs).lower()

            def _tokenize(text: str) -> set[str]:
                return {w for w in re.split(r"[^a-z0-9]+", str(text or "").lower()) if w}

            def _score(p: Any) -> float:
                if not isinstance(p, dict):
                    return 0.0
                gh_login = _extract_login_from_github(p.get("github")).lower()
                if gh_login and gh_login == user_login_l:
                    return -1.0

                area = str(p.get("area") or "")
                famous_work = str(p.get("famous_work") or "")
                company = str(p.get("Company") or "")
                job = str(p.get("Job") or "")
                hay = " ".join([area, famous_work, company, job]).lower()
                if not hay or not wanted:
                    return 0.0
                wt = _tokenize(wanted)
                at = _tokenize(hay)
                if not wt or not at:
                    return 0.0
                return float(len(wt & at)) / float(len(wt | at))

            scored = [(p, _score(p)) for p in pioneers]
            scored = [(p, s) for p, s in scored if s >= 0.0]
            best = max(scored, key=lambda x: x[1])[0] if scored else max(pioneers, key=_score)
            best_score = _score(best)
            role_model = {
                "name": best.get("name") or "Role model",
                "github": best.get("github") or "",
                "similarity_score": float(role_model.get("similarity_score") or best_score or 0.0),
                "reason": role_model.get("reason") or f"Matched by focus area overlap: {best.get('area') or 'N/A'}.",
                "achievement": role_model.get("achievement") or best.get("famous_work") or "",
            }
        else:
            role_model = {
                "name": str(user.get("name") or user_login or login).strip() or login,
                "github": f"https://github.com/{user_login_l}" if user_login_l else f"https://github.com/{str(login or '').strip()}",
                "similarity_score": 1.0,
                "reason": "Role model unavailable (no pioneers dataset); using self as fallback.",
                "achievement": "",
                "_meta": {"fallback": True, "code": "unavailable", "preserve_empty": True, "missing": ["pioneers_dataset"]},
            }

    # Roast
    roast = str(results.get("roast") or "").strip()
    if not roast:
        roast = "Your GitHub looks like a quiet powerhouse—shipping value without making too much noise."

    # MVP PR
    mvp = results.get("most_pr") if isinstance(results.get("most_pr"), dict) else None
    url = str(mvp.get("url") or "").strip() if isinstance(mvp, dict) else ""
    title = str(mvp.get("title") or "").strip() if isinstance(mvp, dict) else ""
    if not url or not title:
        mvp = fallback_pr
    if pr_total > 0 and not mvp:
        mvp = {
            "repository": "",
            "url": "",
            "title": "",
            "additions": 0,
            "deletions": 0,
            "reason": "Most valuable pull request unavailable (missing PR data or temporary API issues).",
            "impact": "Unavailable",
        }

    # Merge tags into the report-shaped output.
    out_user: Any = dict(user or {}) if isinstance(user, dict) else user
    if isinstance(out_user, dict) and tags:
        out_user["tags"] = tags

    feature_out: Any = dict(feature_project or {}) if isinstance(feature_project, dict) else feature_project
    if isinstance(feature_out, dict) and repo_tags:
        feature_out["tags"] = repo_tags

    llm_status = "ok"
    if not isinstance(role_model, dict) or not str(role_model.get("name") or "").strip():
        llm_status = "partial"
    if not isinstance(valuation, dict) or not str(valuation.get("level") or "").strip():
        llm_status = "partial"

    out: Dict[str, Any] = {
        "user": out_user,
        "feature_project": feature_out,
        "top_projects": top_projects,
        "most_valuable_pull_request": mvp,
        "valuation_and_level": valuation,
        "role_model": role_model,
        "roast": roast,
        "description": desc,
        "_meta": {"llm_status": llm_status, "mode": ("fast" if fast_mode else "background"), "timeout_seconds": timeout_seconds},
    }
    return out


def run_github_enrich_bundle(
    *,
    login: str,
    base: Dict[str, Any],
    progress: Optional[ProgressFn] = None,
    mode: str = "fast",
) -> Dict[str, Any]:
    """
    GitHub AI enrichment (upstream-aligned).

    Preserve the upstream sequencing:
      1) user_tags + repository_tags + most_valuable_pull_request
      2) valuation_and_level + role_model + roast (fed with step-1 results)
    """

    def emit(step: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        if progress:
            progress(step, message, data)

    from server.api.github_analyzer_api import get_analyzer  # local import (heavy)

    analyzer = get_analyzer()
    output: Dict[str, Any] = dict(base or {})
    user_payload = output.get("user") if isinstance(output.get("user"), dict) else {}
    feature_project = output.get("feature_project") if isinstance(output.get("feature_project"), dict) else None
    pr_nodes = ((output.get("_pull_requests") or {}) if isinstance(output.get("_pull_requests"), dict) else {}).get("nodes") or []
    if not isinstance(pr_nodes, list):
        pr_nodes = []

    def _extract_login(value: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        lowered = raw.lower().strip()
        if lowered.startswith("http://") or lowered.startswith("https://"):
            parts = lowered.split("github.com/", 1)
            if len(parts) == 2:
                tail = parts[1].split("?", 1)[0].split("#", 1)[0].strip("/")
                if tail:
                    return tail.split("/", 1)[0].strip()
        return raw.lstrip("@").split("/", 1)[0].strip()

    async def run() -> Dict[str, Any]:
        emit("ai_github_step1", "Generating GitHub tags and best PR...", {"mode": str(mode or "fast")})
        user_tags, repo_tags, most_pr = await asyncio.gather(
            analyzer.safe_ai_call(analyzer.ai_user_tags(login), "user_tags", []),
            analyzer.safe_ai_call(analyzer.ai_repository_tags(feature_project), "repository_tags", []),
            analyzer.safe_ai_call(analyzer.ai_most_valuable_pull_request(pr_nodes), "most_valuable_pr", None),
        )

        # Upstream behavior: treat empty/invalid dict as missing (None).
        if isinstance(most_pr, dict):
            url = str(most_pr.get("url") or "").strip()
            title = str(most_pr.get("title") or "").strip()
            if not url or not title:
                most_pr = None
        elif most_pr is not None:
            most_pr = None

        merged: Dict[str, Any] = dict(output)
        if isinstance(user_payload, dict):
            u = dict(user_payload)
            u["tags"] = user_tags if isinstance(user_tags, list) else []
            merged["user"] = u
        if isinstance(feature_project, dict) and feature_project:
            fp = dict(feature_project)
            fp["tags"] = repo_tags if isinstance(repo_tags, list) else []
            merged["feature_project"] = fp
        merged["most_valuable_pull_request"] = most_pr

        # Ensure role model never suggests the user themselves (e.g. the user appears in dev_pioneers.csv).
        original_pioneers = getattr(analyzer, "dev_pioneers_data", None)
        login_l = str(login or "").strip().lower()
        if isinstance(original_pioneers, list) and login_l:
            filtered = []
            for p in original_pioneers:
                if not isinstance(p, dict):
                    continue
                if _extract_login(p.get("github")).lower() == login_l:
                    continue
                filtered.append(p)
            if filtered and len(filtered) != len(original_pioneers):
                analyzer.dev_pioneers_data = filtered

        try:
            emit("ai_github_step2", "Generating valuation, role model, and roast...", {"mode": str(mode or "fast")})
            valuation, role_model, roast = await asyncio.gather(
                analyzer.safe_ai_call(
                    analyzer.ai_valuation_and_level(merged),
                    "valuation_and_level",
                    {"level": "Unknown", "salary_range": "Unknown"},
                ),
                analyzer.safe_ai_call(
                    analyzer.ai_role_model(merged),
                    "role_model",
                    {"name": "Unknown", "similarity_score": 0},
                ),
                analyzer.safe_ai_call(analyzer.ai_roast(merged), "roast", "No roast available"),
            )
        finally:
            if isinstance(original_pioneers, list):
                analyzer.dev_pioneers_data = original_pioneers

        merged["valuation_and_level"] = valuation
        merged["role_model"] = role_model
        merged["roast"] = roast
        return ensure_meta(merged, source="github_enrich", preserve_empty=True)

    try:
        return asyncio.run(run())
    except Exception:
        # Best-effort fallback: keep old logic available if something unexpected breaks.
        try:
            return _run_github_enrich_bundle_legacy(login=login, base=base, progress=progress, mode=mode)
        except Exception:
            return ensure_meta(dict(base or {}), source="github_enrich_fallback", fallback=True)


def refresh_github_enrich_cache(
    *,
    user_id: str,
    subject_key: str,
    login: str,
    base: Dict[str, Any],
    options: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Background refresh for GitHub enrich bundle.

    This is intentionally NOT tied to the original job's job_cards lifecycle.
    It writes refreshed payloads into cross-job caches so the next request can hit.
    """

    from server.analyze.cache_policy import cache_ttl_seconds, compute_options_hash, get_pipeline_version, is_cacheable_subject
    from server.analyze.subject import resolve_subject_key
    from server.tasks.analysis_cache_store import AnalysisCacheStore

    src = "github"
    sk = str(subject_key or "").strip() or resolve_subject_key(src, {"content": login})
    if not sk or not is_cacheable_subject(source=src, subject_key=sk):
        return

    opts = options or {}
    pipeline_version = get_pipeline_version(src)
    options_hash = compute_options_hash(opts)
    ttl_seconds = cache_ttl_seconds(src)

    cache_store = AnalysisCacheStore()
    subject = cache_store.get_or_create_subject(source=src, subject_key=sk, canonical_input={"content": str(login or "")})

    refresh_owner = cache_store.try_begin_refresh_run(
        subject_id=int(subject.id),
        pipeline_version=pipeline_version,
        options_hash=options_hash,
        fingerprint=None,
        meta={"cache": "bg_refresh", "kind": "github_enrich_bundle", "user_id": str(user_id or "")},
    )
    if not refresh_owner:
        return

    enrich = run_github_enrich_bundle(login=str(login), base=base, progress=None, mode="background") or {}
    meta = enrich.get("_meta") if isinstance(enrich, dict) else {}
    llm_status = (meta.get("llm_status") if isinstance(meta, dict) else None) or "unknown"
    if not isinstance(enrich, dict) or llm_status != "ok":
        cache_store.fail_refresh_run(
            subject_id=int(subject.id),
            pipeline_version=pipeline_version,
            options_hash=options_hash,
            reason=f"github_enrich_bundle_{llm_status}",
            meta={"cache": "bg_refresh", "kind": "github_enrich_bundle", "llm_status": llm_status},
        )
        return

    # Build a compact full_report shape compatible with extract_card_payload(source="github", ...).
    full_report: Dict[str, Any] = dict(base or {})
    full_report.pop("_pull_requests", None)

    for k in (
        "feature_project",
        "top_projects",
        "most_valuable_pull_request",
        "valuation_and_level",
        "role_model",
        "roast",
        "description",
    ):
        if enrich.get(k) is not None:
            full_report[k] = enrich.get(k)

    # Save a reusable artifact for the enrich bundle itself (optional), and also update the full_report cache.
    try:
        cache_store.save_cached_artifact(
            source=src,
            subject=subject,
            pipeline_version=pipeline_version,
            options_hash=options_hash,
            kind="resource.github.enrich",
            payload=enrich,
            ttl_seconds=ttl_seconds,
            meta={"cache": "bg_refresh", "kind": "resource.github.enrich"},
        )
    except Exception:
        pass

    cache_store.save_full_report(
        source=src,
        subject=subject,
        pipeline_version=pipeline_version,
        options_hash=options_hash,
        fingerprint=None,
        payload=full_report,
        ttl_seconds=ttl_seconds,
        meta={"cache": "bg_refresh", "kind": "full_report", "reason": "github_enrich_bundle"},
    )
