"""
GitHub Analyzer package.

为避免导入包时触发重依赖/循环导入，这里使用惰性导入。
"""

from __future__ import annotations

from typing import Any

__version__ = "1.0.0"
__author__ = "GitHub Analyzer Team"


def __getattr__(name: str) -> Any:
    if name == "GitHubAnalyzer":
        from .analyzer import GitHubAnalyzer

        return GitHubAnalyzer
    if name == "create_app":
        from .flask_app import create_app

        return create_app
    if name == "load_config":
        from .config import load_config

        return load_config
    raise AttributeError(name)


__all__ = ["GitHubAnalyzer", "create_app", "load_config"]
