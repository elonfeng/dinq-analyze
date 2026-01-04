"""Scholar summary card handler."""
from __future__ import annotations

from typing import Any, Dict, Optional

from server.analyze.handlers.base import CardHandler, CardResult, ExecutionContext


class ScholarSummaryHandler(CardHandler):
    """
    Handle the 'summary' card for Scholar.
    
    Output schema:
    {
        "critical_evaluation": str | dict
    }
    """
    
    source = "scholar"
    card_type = "summary"
    
    def execute(self, ctx: ExecutionContext) -> CardResult:
        """Extract summary from scholar artifacts."""
        data = ctx.get_artifact("resource.scholar.full", {})
        if not isinstance(data, dict):
            data = {}
        
        evaluation = data.get("critical_evaluation")
        
        return CardResult(
            data={
                "critical_evaluation": evaluation or "",
            }
        )
    
    def validate(self, data: Dict[str, Any], ctx: ExecutionContext) -> bool:
        """Validate summary has evaluation."""
        ce = data.get("critical_evaluation")
        if isinstance(ce, dict) and ce:
            return True
        if isinstance(ce, str) and ce.strip():
            return True
        return False
    
    def fallback(self, ctx: ExecutionContext, error: Optional[Exception] = None) -> CardResult:
        """Generate fallback summary."""
        return CardResult(
            data={
                "critical_evaluation": "暂时无法生成总结（可能是模型/网络异常），建议稍后重试。",
            },
            is_fallback=True,
            meta={"code": "summary_unavailable", "preserve_empty": True}
        )
