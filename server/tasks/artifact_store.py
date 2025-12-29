"""
Artifact store for analysis outputs.

Goal:
- Provide a local-disk cache to avoid slow remote DB round-trips during execution.
- Keep DB fallback optional (for legacy/backward compatibility).
"""
from __future__ import annotations

import base64
import json
import os
import time
import zlib
from pathlib import Path
from typing import Any, Dict, Optional

from src.utils.db_utils import get_db_session
from src.models.db import AnalysisArtifact


class ArtifactStore:
    def __init__(self) -> None:
        raw_disable_db = (os.getenv("DINQ_ARTIFACT_STORE_DISABLE_DB") or "").strip().lower()
        self._db_disabled = raw_disable_db in ("1", "true", "yes", "on")

        # Disk fallback/cache (shared by API + runner on the same machine).
        raw_disk_dir = (os.getenv("DINQ_ARTIFACT_DISK_DIR") or "").strip()
        if not raw_disk_dir:
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
            raw_disk_dir = os.path.join(project_root, ".local", "artifacts")
        self._disk_dir = raw_disk_dir
        try:
            disk_ttl = int(os.getenv("DINQ_ARTIFACT_DISK_TTL_SECONDS") or "86400")
        except Exception:
            disk_ttl = 86400
        self._disk_ttl_seconds = max(0, int(disk_ttl))
        try:
            disk_max_bytes = int(os.getenv("DINQ_ARTIFACT_DISK_MAX_BYTES") or "52428800")  # 50 MiB
        except Exception:
            disk_max_bytes = 52_428_800
        self._disk_max_bytes = max(0, int(disk_max_bytes))

        raw = (os.getenv("DINQ_ARTIFACT_COMPRESS") or "1").strip().lower()
        self._compress = raw in ("1", "true", "yes", "on")

        raw_types = (os.getenv("DINQ_ARTIFACT_STORE_SKIP_DB_TYPES") or "").strip()
        self._skip_db_types = {t.strip() for t in raw_types.split(",") if t.strip()}

        raw_prefixes_env = os.getenv("DINQ_ARTIFACT_STORE_SKIP_DB_PREFIXES")
        if raw_prefixes_env is None:
            # Default: do not skip DB writes. This keeps job execution reliable even when the local
            # disk cache is unavailable or the process topology changes (multiple workers/runners).
            self._skip_db_prefixes = []
        else:
            raw_prefixes = raw_prefixes_env.strip()
            self._skip_db_prefixes = [p.strip() for p in raw_prefixes.split(",") if p.strip()]

    def _should_skip_db(self, type: str) -> bool:
        t = str(type or "").strip()
        if not t:
            return False
        if t in self._skip_db_types:
            return True
        for p in self._skip_db_prefixes:
            if p and t.startswith(p):
                return True
        return False

    def _b64(self, value: str) -> str:
        raw = str(value or "")
        enc = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")
        return enc.rstrip("=")

    def _encode(self, obj: Any, *, max_bytes: int) -> Optional[bytes]:
        try:
            raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        except Exception:
            return None

        if self._compress and raw:
            try:
                comp = zlib.compress(raw, level=6)
                if len(comp) < len(raw):
                    raw = b"z" + comp
                else:
                    raw = b"j" + raw
            except Exception:
                raw = b"j" + raw
        else:
            raw = b"j" + raw

        if max_bytes > 0 and len(raw) > int(max_bytes):
            return None
        return raw

    def _decode(self, raw: bytes) -> Any:
        if raw is None:
            return None
        if not isinstance(raw, (bytes, bytearray)) or not raw:
            return None
        try:
            prefix = raw[:1]
            body = raw[1:]
            if prefix == b"z":
                body = zlib.decompress(body)
            elif prefix != b"j":
                # Backward compat: treat as plain JSON.
                body = raw
            text = body.decode("utf-8", errors="replace")
            return json.loads(text) if text else None
        except Exception:
            return None

    def _disk_artifact_path(self, job_id: str, type: str) -> Path:
        return Path(self._disk_dir) / str(job_id) / f"{self._b64(type)}.bin"

    def _disk_get_artifact(self, *, job_id: str, type: str) -> Optional[AnalysisArtifact]:
        if not self._disk_dir:
            return None
        path = self._disk_artifact_path(job_id, type)
        try:
            stat = path.stat()
        except FileNotFoundError:
            return None
        except Exception:
            return None

        if self._disk_ttl_seconds > 0:
            try:
                age_s = time.time() - float(stat.st_mtime)
                if age_s > float(self._disk_ttl_seconds):
                    try:
                        path.unlink(missing_ok=True)  # py3.8+: ignore if already deleted
                    except Exception:
                        pass
                    return None
            except Exception:
                pass

        try:
            raw = path.read_bytes()
        except Exception:
            return None

        obj = self._decode(raw) if isinstance(raw, (bytes, bytearray)) else None
        if not isinstance(obj, dict):
            return None
        payload = obj.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        file_url = obj.get("file_url")
        if file_url is not None:
            file_url = str(file_url)
        card_id = obj.get("card_id")
        try:
            card_id_int = int(card_id) if card_id is not None else None
        except Exception:
            card_id_int = None
        return AnalysisArtifact(job_id=str(job_id), card_id=card_id_int, type=str(type), payload=payload, file_url=file_url)

    def _disk_set_artifact(
        self,
        *,
        job_id: str,
        card_id: Optional[int],
        type: str,
        payload: Optional[Dict[str, Any]],
        file_url: Optional[str],
    ) -> bool:
        if not self._disk_dir:
            return False
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            return False

        encoded = self._encode({"payload": payload, "file_url": file_url, "card_id": card_id}, max_bytes=int(self._disk_max_bytes))
        if not encoded:
            return False

        path = self._disk_artifact_path(job_id, type)
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes(encoded)
            os.replace(str(tmp), str(path))
        except Exception:
            try:
                # Best-effort cleanup
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
            return False
        return True

    def save_artifact(
        self,
        *,
        job_id: str,
        card_id: Optional[int],
        type: str,
        payload: Optional[Dict[str, Any]] = None,
        file_url: Optional[str] = None,
    ) -> AnalysisArtifact:
        type_str = str(type or "")
        payload_dict = payload or {}

        disk_ok = False
        try:
            disk_ok = self._disk_set_artifact(job_id=job_id, card_id=card_id, type=type_str, payload=payload_dict, file_url=file_url)
        except Exception:
            disk_ok = False

        # Optional performance switch: for large, intermediate artifacts (e.g. resource.*), allow disk-only
        # storage to reduce cross-region DB writes.
        if disk_ok and self._should_skip_db(type_str):
            return AnalysisArtifact(job_id=str(job_id), card_id=card_id, type=type_str, payload=payload_dict, file_url=file_url)

        if self._db_disabled and disk_ok:
            return AnalysisArtifact(job_id=str(job_id), card_id=card_id, type=type_str, payload=payload_dict, file_url=file_url)

        with get_db_session() as session:
            artifact = AnalysisArtifact(
                job_id=job_id,
                card_id=card_id,
                type=type_str,
                payload=payload_dict,
                file_url=file_url,
            )
            session.add(artifact)
            session.flush()
            # Avoid session.refresh(): it costs an extra DB round-trip and callers do not rely on server-side defaults.
            if not disk_ok:
                try:
                    self._disk_set_artifact(job_id=job_id, card_id=card_id, type=type_str, payload=payload_dict, file_url=file_url)
                except Exception:
                    pass
            return artifact

    def get_artifact(self, job_id: str, type: str) -> Optional[AnalysisArtifact]:
        cached = None
        try:
            cached = self._disk_get_artifact(job_id=job_id, type=type)
        except Exception:
            cached = None
        if cached is not None:
            return cached

        if self._db_disabled:
            return None

        with get_db_session() as session:
            artifact = (
                session.query(AnalysisArtifact)
                .filter(AnalysisArtifact.job_id == job_id, AnalysisArtifact.type == type)
                .order_by(AnalysisArtifact.id.desc())
                .first()
            )

        if artifact is not None:
            try:
                self._disk_set_artifact(
                    job_id=str(job_id),
                    card_id=int(getattr(artifact, "card_id", None)) if getattr(artifact, "card_id", None) is not None else None,
                    type=str(type),
                    payload=artifact.payload if isinstance(artifact.payload, dict) else {},
                    file_url=str(getattr(artifact, "file_url", None)) if getattr(artifact, "file_url", None) is not None else None,
                )
            except Exception:
                pass
        return artifact
