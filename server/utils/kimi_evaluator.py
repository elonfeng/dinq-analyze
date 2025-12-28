# coding: UTF-8
"""
Compatibility wrapper for legacy Kimi evaluator imports.

Historically, tests referenced server.utils.kimi_evaluator. The actual
implementation now lives in server.prompts.researcher_evaluator.
"""

from __future__ import annotations

from server.prompts.researcher_evaluator import (
    generate_critical_evaluation,
    format_researcher_data_for_critique,
)

__all__ = ["generate_critical_evaluation", "format_researcher_data_for_critique"]
