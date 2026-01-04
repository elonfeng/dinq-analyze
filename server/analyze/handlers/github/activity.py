"""GitHub activity card handler."""
from __future__ import annotations

from typing import Any, Dict, Optional

from server.analyze.handlers.base import CardHandler, CardResult, ExecutionContext


class GitHubActivityHandler(CardHandler):
    """
    Handle the 'activity' card for GitHub.
    
    Dependencies: resource.github.data
    
    Output schema (frontend contract, see docs/frontend/ANALYZE_CARDS.md):
      - overview: aggregated numbers (work_experience/stars/issues/pull_requests/...)
      - activity: date -> { pull_requests/issues/comments/contributions }
      - code_contribution: { total, languages }
    """
    
    source = "github"
    card_type = "activity"
    
    def execute(self, ctx: ExecutionContext) -> CardResult:
        """Extract activity stats from resource.github.data artifact."""
        data = ctx.get_artifact("resource.github.data", {})
        if not isinstance(data, dict):
            data = {}

        overview = data.get("overview")
        if not isinstance(overview, dict):
            overview = {}

        raw_activity = data.get("activity")
        if not isinstance(raw_activity, dict):
            raw_activity = {}

        # Frontend expects: Record<date, {pull_requests/issues/comments/contributions}>
        activity: Dict[str, Dict[str, int]] = {}
        for day, stats in raw_activity.items():
            day_key = str(day or "").strip()
            if not day_key:
                continue
            if not isinstance(stats, dict):
                # Never emit null here; null will crash clients doing `.contributions`.
                activity[day_key] = {}
                continue

            def _as_int(value: Any) -> int:
                try:
                    if value is None or isinstance(value, bool):
                        return 0
                    return int(value)
                except Exception:
                    return 0

            activity[day_key] = {
                "pull_requests": _as_int(stats.get("pull_requests")),
                "issues": _as_int(stats.get("issues")),
                "comments": _as_int(stats.get("comments")),
                "contributions": _as_int(stats.get("contributions")),
            }

        code_contribution = data.get("code_contribution")
        if not isinstance(code_contribution, dict):
            code_contribution = {}

        return CardResult(data={"overview": dict(overview), "activity": activity, "code_contribution": code_contribution})
    
    def validate(self, data: Dict[str, Any], ctx: ExecutionContext) -> bool:
        """Validate activity has at least one non-empty section."""
        if not isinstance(data, dict):
            return False
        overview = data.get("overview")
        activity = data.get("activity")
        code_contribution = data.get("code_contribution")

        if isinstance(overview, dict) and any(v is not None for v in overview.values()):
            return True
        if isinstance(activity, dict) and bool(activity):
            return True
        if isinstance(code_contribution, dict) and any(v is not None for v in code_contribution.values()):
            return True
        return False
    
    def fallback(self, ctx: ExecutionContext, error: Optional[Exception] = None) -> CardResult:
        """Generate fallback activity (no fabricated metrics)."""
        return CardResult(
            data={
                "overview": {},
                "activity": {},
                "code_contribution": {},
            },
            is_fallback=True,
            meta={"code": "activity_unavailable", "preserve_empty": True}
        )
