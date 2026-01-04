"""Scholar papers card handler."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from server.analyze.handlers.base import CardHandler, CardResult, ExecutionContext


class ScholarPapersHandler(CardHandler):
    """
    Handle the 'papers' card for Scholar.
    
    Dependencies: resource.scholar.full
    
    Output schema:
    {
        "most_cited_paper": {...} | null,
        "paper_of_year": {...} | null,
        "top_tier_publications": {"conferences": [...], "journals": [...]},
        "year_distribution": {...},
        "items": [...]
    }
    """
    
    source = "scholar"
    card_type = "papers"
    
    def execute(self, ctx: ExecutionContext) -> CardResult:
        """Extract papers from scholar artifacts."""
        data = ctx.get_artifact("resource.scholar.full", {})
        if not isinstance(data, dict):
            data = {}
        
        pub_stats = data.get("publication_stats", {})
        if not isinstance(pub_stats, dict):
            pub_stats = {}
        
        papers = data.get("papers") or pub_stats.get("papers")
        if not isinstance(papers, list):
            papers = []
        
        # Limit papers for output
        max_items = 200
        items = papers[:max_items] if len(papers) > max_items else papers
        
        return CardResult(
            data={
                "most_cited_paper": pub_stats.get("most_cited_paper"),
                "paper_of_year": pub_stats.get("paper_of_year"),
                "top_tier_publications": pub_stats.get("top_tier_publications") or {"conferences": [], "journals": []},
                "year_distribution": pub_stats.get("year_distribution") or {},
                "items": items,
            }
        )
    
    def validate(self, data: Dict[str, Any], ctx: ExecutionContext) -> bool:
        """Validate papers has content."""
        items = data.get("items", [])
        most_cited = data.get("most_cited_paper")
        year_dist = data.get("year_distribution", {})
        return bool(items or most_cited or year_dist)
    
    def fallback(self, ctx: ExecutionContext, error: Optional[Exception] = None) -> CardResult:
        """Generate fallback papers."""
        return CardResult(
            data={
                "most_cited_paper": None,
                "paper_of_year": None,
                "top_tier_publications": {"conferences": [], "journals": []},
                "year_distribution": {},
                "items": [],
            },
            is_fallback=True,
            meta={"code": "papers_unavailable", "preserve_empty": True}
        )
