"""Scholar role_model card handler."""
from __future__ import annotations

from typing import Any, Dict, Optional

from server.analyze.handlers.base import CardHandler, CardResult, ExecutionContext


class ScholarRoleModelHandler(CardHandler):
    """Handle the 'role_model' card for Scholar."""
    
    source = "scholar"
    card_type = "role_model"
    
    def execute(self, ctx: ExecutionContext) -> CardResult:
        """Extract role model from scholar artifacts."""
        data = ctx.get_artifact("resource.scholar.full", {})
        if not isinstance(data, dict):
            data = {}
        
        role_model = data.get("role_model", {})
        if not isinstance(role_model, dict):
            role_model = {}
        
        return CardResult(data=role_model)
    
    def validate(self, data: Dict[str, Any], ctx: ExecutionContext) -> bool:
        """Validate role model has name."""
        name = str(data.get("name") or "").strip()
        return bool(name)
    
    def fallback(self, ctx: ExecutionContext, error: Optional[Exception] = None) -> CardResult:
        """Generate fallback role model."""
        return CardResult(
            data={
                "name": "",
                "similarity_reason": "暂时无法生成 role model（稍后可重试）"
            },
            is_fallback=True,
            meta={"code": "role_model_unavailable", "preserve_empty": True}
        )
