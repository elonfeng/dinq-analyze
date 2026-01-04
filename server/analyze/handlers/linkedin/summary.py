"""LinkedIn summary card handler."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from server.analyze.handlers.base import CardHandler, CardResult, ExecutionContext


class LinkedInSummaryHandler(CardHandler):
    """
    Handle the 'summary' card for LinkedIn.
    
    Dependencies: resource.linkedin.enrich
    
    Output schema:
    {
        "about": str,
        "personal_tags": [...]
    }
    """
    
    source = "linkedin"
    card_type = "summary"
    
    def execute(self, ctx: ExecutionContext) -> CardResult:
        """Extract summary from enrich artifact."""
        enrich = ctx.get_artifact("resource.linkedin.enrich", {})
        
        if not isinstance(enrich, dict):
            enrich = {}
        
        summary = enrich.get("summary")
        if not isinstance(summary, dict):
            summary = {}
        
        about = str(summary.get("about") or "").strip()
        tags = summary.get("personal_tags")
        if not isinstance(tags, list):
            tags = []
        
        return CardResult(
            data={
                "about": about,
                "personal_tags": tags,
            }
        )
    
    def validate(self, data: Dict[str, Any], ctx: ExecutionContext) -> bool:
        """Validate summary has about text."""
        about = str(data.get("about") or "").strip()
        return bool(about)
    
    def fallback(self, ctx: ExecutionContext, error: Optional[Exception] = None) -> CardResult:
        """Generate fallback summary."""
        return CardResult(
            data={
                "about": "暂时无法生成 About（可能是模型/网络异常），建议稍后重试。",
                "personal_tags": [],
            },
            is_fallback=True,
            meta={"code": "summary_unavailable", "preserve_empty": True}
        )
