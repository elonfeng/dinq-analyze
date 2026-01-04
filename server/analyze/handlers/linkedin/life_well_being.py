"""LinkedIn life_well_being card handler."""
from __future__ import annotations

from typing import Any, Dict, Optional

from server.analyze.handlers.base import CardHandler, CardResult, ExecutionContext


class LinkedInLifeWellBeingHandler(CardHandler):
    """Handle the 'life_well_being' card for LinkedIn."""
    
    source = "linkedin"
    card_type = "life_well_being"
    
    def execute(self, ctx: ExecutionContext) -> CardResult:
        """Extract life_well_being from enrich artifact."""
        enrich = ctx.get_artifact("resource.linkedin.enrich", {})
        
        if not isinstance(enrich, dict):
            enrich = {}
        
        life_well_being = enrich.get("life_well_being")
        if not isinstance(life_well_being, dict):
            life_well_being = {}
        
        life_suggestion = str(life_well_being.get("life_suggestion") or "").strip()
        health = str(life_well_being.get("health") or "").strip()
        
        return CardResult(
            data={
                "life_suggestion": life_suggestion,
                "health": health,
            }
        )
    
    def validate(self, data: Dict[str, Any], ctx: ExecutionContext) -> bool:
        """Validate life_well_being has at least one non-empty field."""
        life = str(data.get("life_suggestion") or "").strip()
        health = str(data.get("health") or "").strip()
        return bool(life or health)
    
    def fallback(self, ctx: ExecutionContext, error: Optional[Exception] = None) -> CardResult:
        """Generate fallback life_well_being."""
        return CardResult(
            data={
                "life_suggestion": "",
                "health": "",
            },
            is_fallback=True,
            meta={"code": "life_well_being_unavailable", "preserve_empty": True}
        )
