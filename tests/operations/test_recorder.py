from __future__ import annotations

import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from operations.domain.events import DomainEvent, EventObject, Lifecycle
from operations.domain.models import Evidence, Run, RunKind, RunStatus
from operations.storage.recorder import (
    EventRecorder,
    IdempotencyConflict,
    RecorderError,
    SealedRunError,
    UnknownObjectError,
)


def simulated_run(run_id: str = "run:test") -> Run:
    return Run(
        run_id=run_id,
        kind=RunKind.SIMULATED,
        scenario_id="scenario:synthetic_test",
        status=RunStatus.OPEN,
        schema_version="ops_db_v1",
        model_version="dispatch_v1",
        layout_version="architecture_v1",
        effective_config={"evidence": "synthetic"},
        seed=42,
        is_test=True,
        created_at_utc=datetime.now(timezone.utc),
    )


def event(
    source_event_id: str,
    lifecycle: Lifecycle = Lifecycle.INSTANT,
    *,
    sim_time_s: float = 0,
    activity_id: str | None = None,
    payload: dict | None = None,
) -> DomainEvent:
    return DomainEvent.create(
        schema_version="ops_event_v1",
        run_id="run:test",
        activity="product_pick" if activity_id else "visit_arrival",
        lifecycle=lifecycle,
        activity_id=activity_id,
        sim_time_s=sim_time_s,
        source_id="sim:dispatch",
        source_event_id=source_event_id,
        evidence=Evidence.SYNTHETIC,
        objects=(EventObject("visit", "visit:1", "subject"),),
        payload=payload or {},
    )


class RecorderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "events.sqlite3"
        self.recorder = EventRecorder(self.db)
        self.recorder.create_run(simulated_run())
        self.recorder.register_entity("visit", "visit:1", run_scope="run:test")

    def tearDown(self) -> None:
        self.recorder.close()
        self.temp.cleanup()

    def test_retry_is_idempotent_and_conflict_is_clear(self) -> None:
        first = event("arrival:1")
        cursor = self.recorder.record(first)
        retry = replace(first, event_id="evt:retry")
        self.assertEqual(self.recorder.record(retry), cursor)
        self.assertEqual(len(self.recorder.events_after("run:test")), 1)
        with self.assertRaises(IdempotencyConflict):
            self.recorder.record(replace(retry, payload={"changed": True}))

    def test_identical_retry_allowed_after_seal_but_new_event_rejected(self) -> None:
        first = event("arrival:1")
        cursor = self.recorder.record(first)
        self.recorder.seal_run("run:test", analysis_cutoff_s=30)
        self.assertEqual(self.recorder.record(replace(first, event_id="evt:retry")), cursor)
        with self.assertRaises(SealedRunError):
            self.recorder.record(event("arrival:2", sim_time_s=2))

    def test_unknown_object_is_rejected(self) -> None:
        bad = replace(
            event("arrival:unknown"),
            objects=(EventObject("worker", "worker:missing", "actor"),),
        )
        with self.assertRaises(UnknownObjectError):
            self.recorder.record(bad)
        self.assertEqual(self.recorder.events_after("run:test"), [])

    def test_out_of_order_arrival_rebuilds_source_time_projection(self) -> None:
        self.recorder.record(event("pick:complete", Lifecycle.COMPLETE,
                                   sim_time_s=10, activity_id="activity:pick1"))
        self.recorder.record(event("pick:start", Lifecycle.START,
                                   sim_time_s=3, activity_id="activity:pick1"))
        connection = sqlite3.connect(self.db)
        row = connection.execute(
            "SELECT current_state, start_time, end_time FROM activities"
        ).fetchone()
        connection.close()
        self.assertEqual(row, ("complete", "3.0", "10.0"))

    def test_unsupported_transition_rolls_back_event_and_links(self) -> None:
        self.recorder.record(event("pick:start", Lifecycle.START,
                                   sim_time_s=1, activity_id="activity:pick1"))
        with self.assertRaises(RecorderError):
            self.recorder.record(event("pick:request", Lifecycle.REQUEST,
                                       sim_time_s=2, activity_id="activity:pick1"))
        self.assertEqual(len(self.recorder.events_after("run:test")), 1)

    def test_subscriber_failure_does_not_unwrite_event(self) -> None:
        def fail(_cursor: int, _event: DomainEvent) -> None:
            raise RuntimeError("viewer unavailable")

        self.recorder.subscribe(fail)
        cursor = self.recorder.record(event("arrival:1"))
        self.assertEqual(self.recorder.events_after("run:test")[0]["recording_cursor"], cursor)
        self.assertEqual(len(self.recorder.subscriber_errors), 1)

    def test_database_reopens_with_history_and_integrity(self) -> None:
        self.recorder.record(event("arrival:1"))
        self.assertEqual(self.recorder.integrity_check(), "ok")
        self.recorder.close()
        self.recorder = EventRecorder(self.db)
        self.assertEqual(len(self.recorder.events_after("run:test")), 1)

    def test_second_history_writer_is_rejected(self) -> None:
        with self.assertRaisesRegex(RecorderError, "active writer"):
            EventRecorder(self.db)


if __name__ == "__main__":
    unittest.main()
