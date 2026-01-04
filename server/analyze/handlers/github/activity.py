"""GitHub activity card handler."""
from __future__ import annotations

from typing import Any, Dict, Optional

from server.analyze.handlers.base import CardHandler, CardResult, ExecutionContext


class GitHubActivityHandler(CardHandler):
    """
    Handle the 'activity' card for GitHub.
    
    Dependencies: resource.github.data
    
    Output schema:
    {
        "overview": {
            "commits": int,
            "pull_requests": int,
            "issues": int,
            "repositories": int,
            "stars_received": int,
            "contributions_last_year": int
        },
        "activity": {
            "contribution_calendar": {...} | null,
            "recent_activity": [...] | null
        },
        "code_contribution": {...} | null
    }
    """
    
    source = "github"
    card_type = "activity"
    
    def execute(self, ctx: ExecutionContext) -> CardResult:
        """Extract activity stats from resource.github.data artifact."""
        data = ctx.get_artifact("resource.github.data", {})
        
        if not isinstance(data, dict):
            data = {}
        
        user = data.get("user", {})
        if not isinstance(user, dict):
            user = {}
        
        overview = data.get("overview", {})
        if not isinstance(overview, dict):
            overview = {}
        
        # Build overview from user data
        def _get_count(field: str) -> int:
            val = user.get(field)
            if isinstance(val, int):
                return val
            if isinstance(val, dict):
                return int(val.get("totalCount", 0) or 0)
            return 0
        
        built_overview = {
            "commits": overview.get("commits", 0),
            "pull_requests": _get_count("pullRequests"),
            "issues": _get_count("issues"),
            "repositories": _get_count("repositories"),
            "stars_received": overview.get("stars_received") or _get_count("starredRepositories"),
            "contributions_last_year": overview.get("contributions_last_year", 0),
        }
        
        # Get contribution data
        contributions = user.get("contributionsCollection", {})
        if not isinstance(contributions, dict):
            contributions = {}
        
        calendar = contributions.get("contributionCalendar")
        
        activity_data = {
            "contribution_calendar": calendar,
            "recent_activity": data.get("recent_activity"),
        }
        
        return CardResult(
            data={
                "overview": built_overview,
                "activity": activity_data,
                "code_contribution": data.get("code_contribution"),
            }
        )
    
    def validate(self, data: Dict[str, Any], ctx: ExecutionContext) -> bool:
        """Validate activity has overview data."""
        overview = data.get("overview")
        if not isinstance(overview, dict):
            return False
        # Accept if we have any stats
        return any(v is not None for v in overview.values())
    
    def fallback(self, ctx: ExecutionContext, error: Optional[Exception] = None) -> CardResult:
        """Generate fallback activity."""
        return CardResult(
            data={
                "overview": {
                    "commits": 0,
                    "pull_requests": 0,
                    "issues": 0,
                    "repositories": 0,
                    "stars_received": 0,
                    "contributions_last_year": 0,
                },
                "activity": {
                    "contribution_calendar": None,
                    "recent_activity": None,
                },
                "code_contribution": None,
            },
            is_fallback=True,
            meta={"code": "activity_unavailable", "preserve_empty": True}
        )
