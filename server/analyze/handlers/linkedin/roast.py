"""LinkedIn roast card handler."""
from __future__ import annotations

from typing import Any, Dict, Optional

from server.analyze.handlers.base import CardHandler, CardResult, ExecutionContext


class LinkedInRoastHandler(CardHandler):
    """Handle the 'roast' card for LinkedIn."""
    
    source = "linkedin"
    card_type = "roast"
    
    def execute(self, ctx: ExecutionContext) -> CardResult:
        """Extract roast from enrich artifact."""
        enrich = ctx.get_artifact("resource.linkedin.enrich", {})
        
        if not isinstance(enrich, dict):
            enrich = {}
        
        roast = enrich.get("roast")
        
        if isinstance(roast, dict):
            roast_text = str(roast.get("roast") or "").strip()
        else:
            roast_text = str(roast or "").strip()
        
        return CardResult(data={"roast": roast_text})
    
    def validate(self, data: Dict[str, Any], ctx: ExecutionContext) -> bool:
        """Validate roast has non-empty text."""
        roast = data.get("roast") if isinstance(data, dict) else data
        if isinstance(roast, dict):
            roast = roast.get("roast")
        return bool(str(roast or "").strip())
    
    def fallback(self, ctx: ExecutionContext, error: Optional[Exception] = None) -> CardResult:
        """Generate fallback roast."""
        return CardResult(
            data={"roast": "暂时无法生成 Roast（可能是模型/网络异常），建议稍后重试。"},
            is_fallback=True,
            meta={"code": "roast_unavailable", "preserve_empty": True}
        )
