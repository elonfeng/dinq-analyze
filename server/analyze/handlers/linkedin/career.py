"""LinkedIn career card handler."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from server.analyze.handlers.base import CardHandler, CardResult, ExecutionContext


class LinkedInCareerHandler(CardHandler):
    """
    Handle the 'career' card for LinkedIn.
    
    Dependencies: resource.linkedin.enrich
    
    Output schema:
    {
        "career": {...},
        "work_experience": [...],
        "education": [...],
        "work_experience_summary": str,
        "education_summary": str
    }
    """
    
    source = "linkedin"
    card_type = "career"
    
    def execute(self, ctx: ExecutionContext) -> CardResult:
        """Extract career from enrich artifact."""
        enrich = ctx.get_artifact("resource.linkedin.enrich", {})
        
        if not isinstance(enrich, dict):
            enrich = {}
        
        career = enrich.get("career")
        if not isinstance(career, dict):
            career = {}
        
        def _as_list(val: Any) -> List[Any]:
            return val if isinstance(val, list) else []
        
        # Also try to get from raw_profile artifact
        raw_profile_art = ctx.get_artifact("resource.linkedin.raw_profile", {})
        profile_data = {}
        if isinstance(raw_profile_art, dict):
            profile_data = raw_profile_art.get("profile_data", {})
            if not isinstance(profile_data, dict):
                profile_data = {}
        
        work_exp = _as_list(enrich.get("work_experience")) or _as_list(profile_data.get("work_experience"))
        education = _as_list(enrich.get("education")) or _as_list(profile_data.get("education"))
        
        return CardResult(
            data={
                "career": career,
                "work_experience": work_exp,
                "education": education,
                "work_experience_summary": str(enrich.get("work_experience_summary") or "").strip(),
                "education_summary": str(enrich.get("education_summary") or "").strip(),
            }
        )
    
    def validate(self, data: Dict[str, Any], ctx: ExecutionContext) -> bool:
        """Validate career has work experience or education."""
        work = data.get("work_experience", [])
        edu = data.get("education", [])
        return bool((isinstance(work, list) and work) or (isinstance(edu, list) and edu))
    
    def fallback(self, ctx: ExecutionContext, error: Optional[Exception] = None) -> CardResult:
        """Generate fallback career."""
        return CardResult(
            data={
                "career": {},
                "work_experience": [],
                "education": [],
                "work_experience_summary": "暂时无法生成工作经历总结",
                "education_summary": "暂时无法生成教育经历总结",
            },
            is_fallback=True,
            meta={"code": "career_unavailable", "preserve_empty": True}
        )
