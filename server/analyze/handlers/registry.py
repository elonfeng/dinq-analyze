"""
Global handler registry.

Import and register all available card handlers here.
"""
from __future__ import annotations

from server.analyze.handlers.base import HandlerRegistry

# Import GitHub handlers
from server.analyze.handlers.github.profile import GitHubProfileHandler
from server.analyze.handlers.github.activity import GitHubActivityHandler
from server.analyze.handlers.github.repos import GitHubReposHandler
from server.analyze.handlers.github.role_model import GitHubRoleModelHandler
from server.analyze.handlers.github.roast import GitHubRoastHandler
from server.analyze.handlers.github.summary import GitHubSummaryHandler

# Import LinkedIn handlers
from server.analyze.handlers.linkedin.skills import LinkedInSkillsHandler
from server.analyze.handlers.linkedin.career import LinkedInCareerHandler
from server.analyze.handlers.linkedin.money import LinkedInMoneyHandler
from server.analyze.handlers.linkedin.colleagues_view import LinkedInColleaguesViewHandler
from server.analyze.handlers.linkedin.life_well_being import LinkedInLifeWellBeingHandler
from server.analyze.handlers.linkedin.roast import LinkedInRoastHandler
from server.analyze.handlers.linkedin.summary import LinkedInSummaryHandler
from server.analyze.handlers.linkedin.role_model import LinkedInRoleModelHandler

# Import Scholar handlers
from server.analyze.handlers.scholar.profile import ScholarProfileHandler
from server.analyze.handlers.scholar.papers import ScholarPapersHandler
from server.analyze.handlers.scholar.coauthors import ScholarCoauthorsHandler
from server.analyze.handlers.scholar.level import ScholarLevelHandler
from server.analyze.handlers.scholar.summary import ScholarSummaryHandler
from server.analyze.handlers.scholar.news import ScholarNewsHandler
from server.analyze.handlers.scholar.role_model import ScholarRoleModelHandler


# Global registry
_global_registry = None


def get_global_registry() -> HandlerRegistry:
    """Get the global handler registry (singleton)."""
    global _global_registry
    
    if _global_registry is None:
        _global_registry = HandlerRegistry()
        
        # Register GitHub handlers
        _global_registry.register_class(GitHubProfileHandler)
        _global_registry.register_class(GitHubActivityHandler)
        _global_registry.register_class(GitHubReposHandler)
        _global_registry.register_class(GitHubRoleModelHandler)
        _global_registry.register_class(GitHubRoastHandler)
        _global_registry.register_class(GitHubSummaryHandler)
        
        # Register LinkedIn handlers
        _global_registry.register_class(LinkedInSkillsHandler)
        _global_registry.register_class(LinkedInCareerHandler)
        _global_registry.register_class(LinkedInMoneyHandler)
        _global_registry.register_class(LinkedInColleaguesViewHandler)
        _global_registry.register_class(LinkedInLifeWellBeingHandler)
        _global_registry.register_class(LinkedInRoastHandler)
        _global_registry.register_class(LinkedInSummaryHandler)
        _global_registry.register_class(LinkedInRoleModelHandler)
        
        # Register Scholar handlers
        _global_registry.register_class(ScholarProfileHandler)
        _global_registry.register_class(ScholarPapersHandler)
        _global_registry.register_class(ScholarCoauthorsHandler)
        _global_registry.register_class(ScholarLevelHandler)
        _global_registry.register_class(ScholarSummaryHandler)
        _global_registry.register_class(ScholarNewsHandler)
        _global_registry.register_class(ScholarRoleModelHandler)
    
    return _global_registry


def get_handler(source: str, card_type: str):
    """Get a handler by (source, card_type)."""
    return get_global_registry().get(source, card_type)


def has_handler(source: str, card_type: str) -> bool:
    """Check if a handler is registered."""
    return get_global_registry().has(source, card_type)
