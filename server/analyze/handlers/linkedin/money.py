"""LinkedIn money card handler."""
from __future__ import annotations

from typing import Any, Dict, Optional

from server.analyze.handlers.base import CardHandler, CardResult, ExecutionContext


class LinkedInMoneyHandler(CardHandler):
    """
    Handle the 'money' card for LinkedIn.
    
    Dependencies: resource.linkedin.enrich
    
    Output schema:
    {
        "years_of_experience": {...},
        "level_us": str | null,
        "level_cn": str | null,
        "estimated_salary": str,
        "explanation": str
    }
    """
    
    source = "linkedin"
    card_type = "money"
    
    def execute(self, ctx: ExecutionContext) -> CardResult:
        """Extract money analysis from enrich artifact."""
        enrich = ctx.get_artifact("resource.linkedin.enrich", {})
        
        if not isinstance(enrich, dict):
            enrich = {}
        
        money = enrich.get("money") or enrich.get("money_analysis")
        if not isinstance(money, dict):
            money = {}
        
        years = money.get("years_of_experience")
        if not isinstance(years, dict):
            years = {}
        
        # Normalize estimated salary
        est_raw = money.get("estimated_salary") or money.get("earnings") or money.get("salary_range") or ""
        est = str(est_raw).strip()
        if est:
            est = est.replace(",", "").replace("$", "").replace("USD", "").strip()
            est = est.replace("–", "-").replace("—", "-").replace("~", "-")
        
        return CardResult(
            data={
                "years_of_experience": years,
                "level_us": str(money.get("level_us") or "").strip() or None,
                "level_cn": str(money.get("level_cn") or "").strip() or None,
                "estimated_salary": est,
                "explanation": str(money.get("explanation") or money.get("justification") or "").strip(),
            }
        )
    
    def validate(self, data: Dict[str, Any], ctx: ExecutionContext) -> bool:
        """Validate money has level or salary."""
        level_us = str(data.get("level_us") or "").strip()
        level_cn = str(data.get("level_cn") or "").strip()
        salary = str(data.get("estimated_salary") or "").strip()
        return bool(level_us or level_cn or salary)
    
    def fallback(self, ctx: ExecutionContext, error: Optional[Exception] = None) -> CardResult:
        """Generate fallback money."""
        return CardResult(
            data={
                "years_of_experience": {},
                "level_us": None,
                "level_cn": None,
                "estimated_salary": "",
                "explanation": "",
            },
            is_fallback=True,
            meta={"code": "money_unavailable", "preserve_empty": True}
        )
