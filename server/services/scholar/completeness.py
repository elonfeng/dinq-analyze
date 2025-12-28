"""
Scholar report completeness helpers.

用于前端判断“哪些模块已补齐/仍在补齐中”，避免依赖字段是否存在的隐式逻辑。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from server.services.scholar.cache_validator import (
    is_valid_collaborator,
    is_valid_critical_evaluation,
    is_valid_role_model,
)


def compute_scholar_completeness(report: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Return a stable completeness object:
    {
      "base": true|false,
      "collaborator": true|false,
      "role_model": true|false,
      "level_info": true|false,
      "critical_evaluation": true|false,
      "paper_news": true|false,
      "missing": ["role_model", ...]
    }
    """

    if not isinstance(report, dict) or not report:
        return {
            "base": False,
            "collaborator": False,
            "role_model": False,
            "level_info": False,
            "critical_evaluation": False,
            "paper_news": False,
            "missing": ["base", "collaborator", "role_model", "level_info", "critical_evaluation", "paper_news"],
        }

    researcher = report.get("researcher")
    base_ok = isinstance(researcher, dict) and bool(researcher.get("name")) and bool(researcher.get("scholar_id"))

    collaborator = report.get("most_frequent_collaborator")
    collaborator_ok = isinstance(collaborator, dict) and is_valid_collaborator(collaborator)

    role_model = report.get("role_model")
    role_model_ok = isinstance(role_model, dict) and is_valid_role_model(role_model)

    level_info = report.get("level_info")
    level_ok = bool(level_info)

    critical = report.get("critical_evaluation")
    critical_ok = is_valid_critical_evaluation(str(critical or ""))

    news = report.get("paper_news")
    news_ok = bool(news)

    missing: List[str] = []
    if not base_ok:
        missing.append("base")
    if not collaborator_ok:
        missing.append("collaborator")
    if not role_model_ok:
        missing.append("role_model")
    if not level_ok:
        missing.append("level_info")
    if not critical_ok:
        missing.append("critical_evaluation")
    if not news_ok:
        missing.append("paper_news")

    return {
        "base": base_ok,
        "collaborator": collaborator_ok,
        "role_model": role_model_ok,
        "level_info": level_ok,
        "critical_evaluation": critical_ok,
        "paper_news": news_ok,
        "missing": missing,
    }

