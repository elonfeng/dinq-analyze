"""Scholar level card handler."""
from __future__ import annotations

from typing import Any, Dict, Optional

from server.analyze.handlers.base import CardHandler, CardResult, ExecutionContext


class ScholarLevelHandler(CardHandler):
    """
    Handle the 'level' card for Scholar.
    
    Output schema:
    {
        "level_cn": str,
        "level_us": str,
        "earnings": str,
        "justification": str
    }
    """
    
    source = "scholar"
    card_type = "level"
    
    def execute(self, ctx: ExecutionContext) -> CardResult:
        """Extract level from scholar artifacts."""
        data = ctx.get_artifact("resource.scholar.level", {})
        if not isinstance(data, dict):
            data = {}
        
        # Also check full report
        if not data:
            full = ctx.get_artifact("resource.scholar.full", {})
            if isinstance(full, dict):
                data = full.get("career_level", {}) or {}
        
        return CardResult(
            data={
                "level_cn": str(data.get("level_cn") or "").strip(),
                "level_us": str(data.get("level_us") or "").strip(),
                "earnings": str(data.get("earnings") or "").strip(),
                "justification": str(data.get("justification") or "").strip(),
            }
        )
    
    def validate(self, data: Dict[str, Any], ctx: ExecutionContext) -> bool:
        """Validate level has at least one field."""
        return any(str(data.get(k) or "").strip() for k in ["level_cn", "level_us", "earnings"])
    
    def fallback(self, ctx: ExecutionContext, error: Optional[Exception] = None) -> CardResult:
        """Generate fallback level."""
        return CardResult(
            data={
                "level_cn": "",
                "level_us": "",
                "earnings": "",
                "justification": "暂时无法评估 level（数据不足或模型异常），建议稍后重试。",
            },
            is_fallback=True,
            meta={"code": "level_unavailable", "preserve_empty": True}
        )
