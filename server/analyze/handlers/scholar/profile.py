"""Scholar profile card handler."""
from __future__ import annotations

from typing import Any, Dict, Optional

from server.analyze.handlers.base import CardHandler, CardResult, ExecutionContext


class ScholarProfileHandler(CardHandler):
    """
    Handle the 'profile' card for Scholar.
    
    Dependencies: resource.scholar.page0 or resource.scholar.base
    
    Output schema:
    {
        "name": str,
        "scholar_id": str | null,
        "affiliation": str | null,
        "email": str | null,
        "research_fields": [...],
        "total_citations": int,
        "h_index": int,
        "avatar": str | null
    }
    """
    
    source = "scholar"
    card_type = "profile"
    
    def execute(self, ctx: ExecutionContext) -> CardResult:
        """Extract profile from scholar artifacts."""
        # Try page0 first, then base, then full
        data = ctx.get_artifact("resource.scholar.page0", {})
        if not isinstance(data, dict) or not data:
            data = ctx.get_artifact("resource.scholar.base", {})
        if not isinstance(data, dict) or not data:
            data = ctx.get_artifact("resource.scholar.full", {})
        
        if not isinstance(data, dict):
            data = {}
        
        researcher = data.get("researcher", {})
        if not isinstance(researcher, dict):
            researcher = {}
        
        return CardResult(
            data={
                "name": str(researcher.get("name") or "").strip(),
                "scholar_id": researcher.get("scholar_id"),
                "affiliation": researcher.get("affiliation"),
                "email": researcher.get("email"),
                "research_fields": researcher.get("research_fields") or [],
                "total_citations": researcher.get("total_citations") or 0,
                "h_index": researcher.get("h_index") or 0,
                "avatar": researcher.get("avatar"),
            }
        )
    
    def validate(self, data: Dict[str, Any], ctx: ExecutionContext) -> bool:
        """Validate profile has name or scholar_id."""
        name = str(data.get("name") or "").strip()
        scholar_id = str(data.get("scholar_id") or "").strip()
        return bool(name or scholar_id)
    
    def fallback(self, ctx: ExecutionContext, error: Optional[Exception] = None) -> CardResult:
        """Generate fallback profile."""
        return CardResult(
            data={
                "name": "",
                "scholar_id": None,
                "affiliation": None,
                "email": None,
                "research_fields": [],
                "total_citations": 0,
                "h_index": 0,
                "avatar": None,
            },
            is_fallback=True,
            meta={"code": "profile_unavailable", "preserve_empty": True}
        )
