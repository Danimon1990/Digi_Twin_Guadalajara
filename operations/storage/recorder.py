from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock, get_ident
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - this project currently targets POSIX hosts
    fcntl = None  # type: ignore[assignment]

from ..domain.events import DomainEvent, EventObject, EvidenceReference, Lifecycle
from ..domain.models import Run, RunKind, RunStatus
from ..domain.validation import require_id
from ..capture.models import CoverageInterval, ObservationSource, SourceAlignment

SCHEMA_VERSION = 2


class RecorderError(RuntimeError):
    pass


class IdempotencyConflict(RecorderError):
    pass


class SealedRunError(RecorderError):
    pass


class UnknownObjectError(RecorderError):
    pass


class EventRecorder:
    """Single-owner SQLite event writer; subscriber callbacks run after commit."""

    def __init__(self, database: str | Path) -> None:
        self.database = str(database)
        self._owner_thread = get_ident()
        self._lock = RLock()
        self._subscribers: list[Callable[[int, DomainEvent], None]] = []
        self._subscriber_errors: list[Exception] = []
        self._closed = False
        self._writer_lock_handle = None
        try:
            self._acquire_writer_lock()
            self._connection = sqlite3.connect(self.database, isolation_level=None)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._initialize_schema()
        except Exception:
            self._release_writer_lock()
            raise

    def _acquire_writer_lock(self) -> None:
        if self.database == ":memory:" or fcntl is None:
            return
        lock_path = Path(f"{self.database}.writer.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = lock_path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.close()
            raise RecorderError(f"database already has an active writer: {self.database}") from exc
        self._writer_lock_handle = handle

    def _release_writer_lock(self) -> None:
        if self._writer_lock_handle is not None:
            if fcntl is not None:
                fcntl.flock(self._writer_lock_handle.fileno(), fcntl.LOCK_UN)
            self._writer_lock_handle.close()
            self._writer_lock_handle = None

    def _initialize_schema(self) -> None:
        tables = {
            row[0] for row in self._connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        managed = {"runs", "events", "event_objects", "entity_registry"}
        if "schema_migrations" not in tables and tables.intersection(managed):
            raise RecorderError(
                "database has operations tables without schema metadata; explicit migration required"
            )
        if "schema_migrations" in tables:
            row = self._connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
            current = int(row[0] or 0)
            if current > SCHEMA_VERSION:
                raise RecorderError(
                    f"database schema {current} is newer than supported {SCHEMA_VERSION}"
                )
        else:
            current = 0
        needs_backup = 0 < current < SCHEMA_VERSION
        if current < 1:
            schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
            self._connection.executescript(schema)
            self._connection.execute(
                "INSERT INTO schema_migrations(version, applied_at_utc) VALUES (?, ?)",
                (1, datetime.now(timezone.utc).isoformat()),
            )
            current = 1
        if current < 2:
            if needs_backup:
                self._backup_before_migration(current, 2)
            migration = Path(__file__).with_name("migrations").joinpath(
                "0002_observations.sql"
            ).read_text(encoding="utf-8")
            self._connection.executescript(migration)
            self._connection.execute(
                "INSERT INTO schema_migrations(version, applied_at_utc) VALUES (?, ?)",
                (2, datetime.now(timezone.utc).isoformat()),
            )

    def _backup_before_migration(self, from_version: int, to_version: int) -> None:
        if self.database == ":memory:":
            return
        backup_path = Path(
            f"{self.database}.pre_v{to_version}_from_v{from_version}.sqlite3"
        )
        if backup_path.exists():
            return
        backup = sqlite3.connect(backup_path)
        try:
            self._connection.backup(backup)
        finally:
            backup.close()

    def __enter__(self) -> "EventRecorder":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _assert_owner(self) -> None:
        if get_ident() != self._owner_thread:
            raise RecorderError("EventRecorder must be used by its owning thread")

    def close(self) -> None:
        self._assert_owner()
        if not self._closed:
            self._connection.close()
            self._release_writer_lock()
            self._closed = True

    @property
    def subscriber_errors(self) -> tuple[Exception, ...]:
        return tuple(self._subscriber_errors)

    def subscribe(self, callback: Callable[[int, DomainEvent], None]) -> None:
        self._subscribers.append(callback)

    def create_run(self, run: Run) -> None:
        self._assert_owner()
        self._connection.execute(
            """INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run.run_id, run.kind.value, run.scenario_id, run.status.value,
                run.schema_version, run.model_version, run.layout_version,
                _json(run.effective_config), run.seed, run.source_ref, run.parent_run_id,
                int(run.is_test), run.created_at_utc.isoformat(), run.analysis_cutoff_s,
                _dt(run.stopped_at_utc), run.stop_reason,
            ),
        )
        self.register_entity("run", run.run_id, run_scope=run.run_id)

    def run_info(self, run_id: str) -> sqlite3.Row | None:
        self._assert_owner()
        return self._connection.execute(
            "SELECT * FROM runs WHERE run_id=?", (run_id,)
        ).fetchone()

    def register_entity(self, object_type: str, object_id: str, *, run_scope: str = "*") -> None:
        self._assert_owner()
        require_id(object_type, "object_type")
        require_id(object_id, "object_id")
        self._connection.execute(
            "INSERT OR IGNORE INTO entity_registry VALUES (?, ?, ?)",
            (run_scope, object_type, object_id),
        )

    def add_observation_source(self, source: ObservationSource) -> None:
        self._assert_owner()
        run = self._connection.execute(
            "SELECT kind FROM runs WHERE run_id=?", (source.run_id,)
        ).fetchone()
        if run is None or run["kind"] != RunKind.OBSERVED.value:
            raise RecorderError("observation sources require an observed run")
        values = (
            source.run_id, source.source_id, source.source_type, source.file_name,
            source.sha256, source.viewpoint, _json(source.visible_zones),
            source.timezone, _dt(source.wall_clock_start_utc), source.duration_s,
            source.notes,
        )
        self._connection.execute(
            """INSERT INTO observation_sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(run_id, source_id) DO NOTHING""",
            values,
        )
        existing = self._connection.execute(
            """SELECT run_id,source_id,source_type,file_name,sha256,viewpoint,
                      visible_zones_json,timezone,wall_clock_start_utc,duration_s,notes
               FROM observation_sources WHERE run_id=? AND source_id=?""",
            (source.run_id, source.source_id),
        ).fetchone()
        if existing is None or tuple(existing) != values:
            raise IdempotencyConflict(
                f"observation source {source.source_id!r} has different content"
            )

    def add_source_alignment(self, alignment: SourceAlignment) -> None:
        self._assert_owner()
        values = (
            alignment.run_id, alignment.alignment_id, alignment.source_a_id,
            alignment.source_b_id, alignment.offset_b_minus_a_s,
            alignment.method, alignment.confidence, alignment.notes,
        )
        self._connection.execute(
            """INSERT INTO source_alignments VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(run_id, alignment_id) DO NOTHING""",
            values,
        )
        existing = self._connection.execute(
            """SELECT run_id,alignment_id,source_a_id,source_b_id,
                      offset_b_minus_a_s,method,confidence,notes
               FROM source_alignments WHERE run_id=? AND alignment_id=?""",
            (alignment.run_id, alignment.alignment_id),
        ).fetchone()
        if existing is None or tuple(existing) != values:
            raise IdempotencyConflict(
                f"source alignment {alignment.alignment_id!r} has different content"
            )

    def add_coverage_interval(self, coverage: CoverageInterval) -> None:
        self._assert_owner()
        values = (
            coverage.run_id, coverage.coverage_id, coverage.source_id,
            coverage.start_offset_s, coverage.end_offset_s, coverage.state,
            _json(coverage.zones), coverage.notes,
        )
        self._connection.execute(
            """INSERT INTO observation_coverage VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(run_id, coverage_id) DO NOTHING""",
            values,
        )
        existing = self._connection.execute(
            """SELECT run_id,coverage_id,source_id,start_offset_s,end_offset_s,
                      state,zones_json,notes
               FROM observation_coverage WHERE run_id=? AND coverage_id=?""",
            (coverage.run_id, coverage.coverage_id),
        ).fetchone()
        if existing is None or tuple(existing) != values:
            raise IdempotencyConflict(
                f"coverage interval {coverage.coverage_id!r} has different content"
            )

    def seal_run(
        self,
        run_id: str,
        *,
        analysis_cutoff_s: float | None = None,
        reason: str = "completed",
        status: RunStatus = RunStatus.SEALED,
    ) -> None:
        self._assert_owner()
        require_id(run_id, "run_id")
        changed = self._connection.execute(
            """UPDATE runs SET status=?, analysis_cutoff_s=?, stopped_at_utc=?, stop_reason=?
               WHERE run_id=? AND status='open'""",
            (status.value, analysis_cutoff_s, datetime.now(timezone.utc).isoformat(), reason, run_id),
        ).rowcount
        if changed != 1:
            raise RecorderError(f"run {run_id!r} is missing or not open")

    def record(self, event: DomainEvent) -> int:
        self._assert_owner()
        with self._lock:
            run = self._connection.execute(
                "SELECT kind, status FROM runs WHERE run_id=?", (event.run_id,)
            ).fetchone()
            if run is None:
                raise RecorderError(f"unknown run {event.run_id!r}")
            event.validate_for_run(RunKind(run["kind"]))
            if RunKind(run["kind"]) is RunKind.OBSERVED:
                self._validate_observation_sources(event)
            content_hash = _content_hash(event)
            existing = self._connection.execute(
                """SELECT recording_cursor, content_hash FROM events
                   WHERE run_id=? AND source_id=? AND source_event_id=?""",
                (event.run_id, event.source_id, event.source_event_id),
            ).fetchone()
            if existing is not None:
                if existing["content_hash"] != content_hash:
                    raise IdempotencyConflict(
                        f"source identity {event.source_id}/{event.source_event_id} has different content"
                    )
                return int(existing["recording_cursor"])
            if run["status"] != RunStatus.OPEN.value:
                raise SealedRunError(f"run {event.run_id!r} is sealed; new events require an amendment run")
            self._validate_objects(event.run_id, event.objects)
            stored = event.with_recorded_time()
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                cursor = self._insert_event(stored, content_hash)
                self._insert_objects(cursor, stored.objects)
                self._insert_evidence(cursor, stored.run_id, stored.evidence_refs)
                if stored.activity_id is not None:
                    self._rebuild_activity_projection(stored.run_id, stored.activity_id)
                self._connection.execute("COMMIT")
            except Exception:
                self._connection.execute("ROLLBACK")
                raise
        for subscriber in self._subscribers:
            try:
                subscriber(cursor, stored)
            except Exception as exc:  # committed history is authoritative
                self._subscriber_errors.append(exc)
        return cursor

    def _validate_objects(self, run_id: str, objects: Iterable[EventObject]) -> None:
        for obj in objects:
            found = self._connection.execute(
                """SELECT 1 FROM entity_registry
                   WHERE object_type=? AND object_id=? AND run_scope IN ('*', ?)""",
                (obj.object_type, obj.object_id, run_id),
            ).fetchone()
            if found is None:
                raise UnknownObjectError(f"unknown {obj.object_type} object {obj.object_id!r}")

    def _validate_observation_sources(self, event: DomainEvent) -> None:
        source_ids = {event.source_id, *(ref.source_id for ref in event.evidence_refs)}
        for source_id in source_ids:
            found = self._connection.execute(
                "SELECT 1 FROM observation_sources WHERE run_id=? AND source_id=?",
                (event.run_id, source_id),
            ).fetchone()
            if found is None:
                raise RecorderError(f"unknown observation source {source_id!r}")

    def _insert_event(self, event: DomainEvent, content_hash: str) -> int:
        values = (
            event.event_id, content_hash, event.schema_version, event.run_id, event.activity,
            event.lifecycle.value, event.activity_id, event.sim_time_s, _dt(event.occurred_at_utc),
            _dt(event.recorded_at_utc), event.source_id, event.source_event_id,
            event.evidence.value, event.source_ref, event.source_offset_s,
            event.correction_of_event_id, _json(event.payload),
        )
        cursor = self._connection.execute(
            """INSERT INTO events(
                 event_id, content_hash, schema_version, run_id, activity, lifecycle,
                 activity_id, sim_time_s, occurred_at_utc, recorded_at_utc, source_id,
                 source_event_id, evidence, source_ref, source_offset_s,
                 correction_of_event_id, payload_json
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            values,
        )
        return int(cursor.lastrowid)

    def _insert_objects(self, cursor: int, objects: Iterable[EventObject]) -> None:
        self._connection.executemany(
            "INSERT INTO event_objects VALUES (?, ?, ?, ?)",
            ((cursor, obj.object_type, obj.object_id, obj.qualifier) for obj in objects),
        )

    def _insert_evidence(
        self, cursor: int, run_id: str, evidence_refs: Iterable[EvidenceReference]
    ) -> None:
        self._connection.executemany(
            """INSERT INTO event_evidence(
                 recording_cursor,evidence_index,run_id,source_id,clip_start_offset_s,
                 clip_end_offset_s,confidence,observation_kind,notes
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ((cursor, index, run_id, ref.source_id, ref.clip_start_offset_s,
              ref.clip_end_offset_s, ref.confidence, ref.observation_kind,
              ref.notes) for index, ref in enumerate(evidence_refs)),
        )

    def _rebuild_activity_projection(self, run_id: str, activity_id: str) -> None:
        rows = self._connection.execute(
            """SELECT recording_cursor, activity, lifecycle, source_id, sim_time_s,
                      occurred_at_utc, source_offset_s
               FROM events WHERE run_id=? AND activity_id=?
               ORDER BY
                 CASE WHEN sim_time_s IS NOT NULL THEN sim_time_s END,
                 CASE WHEN occurred_at_utc IS NOT NULL THEN occurred_at_utc END,
                 CASE WHEN source_offset_s IS NOT NULL THEN source_offset_s END,
                 recording_cursor""",
            (run_id, activity_id),
        ).fetchall()
        sources = {row["source_id"] for row in rows}
        clock_kinds = {
            "simulation" if row["sim_time_s"] is not None
            else "wall_clock" if row["occurred_at_utc"] is not None
            else "source_offset"
            for row in rows
        }
        if len(sources) != 1 or len(clock_kinds) != 1:
            raise RecorderError("one activity cannot mix sources or unaligned clock types")
        lifecycles = [Lifecycle(row["lifecycle"]) for row in rows]
        self._validate_transition_sequence(lifecycles)
        times: dict[Lifecycle, str | None] = {}
        for row in rows:
            lifecycle = Lifecycle(row["lifecycle"])
            raw = row["sim_time_s"]
            if raw is None:
                raw = row["occurred_at_utc"] or row["source_offset_s"]
            times[lifecycle] = None if raw is None else str(raw)
        state = lifecycles[-1].value
        last = rows[-1]
        self._connection.execute(
            """INSERT INTO activities(activity_id, run_id, activity_type, current_state,
                   request_time, start_time, end_time, last_event_cursor)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(activity_id) DO UPDATE SET
                   current_state=excluded.current_state,
                   request_time=excluded.request_time,
                   start_time=excluded.start_time,
                   end_time=excluded.end_time,
                   last_event_cursor=excluded.last_event_cursor""",
            (
                activity_id, run_id, last["activity"], state,
                times.get(Lifecycle.REQUEST), times.get(Lifecycle.START),
                times.get(Lifecycle.COMPLETE) or times.get(Lifecycle.CANCEL),
                max(row["recording_cursor"] for row in rows),
            ),
        )

    @staticmethod
    def _validate_transition_sequence(sequence: list[Lifecycle]) -> None:
        allowed = {
            (Lifecycle.REQUEST,),
            (Lifecycle.REQUEST, Lifecycle.START),
            (Lifecycle.REQUEST, Lifecycle.START, Lifecycle.COMPLETE),
            (Lifecycle.REQUEST, Lifecycle.START, Lifecycle.CANCEL),
            (Lifecycle.REQUEST, Lifecycle.CANCEL),
            (Lifecycle.START,),
            (Lifecycle.START, Lifecycle.COMPLETE),
            (Lifecycle.START, Lifecycle.CANCEL),
            (Lifecycle.COMPLETE,),  # partial observation
            (Lifecycle.CANCEL,),  # partial observation
        }
        if tuple(sequence) not in allowed:
            raise RecorderError(f"unsupported activity lifecycle sequence: {[x.value for x in sequence]}")

    def events_after(self, run_id: str, cursor: int = 0) -> list[sqlite3.Row]:
        self._assert_owner()
        return self._connection.execute(
            "SELECT * FROM events WHERE run_id=? AND recording_cursor>? ORDER BY recording_cursor",
            (run_id, cursor),
        ).fetchall()

    def integrity_check(self) -> str:
        self._assert_owner()
        foreign_keys = self._connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_keys:
            raise RecorderError(f"foreign-key violations: {foreign_keys}")
        return str(self._connection.execute("PRAGMA integrity_check").fetchone()[0])


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _dt(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(timezone.utc).isoformat()


def _content_hash(event: DomainEvent) -> str:
    data = asdict(event)
    data.pop("event_id", None)
    data.pop("recorded_at_utc", None)
    for name in ("lifecycle", "evidence"):
        value = data[name]
        data[name] = value.value if hasattr(value, "value") else value
    for name in ("occurred_at_utc",):
        value = data[name]
        data[name] = _dt(value)
    canonical = _json(data).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
