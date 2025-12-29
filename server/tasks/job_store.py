"""
DB-backed job storage for unified analysis pipeline.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime

from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import load_only

from src.utils.db_utils import get_db_session
from src.models.db import AnalysisJob, AnalysisJobCard, AnalysisJobEvent, AnalysisJobIdempotency
from server.tasks.output_schema import ensure_output_envelope


class JobStore:
    def _dialect_name(self, session) -> str:  # type: ignore[no-untyped-def]
        try:
            bind = session.get_bind()
            name = getattr(getattr(bind, "dialect", None), "name", None) if bind is not None else None
            return str(name or "").strip().lower()
        except Exception:
            return ""

    def create_job(
        self,
        *,
        job_id: str,
        user_id: str,
        source: str,
        input_payload: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> AnalysisJob:
        with get_db_session() as session:
            job = AnalysisJob(
                id=job_id,
                user_id=user_id,
                source=source,
                status="queued",
                last_seq=0,
                input=input_payload or {},
                options=options or {},
            )
            session.add(job)
            session.flush()
            session.refresh(job)
            return job

    def create_job_bundle(
        self,
        *,
        job_id: Optional[str] = None,
        user_id: str,
        source: str,
        input_payload: Dict[str, Any],
        options: Dict[str, Any],
        plan: List[Dict[str, Any]],
        subject_key: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        request_hash: Optional[str] = None,
    ) -> tuple[str, bool]:
        """
        Create a job + job_cards (+ initial job.started event) atomically.

        If (user_id, idempotency_key) is provided, enforces idempotency:
        - Same key + same request_hash => returns existing job_id
        - Same key + different request_hash => raises ValueError
        """

        if idempotency_key and not request_hash:
            raise ValueError("missing request_hash for idempotency key")

        job_id = (str(job_id or "").strip() or uuid.uuid4().hex)

        with get_db_session() as session:
            if idempotency_key:
                existing = (
                    session.query(AnalysisJobIdempotency)
                    .filter(
                        AnalysisJobIdempotency.user_id == user_id,
                        AnalysisJobIdempotency.idempotency_key == idempotency_key,
                    )
                    .first()
                )
                if existing is not None:
                    if str(existing.request_hash or "") != str(request_hash or ""):
                        raise ValueError("idempotency_key_conflict")
                    return str(existing.job_id), False

            job = AnalysisJob(
                id=job_id,
                user_id=user_id,
                source=source,
                status="queued",
                last_seq=1,
                input=input_payload or {},
                options=options or {},
                subject_key=subject_key or None,
            )
            session.add(job)
            # NOTE: we bulk-insert job_cards below; ensure the parent job row exists first to satisfy FK constraints.
            session.flush()

            # cards
            card_rows: List[Dict[str, Any]] = []
            for card in plan:
                deadline_ms = None
                raw_deadline = card.get("deadline_ms")
                if raw_deadline is not None:
                    try:
                        deadline_ms = int(raw_deadline)
                    except Exception:
                        deadline_ms = None
                concurrency_group = str(card.get("concurrency_group") or "").strip() or None
                card_rows.append(
                    {
                        "job_id": job_id,
                        "card_type": str(card.get("card_type")),
                        "status": str(card.get("status", "pending")),
                        "priority": int(card.get("priority", 0) or 0),
                        "deadline_ms": deadline_ms,
                        "concurrency_group": concurrency_group,
                        "input": card.get("input") or {},
                        "deps": card.get("depends_on") or [],
                        "output": {"data": None, "stream": {}},
                    }
                )
            if card_rows:
                # Bulk insert reduces DB round trips significantly when the DB is remote/high RTT.
                session.bulk_insert_mappings(AnalysisJobCard, card_rows)

            # initial event: seq=1 for brand new job
            ev = AnalysisJobEvent(
                job_id=job_id,
                card_id=None,
                seq=1,
                event_type="job.started",
                payload={"job_id": job_id, "source": source},
            )
            session.add(ev)

            if idempotency_key:
                session.add(
                    AnalysisJobIdempotency(
                        user_id=user_id,
                        idempotency_key=idempotency_key,
                        request_hash=str(request_hash),
                        job_id=job_id,
                    )
                )

            try:
                session.flush()
            except IntegrityError:
                # Likely: another request inserted the same idempotency key concurrently.
                session.rollback()
                if not idempotency_key:
                    raise
                existing = (
                    session.query(AnalysisJobIdempotency)
                    .filter(
                        AnalysisJobIdempotency.user_id == user_id,
                        AnalysisJobIdempotency.idempotency_key == idempotency_key,
                    )
                    .first()
                )
                if existing is not None and str(existing.request_hash or "") == str(request_hash or ""):
                    return str(existing.job_id), False
                raise

            return job_id, True

    def set_job_status(self, job_id: str, status: str, result: Optional[Dict[str, Any]] = None) -> None:
        with get_db_session() as session:
            session.query(AnalysisJob).filter(AnalysisJob.id == job_id).update(
                {
                    "status": status,
                    "result": result,
                    "updated_at": func.now(),
                }
            )

    def try_finalize_job(self, job_id: str, status: str, result: Optional[Dict[str, Any]] = None) -> bool:
        """
        Idempotently set a terminal job status.

        Returns True only for the first caller that transitions the job into a
        terminal status (completed/partial/failed/cancelled).
        """

        terminal = {"completed", "partial", "failed", "cancelled"}
        if status not in terminal:
            raise ValueError(f"try_finalize_job requires terminal status, got: {status}")

        patch: Dict[str, Any] = {"status": status, "updated_at": func.now()}
        if result is not None:
            patch["result"] = result

        with get_db_session() as session:
            updated = (
                session.query(AnalysisJob)
                .filter(AnalysisJob.id == job_id, ~AnalysisJob.status.in_(terminal))
                .update(patch, synchronize_session=False)
            )
            return bool(updated and int(updated) > 0)

    def get_job(self, job_id: str) -> Optional[AnalysisJob]:
        with get_db_session() as session:
            return session.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()

    def get_job_with_cards(self, job_id: str, *, include_output: bool = True) -> Optional[Dict[str, Any]]:
        with get_db_session() as session:
            job = session.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
            if job is None:
                return None
            q = session.query(AnalysisJobCard).filter(AnalysisJobCard.job_id == job_id).order_by(AnalysisJobCard.id.asc())
            if not include_output:
                q = q.options(
                    load_only(
                        AnalysisJobCard.id,
                        AnalysisJobCard.job_id,
                        AnalysisJobCard.card_type,
                        AnalysisJobCard.status,
                        AnalysisJobCard.retry_count,
                        AnalysisJobCard.started_at,
                        AnalysisJobCard.ended_at,
                        AnalysisJobCard.created_at,
                        AnalysisJobCard.updated_at,
                    )
                )
            cards = q.all()
            return {
                "job": job,
                "cards": cards,
            }

    def get_card_outputs(self, card_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        if not card_ids:
            return {}
        out: Dict[int, Dict[str, Any]] = {}
        with get_db_session() as session:
            rows = (
                session.query(AnalysisJobCard.id, AnalysisJobCard.output)
                .filter(AnalysisJobCard.id.in_([int(cid) for cid in card_ids if cid]))
                .all()
            )
            for cid, payload in rows:
                try:
                    out[int(cid)] = ensure_output_envelope(payload)
                except Exception:
                    continue
        return out

    def create_cards(self, job_id: str, cards: List[Dict[str, Any]]) -> List[AnalysisJobCard]:
        created: List[AnalysisJobCard] = []
        with get_db_session() as session:
            for card in cards:
                deadline_ms = None
                raw_deadline = card.get("deadline_ms")
                if raw_deadline is not None:
                    try:
                        deadline_ms = int(raw_deadline)
                    except Exception:
                        deadline_ms = None
                rec = AnalysisJobCard(
                    job_id=job_id,
                    card_type=str(card.get("card_type")),
                    status=str(card.get("status", "pending")),
                    priority=int(card.get("priority", 0) or 0),
                    deadline_ms=deadline_ms,
                    concurrency_group=str(card.get("concurrency_group") or "") or None,
                    input=card.get("input") or {},
                    deps=card.get("depends_on") or [],
                    output={"data": None, "stream": {}},
                )
                session.add(rec)
                created.append(rec)
            session.flush()
            for rec in created:
                session.refresh(rec)
        return created

    def update_card_status(
        self,
        *,
        card_id: int,
        status: str,
        output: Optional[Dict[str, Any]] = None,
        preserve_existing_stream: bool = True,
        retry_count: Optional[int] = None,
        started_at: Optional[datetime] = None,
        ended_at: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Update card status and (optionally) output.

        If output is provided:
        - preserve_existing_stream=True (default): merge into the {data, stream} envelope while preserving any
          existing output.stream accumulated from card.delta events (DB-mode streaming).
        - preserve_existing_stream=False: write output directly (fast path) without reading the existing row.
        """

        if output is not None and preserve_existing_stream:
            with get_db_session() as session:
                q = session.query(AnalysisJobCard).filter(AnalysisJobCard.id == card_id)
                try:
                    q = q.with_for_update()
                except Exception:  # noqa: BLE001
                    pass
                card = q.first()
                if card is None:
                    return None

                existing = ensure_output_envelope(getattr(card, "output", None))
                incoming = ensure_output_envelope(output)

                stream = existing.get("stream")
                if not isinstance(stream, dict):
                    stream = {}

                incoming_stream = incoming.get("stream")
                if isinstance(incoming_stream, dict) and incoming_stream:
                    merged_stream = dict(stream)
                    merged_stream.update(incoming_stream)
                    stream = merged_stream

                merged = {"data": incoming.get("data"), "stream": stream}

                card.status = status
                card.output = merged
                if retry_count is not None:
                    card.retry_count = retry_count
                if started_at is not None:
                    card.started_at = started_at
                if ended_at is not None:
                    card.ended_at = ended_at
                try:
                    card.updated_at = datetime.utcnow()
                except Exception:
                    pass
                session.flush()
                return merged

        patch: Dict[str, Any] = {
            "status": status,
            "updated_at": func.now(),
        }
        if output is not None:
            patch["output"] = ensure_output_envelope(output)
        if retry_count is not None:
            patch["retry_count"] = retry_count
        if started_at is not None:
            patch["started_at"] = started_at
        if ended_at is not None:
            patch["ended_at"] = ended_at
        with get_db_session() as session:
            session.query(AnalysisJobCard).filter(AnalysisJobCard.id == card_id).update(patch)
        return patch.get("output") if output is not None else None

    def fetch_ready_cards(self, limit: int = 10) -> List[AnalysisJobCard]:
        # Kept for backward-compat / debugging. Prefer claim_ready_cards() for schedulers.
        with get_db_session() as session:
            return (
                session.query(AnalysisJobCard)
                .filter(AnalysisJobCard.status == "ready")
                .order_by(AnalysisJobCard.priority.desc(), AnalysisJobCard.id.asc())
                .limit(limit)
                .all()
            )

    def claim_ready_cards(self, limit: int = 10) -> List[AnalysisJobCard]:
        """
        Atomically claim a batch of ready cards for execution.

        Why:
        - The scheduler may run in multiple processes (gunicorn workers). Without DB locking, the
          same ready card could be picked and executed multiple times.
        - Postgres row-level locking (FOR UPDATE SKIP LOCKED) prevents duplicate claims.
        """
        now = datetime.utcnow()
        with get_db_session() as session:
            # Postgres fast path: one UPDATE ... RETURNING to reduce DB round trips across high-RTT links.
            if self._dialect_name(session) == "postgresql":
                try:
                    rows = session.execute(
                        text(
                            "UPDATE job_cards "
                            "SET status = 'running', started_at = :now, ended_at = NULL, updated_at = :now "
                            "WHERE id IN ("
                            "  SELECT id FROM job_cards "
                            "  WHERE status = 'ready' "
                            "  ORDER BY priority DESC, id ASC "
                            "  FOR UPDATE SKIP LOCKED "
                            "  LIMIT :limit"
                            ") "
                            "RETURNING id, job_id, card_type, priority, status, deadline_ms, concurrency_group, input, deps, output, retry_count, started_at, ended_at, created_at, updated_at"
                        ),
                        {"now": now, "limit": int(limit or 10)},
                    ).all()
                    cards: List[AnalysisJobCard] = []
                    for r in rows:
                        try:
                            cards.append(
                                AnalysisJobCard(
                                    id=int(r.id),
                                    job_id=str(r.job_id),
                                    card_type=str(r.card_type),
                                    priority=int(r.priority or 0),
                                    status=str(r.status or "running"),
                                    deadline_ms=int(r.deadline_ms) if r.deadline_ms is not None else None,
                                    concurrency_group=str(r.concurrency_group) if r.concurrency_group is not None else None,
                                    input=r.input if isinstance(r.input, dict) else (r.input or {}),
                                    deps=r.deps if isinstance(r.deps, list) else (r.deps or []),
                                    output=r.output,
                                    retry_count=int(r.retry_count or 0),
                                    started_at=r.started_at,
                                    ended_at=r.ended_at,
                                    created_at=r.created_at,
                                    updated_at=r.updated_at,
                                )
                            )
                        except Exception:
                            continue
                    return cards
                except Exception:
                    # Fall back to the generic ORM path below.
                    pass

            q = (
                session.query(AnalysisJobCard)
                .filter(AnalysisJobCard.status == "ready")
                .order_by(AnalysisJobCard.priority.desc(), AnalysisJobCard.id.asc())
                .limit(limit)
            )
            try:
                q = q.with_for_update(skip_locked=True)
            except Exception:  # noqa: BLE001
                # Best-effort fallback for DBs that don't support SKIP LOCKED (e.g. sqlite).
                pass
            cards = q.all()
            for c in cards:
                c.status = "running"
                c.started_at = now
                # Clear any previous attempt end time (retries / stale running recovery).
                # The scheduler uses ended_at=None as a lease guard.
                c.ended_at = None
                c.updated_at = now
            session.flush()
            return cards

    def confirm_card_claim(self, *, card_id: int, started_at: datetime) -> bool:
        """
        Confirm this worker still owns the claimed card execution.

        Why:
        - In rare cases under multi-worker concurrency, the same card may be executed twice.
        - We treat (card_id, started_at) as a best-effort lease token written by claim_ready_cards().
        - If another worker overwrote started_at (or already completed the card), this returns False.
        """

        if not card_id or started_at is None:
            return False

        with get_db_session() as session:
            updated = (
                session.query(AnalysisJobCard)
                .filter(
                    AnalysisJobCard.id == int(card_id),
                    AnalysisJobCard.status == "running",
                    AnalysisJobCard.started_at == started_at,
                    AnalysisJobCard.ended_at.is_(None),
                )
                .update({"updated_at": func.now()}, synchronize_session=False)
            )
            return bool(updated and int(updated) > 0)

    def mark_cards_running(self, card_ids: List[int]) -> None:
        if not card_ids:
            return
        now = datetime.utcnow()
        with get_db_session() as session:
            session.query(AnalysisJobCard).filter(AnalysisJobCard.id.in_(card_ids)).update(
                {
                    "status": "running",
                    "started_at": now,
                    "ended_at": None,
                    "updated_at": now,
                },
                synchronize_session=False,
            )

    def list_cards_for_job(self, job_id: str) -> List[AnalysisJobCard]:
        with get_db_session() as session:
            return (
                session.query(AnalysisJobCard)
                .filter(AnalysisJobCard.job_id == job_id)
                .order_by(AnalysisJobCard.id.asc())
                .all()
            )

    def mark_cards_ready(self, job_id: str, card_types: List[str]) -> None:
        if not card_types:
            return
        with get_db_session() as session:
            session.query(AnalysisJobCard).filter(
                AnalysisJobCard.job_id == job_id,
                AnalysisJobCard.card_type.in_(card_types),
                AnalysisJobCard.status == "pending",
            ).update(
                {"status": "ready", "updated_at": func.now()},
                synchronize_session=False,
            )

    def mark_pending_cards_skipped(self, job_id: str) -> None:
        with get_db_session() as session:
            session.query(AnalysisJobCard).filter(
                AnalysisJobCard.job_id == job_id,
                AnalysisJobCard.status.in_(["pending", "ready", "running"]),
            ).update(
                {"status": "skipped", "updated_at": func.now()},
                synchronize_session=False,
            )

    def release_ready_cards(self, job_id: str) -> int:
        """
        Transition cards from pending -> ready when all their deps are completed.

        Dependencies are stored as `job_cards.deps` (list of card_type strings).
        Backward-compat:
        - If deps is NULL for a non-full_report card, treat it as depending on full_report.
        """

        with get_db_session() as session:
            rows = (
                session.query(AnalysisJobCard.id, AnalysisJobCard.card_type, AnalysisJobCard.status, AnalysisJobCard.deps)
                .filter(AnalysisJobCard.job_id == job_id)
                .order_by(AnalysisJobCard.id.asc())
                .all()
            )
            if not rows:
                return 0

            status_by_type = {str(card_type): str(status or "") for _id, card_type, status, _deps in rows}
            ready_ids: list[int] = []

            for cid, card_type, status, deps_raw in rows:
                if str(status) != "pending":
                    continue

                if deps_raw is None and str(card_type) != "full_report":
                    deps = ["full_report"]
                elif isinstance(deps_raw, list):
                    deps = [str(d).strip() for d in deps_raw if str(d).strip()]
                else:
                    deps = []

                if not deps or all(status_by_type.get(dep) == "completed" for dep in deps):
                    try:
                        ready_ids.append(int(cid))
                    except Exception:
                        continue

            if not ready_ids:
                return 0

            now = datetime.utcnow()
            updated = (
                session.query(AnalysisJobCard)
                .filter(
                    AnalysisJobCard.job_id == job_id,
                    AnalysisJobCard.id.in_(ready_ids),
                    AnalysisJobCard.status == "pending",
                )
                .update({"status": "ready", "updated_at": now}, synchronize_session=False)
            )
            return int(updated or 0)

    def mark_dependent_cards_skipped(self, job_id: str, failed_card_type: str) -> int:
        """
        Skip cards that depend (directly or transitively) on a failed card.

        This prevents jobs from getting stuck with pending cards whose deps can never be satisfied.
        """

        root = str(failed_card_type or "").strip()
        if not root:
            return 0

        with get_db_session() as session:
            rows = (
                session.query(AnalysisJobCard.card_type, AnalysisJobCard.status, AnalysisJobCard.deps)
                .filter(AnalysisJobCard.job_id == job_id)
                .order_by(AnalysisJobCard.id.asc())
                .all()
            )
            if not rows:
                return 0

            deps_by_type: Dict[str, list[str]] = {}
            for card_type, _status, deps_raw in rows:
                if deps_raw is None and str(card_type) != "full_report":
                    deps = ["full_report"]
                elif isinstance(deps_raw, list):
                    deps = [str(d).strip() for d in deps_raw if str(d).strip()]
                else:
                    deps = []
                deps_by_type[str(card_type)] = deps

            # Build adjacency dep -> dependents
            dependents: Dict[str, list[str]] = {}
            for card_type, deps in deps_by_type.items():
                for dep in deps:
                    dependents.setdefault(dep, []).append(card_type)

            # BFS to find all transitively dependent cards
            to_visit = [root]
            visited: set[str] = set()
            impacted: set[str] = set()
            while to_visit:
                cur = to_visit.pop()
                if cur in visited:
                    continue
                visited.add(cur)
                for nxt in dependents.get(cur, []):
                    if nxt not in visited:
                        impacted.add(nxt)
                        to_visit.append(nxt)

            if not impacted:
                return 0

            now = datetime.utcnow()
            updated = (
                session.query(AnalysisJobCard)
                .filter(
                    AnalysisJobCard.job_id == job_id,
                    AnalysisJobCard.card_type.in_(list(impacted)),
                    AnalysisJobCard.status.in_(["pending", "ready"]),
                )
                .update({"status": "skipped", "updated_at": now}, synchronize_session=False)
            )
            return int(updated or 0)

    def count_cards_by_status(self, job_id: str) -> Dict[str, int]:
        with get_db_session() as session:
            rows = (
                session.query(AnalysisJobCard.status, func.count(AnalysisJobCard.id))
                .filter(AnalysisJobCard.job_id == job_id)
                .group_by(AnalysisJobCard.status)
                .all()
            )
            return {status: int(count) for status, count in rows}
