"""GitHub card handlers."""
from __future__ import annotations

from server.analyze.handlers.github.profile import GitHubProfileHandler
from server.analyze.handlers.github.activity import GitHubActivityHandler
from server.analyze.handlers.github.repos import GitHubReposHandler
from server.analyze.handlers.github.role_model import GitHubRoleModelHandler
from server.analyze.handlers.github.roast import GitHubRoastHandler
from server.analyze.handlers.github.summary import GitHubSummaryHandler

__all__ = [
    "GitHubProfileHandler",
    "GitHubActivityHandler",
    "GitHubReposHandler",
    "GitHubRoleModelHandler",
    "GitHubRoastHandler",
    "GitHubSummaryHandler",
]
