"""
Gateway authentication utilities (DINQ analysis service).

This service is designed to run behind `dinq-gateway`.
The gateway authenticates end users and then forwards requests to this service
while injecting:
  - X-User-ID: authenticated user id (UUID string from gateway)
  - X-User-Tier: optional subscription tier

Direct user-auth (Firebase, etc.) is intentionally not supported in this
deployment model.
"""

from __future__ import annotations

import logging
import os
import time
from functools import wraps
from typing import Callable, Optional

from flask import g, jsonify, request

from server.utils.logging_config import setup_logging

setup_logging()
logger = logging.getLogger("server.utils.auth")


def _auth_bypass_enabled() -> bool:
    """Local/CI bypass (never enable in production)."""
    env = os.environ.get("FLASK_ENV", "development").lower()
    if env == "production":
        return False
    return os.environ.get("DINQ_AUTH_BYPASS", "false").lower() in ("1", "true", "yes", "on")


def _require_gateway_headers() -> tuple[Optional[str], Optional[str], Optional[str]]:
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        return None, None, "missing_user_id"

    tier = request.headers.get("X-User-Tier")
    return user_id, tier, None


def require_auth(f: Callable) -> Callable:
    """
    Require gateway-authenticated request.

    - OPTIONS is always allowed (CORS preflight).
    - In non-production, DINQ_AUTH_BYPASS can be used for local testing.
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == "OPTIONS":
            return f(*args, **kwargs)

        start = time.time()

        if _auth_bypass_enabled():
            user_id = request.headers.get("X-User-ID") or request.headers.get("Userid") or "test_user"
            g.user_id = user_id
            g.user_tier = request.headers.get("X-User-Tier") or ""
            g.is_verified_user = True
            g.verification_method = "bypass"
            result = f(*args, **kwargs)
            logger.warning(
                "Auth bypass used for %s %s (%.2fs), user_id=%s",
                request.method,
                request.path,
                time.time() - start,
                user_id,
            )
            return result

        user_id, tier, err = _require_gateway_headers()
        if err:
            return jsonify({"success": False, "error": "Authentication required"}), 401

        g.user_id = user_id
        g.user_tier = tier or ""
        g.is_verified_user = True
        g.verification_method = "gateway_headers"

        result = f(*args, **kwargs)
        logger.info(
            "Auth ok for %s %s (%.2fs), user_id=%s",
            request.method,
            request.path,
            time.time() - start,
            user_id,
        )
        return result

    return decorated


def require_verified_user(f: Callable) -> Callable:
    """Alias for require_auth (gateway already enforces user verification)."""

    return require_auth(f)


def get_user_id_from_header() -> Optional[str]:
    """
    Backward-compatible helper for legacy endpoints/tests.

    Historically some endpoints used a `Userid` header. The gateway model uses `X-User-ID`.
    """

    return (request.headers.get("X-User-ID") or request.headers.get("Userid") or "").strip() or None
