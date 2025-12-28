"""DB-backed cache for LLM responses."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Optional

from src.utils.db_utils import get_db_session
from src.models.db import LLMCache


class LLMCacheStore:
    def __init__(self) -> None:
        ttl_seconds = os.getenv("DINQ_LLM_CACHE_TTL_SECONDS", "0")
        try:
            self._ttl_seconds = int(ttl_seconds)
        except ValueError:
            self._ttl_seconds = 0

    def _is_expired(self, created_at) -> bool:
        if not created_at or self._ttl_seconds <= 0:
            return False
        return datetime.utcnow() - created_at > timedelta(seconds=self._ttl_seconds)

    def get(self, key: str) -> Optional[str]:
        with get_db_session() as session:
            row = session.query(LLMCache).filter(LLMCache.cache_key == key).first()
            if not row:
                return None
            if self._is_expired(row.created_at):
                try:
                    session.delete(row)
                except Exception:
                    pass
                return None
            return row.response_text

    def set(self, key: str, response_text: str) -> None:
        with get_db_session() as session:
            row = session.query(LLMCache).filter(LLMCache.cache_key == key).first()
            if row:
                row.response_text = response_text
                row.created_at = datetime.utcnow()
                return
            session.add(LLMCache(cache_key=key, response_text=response_text))
