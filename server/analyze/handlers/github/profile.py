"""GitHub profile card handler."""
from __future__ import annotations

from typing import Any, Dict, Optional

from server.analyze.handlers.base import CardHandler, CardResult, ExecutionContext


class GitHubProfileHandler(CardHandler):
    """
    Handle the 'profile' card for GitHub.
    
    Dependencies: resource.github.profile
    
    Output schema:
    {
        "login": str,
        "name": str | null,
        "avatar_url": str | null,
        "bio": str | null,
        "company": str | null,
        "location": str | null,
        "email": str | null,
        "blog": str | null,
        "twitter_username": str | null,
        "followers": int,
        "following": int,
        "public_repos": int,
        "public_gists": int,
        "created_at": str | null
    }
    """
    
    source = "github"
    card_type = "profile"
    version = "2"
    
    def execute(self, ctx: ExecutionContext) -> CardResult:
        """Extract profile from resource artifacts.
        
        Data sources (in priority order):
        1. resource.github.profile - dedicated profile artifact
        2. resource.github.data - contains user info and analysis data
        """
        # Get profile artifact (may contain direct profile data)
        profile = ctx.get_artifact("resource.github.profile", {})
        if not isinstance(profile, dict):
            profile = {}
        
        # Get data artifact which contains user info
        data = ctx.get_artifact("resource.github.data", {})
        if not isinstance(data, dict):
            data = {}
        
        # User info can be at top level or under "user" key
        user = data.get("user", {}) if isinstance(data, dict) else {}
        if not isinstance(user, dict):
            user = {}
        
        # Merge all sources: data top-level < data.user < profile (last wins)
        merged = {}
        # First add top-level data fields (login, name, etc from data artifact)
        for k, v in data.items():
            if k not in ("user", "_meta") and v is not None:
                merged[k] = v
        # Then user dict
        for k, v in user.items():
            if v is not None:
                merged[k] = v
        # Finally profile artifact (highest priority)
        for k, v in profile.items():
            if v is not None:
                merged[k] = v
        
        return CardResult(
            data={
                "login": str(merged.get("login") or "").strip(),
                "name": merged.get("name"),
                "avatar_url": merged.get("avatar_url") or merged.get("avatarUrl"),
                "bio": merged.get("bio"),
                "company": merged.get("company"),
                "location": merged.get("location"),
                "email": merged.get("email"),
                "blog": merged.get("blog") or merged.get("websiteUrl"),
                "twitter_username": merged.get("twitter_username") or merged.get("twitterUsername"),
                "followers": merged.get("followers") if isinstance(merged.get("followers"), int) else (
                    merged.get("followers", {}).get("totalCount") if isinstance(merged.get("followers"), dict) else 0
                ),
                "following": merged.get("following") if isinstance(merged.get("following"), int) else (
                    merged.get("following", {}).get("totalCount") if isinstance(merged.get("following"), dict) else 0
                ),
                "public_repos": merged.get("public_repos") if isinstance(merged.get("public_repos"), int) else (
                    merged.get("repositories", {}).get("totalCount") if isinstance(merged.get("repositories"), dict) else 0
                ),
                "public_gists": merged.get("public_gists", 0),
                "created_at": merged.get("created_at") or merged.get("createdAt"),
            }
        )
    
    def validate(self, data: Dict[str, Any], ctx: ExecutionContext) -> bool:
        """Validate profile has login."""
        login = str(data.get("login") or "").strip()
        return bool(login)
    
    def fallback(self, ctx: ExecutionContext, error: Optional[Exception] = None) -> CardResult:
        """Generate fallback profile."""
        return CardResult(
            data={
                "login": "",
                "name": None,
                "avatar_url": None,
                "bio": None,
                "company": None,
                "location": None,
                "email": None,
                "blog": None,
                "twitter_username": None,
                "followers": 0,
                "following": 0,
                "public_repos": 0,
                "public_gists": 0,
                "created_at": None,
            },
            is_fallback=True,
            meta={"code": "profile_unavailable", "preserve_empty": True}
        )
