"""Scholar news card handler."""
from __future__ import annotations

from typing import Any, Dict, Optional

from server.analyze.handlers.base import CardHandler, CardResult, ExecutionContext


class ScholarNewsHandler(CardHandler):
    """
    Handle the 'news' card for Scholar.
    
    Output schema:
    {
        "news": str,
        "date": str,
        "description": str,
        "url": str | null
    }
    """
    
    source = "scholar"
    card_type = "news"
    
    def execute(self, ctx: ExecutionContext) -> CardResult:
        """Extract news from scholar artifacts."""
        data = ctx.get_artifact("resource.scholar.full", {})
        if not isinstance(data, dict):
            data = {}
        
        news = data.get("news", {})
        if not isinstance(news, dict):
            news = {}
        
        return CardResult(
            data={
                "news": str(news.get("news") or news.get("title") or "").strip(),
                "date": str(news.get("date") or "").strip(),
                "description": str(news.get("description") or "").strip(),
                "url": news.get("url"),
            }
        )
    
    def validate(self, data: Dict[str, Any], ctx: ExecutionContext) -> bool:
        """Validate news has content."""
        news = str(data.get("news") or "").strip()
        desc = str(data.get("description") or "").strip()
        return bool(news or desc)
    
    def fallback(self, ctx: ExecutionContext, error: Optional[Exception] = None) -> CardResult:
        """Generate fallback news."""
        return CardResult(
            data={
                "news": "暂无相关新闻",
                "date": "",
                "description": "未能获取相关新闻（可能无可用来源或数据不足）。",
                "url": None,
            },
            is_fallback=True,
            meta={"code": "news_unavailable", "preserve_empty": True}
        )
