"""LinkedIn colleagues_view card handler."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from server.analyze.handlers.base import CardHandler, CardResult, ExecutionContext


class LinkedInColleaguesViewHandler(CardHandler):
    """Handle the 'colleagues_view' card for LinkedIn."""
    
    source = "linkedin"
    card_type = "colleagues_view"
    
    def execute(self, ctx: ExecutionContext) -> CardResult:
        """Extract colleagues_view from enrich artifact."""
        enrich = ctx.get_artifact("resource.linkedin.enrich", {})
        
        if not isinstance(enrich, dict):
            enrich = {}
        
        colleagues_view = enrich.get("colleagues_view")
        if not isinstance(colleagues_view, dict):
            colleagues_view = {}
        
        highlights = colleagues_view.get("highlights")
        areas = colleagues_view.get("areas_for_improvement")
        
        if not isinstance(highlights, list):
            highlights = []
        if not isinstance(areas, list):
            areas = []
        
        return CardResult(
            data={
                "highlights": highlights,
                "areas_for_improvement": areas,
            }
        )
    
    def validate(self, data: Dict[str, Any], ctx: ExecutionContext) -> bool:
        """Validate colleagues_view has at least one non-empty string."""
        highlights = data.get("highlights") or []
        areas = data.get("areas_for_improvement") or []
        
        # Check if any item is a non-empty string
        for item in highlights + areas:
            if isinstance(item, str) and item.strip():
                return True
        
        return False
    
    def fallback(self, ctx: ExecutionContext, error: Optional[Exception] = None) -> CardResult:
        """Generate fallback colleagues_view."""
        return CardResult(
            data={
                "highlights": [],
                "areas_for_improvement": [],
            },
            is_fallback=True,
            meta={"code": "colleagues_view_unavailable", "preserve_empty": True}
        )
