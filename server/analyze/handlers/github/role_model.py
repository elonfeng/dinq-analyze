"""GitHub role_model card handler."""
from __future__ import annotations

from typing import Any, Dict, Optional

from server.analyze.handlers.base import CardHandler, CardResult, ExecutionContext


class GitHubRoleModelHandler(CardHandler):
    """Handle the 'role_model' card for GitHub."""
    
    source = "github"
    card_type = "role_model"
    version = "3"
    
    def execute(self, ctx: ExecutionContext) -> CardResult:
        """Extract role model from enrich artifact."""
        enrich = ctx.get_artifact("resource.github.enrich", {})
        
        if not isinstance(enrich, dict):
            enrich = {}
        
        role_model = enrich.get("role_model")
        if not isinstance(role_model, dict):
            role_model = {}
        
        return CardResult(data=role_model)
    
    def validate(self, data: Dict[str, Any], ctx: ExecutionContext) -> bool:
        """Validate role model has name and github fields."""
        name = str(data.get("name") or "").strip()
        github = str(data.get("github") or "").strip()
        return bool(name and github)
    
    def fallback(self, ctx: ExecutionContext, error: Optional[Exception] = None) -> CardResult:
        """Generate fallback role model."""
        # Final fallback (allowed): use the user themselves so the UI always has a baseline.
        login = ""
        name = ""
        url = ""
        data_artifact = ctx.get_artifact("resource.github.data", {})
        if isinstance(data_artifact, dict):
            user = data_artifact.get("user")
            if isinstance(user, dict):
                login = str(user.get("login") or "").strip()
                name = str(user.get("name") or "").strip()
                url = str(user.get("url") or "").strip()
        if not url and login:
            url = f"https://github.com/{login}"
        if not name:
            name = login

        return CardResult(
            data={
                "name": name or "",
                "github": url or "",
                "similarity_score": 1.0 if url else 0.0,
                "reason": "Fallback: no suitable external role model was found; using the user as a baseline comparison.",
            },
            is_fallback=True,
            meta={"code": "role_model_unavailable", "preserve_empty": True}
        )
