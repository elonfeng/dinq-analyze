"""
SQLite local cache (L1).

This is used as a fast, single-machine cache without requiring any external cache service.

Notes:
- Designed for small/medium JSON blobs (final results / full_report snapshots).
- Safe for multi-process usage via SQLite file locks (WAL + short transactions).
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return int(default)
    try:
        return int(raw)
    except Exception:
        return int(default)


def _default_cache_path() -> str:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    return os.path.join(project_root, ".local", "cache", "dinq_l1.sqlite3")


@dataclass(frozen=True)
class CacheRow:
    key: str
    value: Dict[str, Any]
    created_at_s: int
    expires_at_s: Optional[int]


class SqliteCache:
    def __init__(self, path: str) -> None:
        self._path = str(path or "").strip() or _default_cache_path()
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._busy_timeout_ms = max(1, min(_int_env("DINQ_SQLITE_CACHE_BUSY_TIMEOUT_MS", 500), 60_000))
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self._path,
            timeout=max(0.001, float(self._busy_timeout_ms) / 1000.0),
            isolation_level=None,  # autocommit (short transactions)
            check_same_thread=False,
        )
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute(f"PRAGMA busy_timeout={int(self._busy_timeout_ms)};")
        except Exception:
            pass
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS kv ("
                "  key TEXT PRIMARY KEY,"
                "  value BLOB NOT NULL,"
                "  created_at_s INTEGER NOT NULL,"
                "  expires_at_s INTEGER"
                ");"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS kv_expires_at_idx ON kv(expires_at_s);")

    def _encode_json(self, value: Dict[str, Any]) -> bytes:
        raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        try:
            comp = zlib.compress(raw, level=6)
            if len(comp) < len(raw):
                return b"z" + comp
        except Exception:
            pass
        return b"j" + raw

    def _decode_json(self, raw: bytes) -> Optional[Dict[str, Any]]:
        if not raw:
            return None
        try:
            prefix = raw[:1]
            body = raw[1:]
            if prefix == b"z":
                body = zlib.decompress(body)
            elif prefix != b"j":
                body = raw
            text = body.decode("utf-8", errors="replace")
            obj = json.loads(text) if text else None
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

    def get_json(self, key: str) -> Optional[CacheRow]:
        k = str(key or "").strip()
        if not k:
            return None

        with self._connect() as conn:
            row = conn.execute(
                "SELECT value, created_at_s, expires_at_s FROM kv WHERE key = ?;",
                (k,),
            ).fetchone()
        if not row:
            return None
        value_raw, created_at_s, expires_at_s = row
        value = self._decode_json(value_raw) if isinstance(value_raw, (bytes, bytearray)) else None
        if value is None:
            return None
        try:
            created_at_int = int(created_at_s)
        except Exception:
            created_at_int = int(time.time())
        try:
            expires_int = int(expires_at_s) if expires_at_s is not None else None
        except Exception:
            expires_int = None
        return CacheRow(key=k, value=value, created_at_s=created_at_int, expires_at_s=expires_int)

    def set_json(self, *, key: str, value: Dict[str, Any], expires_at_s: Optional[int]) -> None:
        k = str(key or "").strip()
        if not k:
            raise ValueError("missing cache key")
        if not isinstance(value, dict):
            raise ValueError("cache value must be a dict")

        now_s = int(time.time())
        encoded = self._encode_json(value)

        with self._connect() as conn:
            conn.execute(
                "INSERT INTO kv(key, value, created_at_s, expires_at_s) VALUES(?, ?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, created_at_s=excluded.created_at_s, expires_at_s=excluded.expires_at_s;",
                (k, encoded, now_s, int(expires_at_s) if expires_at_s is not None else None),
            )


_CACHE_LOCK = threading.Lock()
_CACHE_SINGLETON: Optional[SqliteCache] = None


def sqlite_cache_enabled() -> bool:
    return _bool_env("DINQ_SQLITE_CACHE_ENABLED", True)


def get_sqlite_cache() -> Optional[SqliteCache]:
    """
    Return the process-global SQLite cache instance, or None when disabled.
    """

    if not sqlite_cache_enabled():
        return None
    global _CACHE_SINGLETON
    if _CACHE_SINGLETON is not None:
        return _CACHE_SINGLETON
    with _CACHE_LOCK:
        if _CACHE_SINGLETON is not None:
            return _CACHE_SINGLETON
        path = (os.getenv("DINQ_SQLITE_CACHE_PATH") or "").strip() or _default_cache_path()
        _CACHE_SINGLETON = SqliteCache(path)
        return _CACHE_SINGLETON
