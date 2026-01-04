"""LinkedIn skills card handler."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from server.analyze.handlers.base import CardHandler, CardResult, ExecutionContext


class LinkedInSkillsHandler(CardHandler):
    """
    Handle the 'skills' card for LinkedIn.
    
    Dependencies: resource.linkedin.enrich
    
    Output schema:
    {
        "industry_knowledge": [...],
        "tools_technologies": [...],
        "interpersonal_skills": [...],
        "language": [...]
    }
    """
    
    source = "linkedin"
    card_type = "skills"
    
    def execute(self, ctx: ExecutionContext) -> CardResult:
        """Extract skills from enrich artifact."""
        enrich = ctx.get_artifact("resource.linkedin.enrich", {})
        
        if not isinstance(enrich, dict):
            enrich = {}
        
        skills = enrich.get("skills")
        if not isinstance(skills, dict):
            skills = {}
        
        def _as_list(val: Any) -> List[Any]:
            return val if isinstance(val, list) else []
        
        return CardResult(
            data={
                "industry_knowledge": _as_list(skills.get("industry_knowledge")),
                "tools_technologies": _as_list(skills.get("tools_technologies")),
                "interpersonal_skills": _as_list(skills.get("interpersonal_skills")),
                "language": _as_list(skills.get("language")),
            }
        )
    
    def validate(self, data: Dict[str, Any], ctx: ExecutionContext) -> bool:
        """Validate skills has at least one non-empty category."""
        return any(
            isinstance(data.get(k), list) and len(data.get(k, [])) > 0
            for k in ["industry_knowledge", "tools_technologies", "interpersonal_skills", "language"]
        )
    
    def fallback(self, ctx: ExecutionContext, error: Optional[Exception] = None) -> CardResult:
        """Generate fallback skills."""
        return CardResult(
            data={
                "industry_knowledge": [],
                "tools_technologies": [],
                "interpersonal_skills": [],
                "language": [],
            },
            is_fallback=True,
            meta={"code": "skills_unavailable", "preserve_empty": True}
        )
