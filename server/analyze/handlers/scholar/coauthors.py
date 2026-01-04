"""Scholar coauthors card handler."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from server.analyze.handlers.base import CardHandler, CardResult, ExecutionContext


class ScholarCoauthorsHandler(CardHandler):
    """
    Handle the 'coauthors' card for Scholar.
    
    Output schema:
    {
        "main_author": {...} | null,
        "total_coauthors": int,
        "collaboration_index": float,
        "top_coauthors": [...],
        "most_frequent_collaborator": {...} | null
    }
    """
    
    source = "scholar"
    card_type = "coauthors"
    
    def execute(self, ctx: ExecutionContext) -> CardResult:
        """Extract coauthors from scholar artifacts."""
        data = ctx.get_artifact("resource.scholar.full", {})
        if not isinstance(data, dict):
            data = {}
        
        coauthors = data.get("coauthors", {})
        if not isinstance(coauthors, dict):
            coauthors = {}
        
        return CardResult(
            data={
                "main_author": coauthors.get("main_author"),
                "total_coauthors": coauthors.get("total_coauthors") or 0,
                "collaboration_index": coauthors.get("collaboration_index") or 0,
                "top_coauthors": coauthors.get("top_coauthors") or [],
                "most_frequent_collaborator": coauthors.get("most_frequent_collaborator"),
            }
        )
    
    def validate(self, data: Dict[str, Any], ctx: ExecutionContext) -> bool:
        """Coauthors is always valid (even if empty)."""
        return True
    
    def fallback(self, ctx: ExecutionContext, error: Optional[Exception] = None) -> CardResult:
        """Generate fallback coauthors."""
        return CardResult(
            data={
                "main_author": None,
                "total_coauthors": 0,
                "collaboration_index": 0,
                "top_coauthors": [],
                "most_frequent_collaborator": None,
            },
            is_fallback=True,
            meta={"code": "coauthors_unavailable", "preserve_empty": True}
        )
