"""GitHub summary card handler."""
from __future__ import annotations

from typing import Any, Dict, Optional

from server.analyze.handlers.base import CardHandler, CardResult, ExecutionContext


class GitHubSummaryHandler(CardHandler):
    """Handle the 'summary' card for GitHub."""
    
    source = "github"
    card_type = "summary"
    
    def execute(self, ctx: ExecutionContext) -> CardResult:
        """Extract summary (valuation_and_level + description) from enrich artifact."""
        enrich = ctx.get_artifact("resource.github.enrich", {})
        
        if not isinstance(enrich, dict):
            enrich = {}
        
        valuation = enrich.get("valuation_and_level")
        if not isinstance(valuation, dict):
            valuation = {}
        
        # Normalize valuation schema
        normalized_valuation = {
            "level": str(valuation.get("level") or "").strip(),
            "salary_range": valuation.get("salary_range") or [None, None],
            "industry_ranking": valuation.get("industry_ranking"),
            "growth_potential": str(valuation.get("growth_potential") or "").strip(),
            "reasoning": str(valuation.get("reasoning") or "").strip(),
        }
        
        description = str(enrich.get("description") or "").strip()
        
        return CardResult(
            data={
                "valuation_and_level": normalized_valuation,
                "description": description,
            }
        )
    
    def validate(self, data: Dict[str, Any], ctx: ExecutionContext) -> bool:
        """Validate summary has level."""
        valuation = data.get("valuation_and_level")
        if not isinstance(valuation, dict):
            return False
        level = str(valuation.get("level") or "").strip()
        return bool(level)
    
    def fallback(self, ctx: ExecutionContext, error: Optional[Exception] = None) -> CardResult:
        """Generate fallback summary."""
        # Try to get login from artifacts for better fallback message
        login = ""
        data_artifact = ctx.get_artifact("resource.github.data", {})
        if isinstance(data_artifact, dict):
            user = data_artifact.get("user")
            if isinstance(user, dict):
                login = str(user.get("login") or "").strip()
        
        desc = f"GitHub profile summary{(' for ' + login) if login else ''}."
        
        return CardResult(
            data={
                "valuation_and_level": {
                    "level": "",
                    "salary_range": [None, None],
                    "industry_ranking": None,
                    "growth_potential": "",
                    "reasoning": "",
                },
                "description": desc,
            },
            is_fallback=True,
            meta={"code": "summary_unavailable", "preserve_empty": True}
        )
