"""
GitHub repos card handler.

Extracts repository information from the enrich artifact.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from server.analyze.handlers.base import CardHandler, CardResult, ExecutionContext


class GitHubReposHandler(CardHandler):
    """
    Handle the 'repos' card for GitHub.
    
    Dependencies: resource.github.enrich
    
    Output schema:
    {
        "feature_project": {...} | null,
        "top_projects": [...],
        "most_valuable_pull_request": {...} | null
    }
    """
    
    source = "github"
    card_type = "repos"
    
    def execute(self, ctx: ExecutionContext) -> CardResult:
        """Extract repos info from enrich artifact."""
        enrich = ctx.get_artifact("resource.github.enrich", {})
        
        if not isinstance(enrich, dict):
            enrich = {}
        
        feature_project = enrich.get("feature_project")
        top_projects = enrich.get("top_projects")
        mvp_pr = enrich.get("most_valuable_pull_request")
        
        # Normalize types
        if not isinstance(top_projects, list):
            top_projects = []
        
        return CardResult(
            data={
                "feature_project": feature_project,
                "top_projects": top_projects,
                "most_valuable_pull_request": mvp_pr,
            }
        )
    
    def validate(self, data: Dict[str, Any], ctx: ExecutionContext) -> bool:
        """
        Validate repos card.
        
        Acceptable if:
        - Has feature_project OR has top_projects
        - MVP PR is optional (user might have no PRs)
        """
        has_feature = bool(data.get("feature_project"))
        has_top = bool(data.get("top_projects"))
        
        return has_feature or has_top
    
    def fallback(self, ctx: ExecutionContext, error: Optional[Exception] = None) -> CardResult:
        """Generate fallback repos payload."""
        return CardResult(
            data={
                "feature_project": None,
                "top_projects": [],
                "most_valuable_pull_request": None,
            },
            is_fallback=True,
            meta={"code": "repos_unavailable", "preserve_empty": True}
        )
