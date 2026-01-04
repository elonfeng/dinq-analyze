"""LinkedIn card handlers."""
from __future__ import annotations

from server.analyze.handlers.linkedin.skills import LinkedInSkillsHandler
from server.analyze.handlers.linkedin.career import LinkedInCareerHandler
from server.analyze.handlers.linkedin.money import LinkedInMoneyHandler
from server.analyze.handlers.linkedin.colleagues_view import LinkedInColleaguesViewHandler
from server.analyze.handlers.linkedin.life_well_being import LinkedInLifeWellBeingHandler
from server.analyze.handlers.linkedin.roast import LinkedInRoastHandler
from server.analyze.handlers.linkedin.summary import LinkedInSummaryHandler
from server.analyze.handlers.linkedin.role_model import LinkedInRoleModelHandler

__all__ = [
    "LinkedInSkillsHandler",
    "LinkedInCareerHandler",
    "LinkedInMoneyHandler",
    "LinkedInColleaguesViewHandler",
    "LinkedInLifeWellBeingHandler",
    "LinkedInRoastHandler",
    "LinkedInSummaryHandler",
    "LinkedInRoleModelHandler",
]
