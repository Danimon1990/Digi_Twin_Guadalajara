from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from operations.capture.importer import import_jsonl
from operations.storage.recorder import EventRecorder


RUN_ID = "run:observed_test"


def line(record_type: str, **values: object) -> str:
    return json.dumps({"record_type": record_type, **values})


class ObservationImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "observations.sqlite3"
        self.input = self.root / "observations.jsonl"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write(self, lines: list[str]) -> None:
        self.input.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def base_lines(self) -> list[str]:
        return [
            line(
                "run",
                run_id=RUN_ID,
                scenario_id="scenario:observed_test",
                is_test=True,
                effective_config={"timezone": "America/Bogota"},
            ),
            line(
                "source",
                source_id="source:cam_a",
                source_type="camera_video",
                file_name="cam_a.mp4",
                visible_zones=["zone:queue"],
                timezone="America/Bogota",
                duration_s=60,
            ),
            line(
                "source",
                source_id="source:cam_b",
                source_type="camera_video",
                file_name="cam_b.mp4",
                visible_zones=["zone:counter"],
                timezone="America/Bogota",
                duration_s=60,
            ),
            line(
                "alignment",
                alignment_id="alignment:a_b",
                source_a_id="source:cam_a",
                source_b_id="source:cam_b",
                offset_b_minus_a_s=0.25,
                method="sync_clap",
                confidence=0.9,
            ),
            line(
                "coverage",
                coverage_id="coverage:a_full",
                source_id="source:cam_a",
                start_offset_s=0,
                end_offset_s=60,
                state="visible",
                zones=["zone:queue"],
            ),
            line("entity", object_type="visit", object_id="visit:V001"),
        ]

    def event_line(self, *, payload: dict[str, object] | None = None) -> str:
        return line(
            "event",
            activity="ordering_queue",
            lifecycle="complete",
            activity_id="activity:queue_V001",
            source_id="source:cam_a",
            source_event_id="queue_complete:V001",
            source_offset_s=15.0,
            evidence="observed",
            objects=[{
                "object_type": "visit",
                "object_id": "visit:V001",
                "qualifier": "subject",
            }],
            evidence_refs=[
                {
                    "source_id": "source:cam_a",
                    "clip_start_offset_s": 13,
                    "clip_end_offset_s": 17,
                    "confidence": 0.95,
                    "observation_kind": "direct",
                },
                {
                    "source_id": "source:cam_b",
                    "clip_start_offset_s": 13.25,
                    "clip_end_offset_s": 17.25,
                    "confidence": 0.75,
                    "observation_kind": "direct",
                },
            ],
            payload=payload or {"missing_start": True},
        )

    def test_imports_sources_alignment_coverage_partial_event_and_evidence(self) -> None:
        self.write(self.base_lines() + [self.event_line()])
        result = import_jsonl(self.input, self.db)
        self.assertEqual(result.errors, ())
        self.assertEqual(result.event_lines, 1)

        connection = sqlite3.connect(self.db)
        counts = tuple(connection.execute(
            """SELECT
                 (SELECT COUNT(*) FROM observation_sources),
                 (SELECT COUNT(*) FROM source_alignments),
                 (SELECT COUNT(*) FROM observation_coverage),
                 (SELECT COUNT(*) FROM events),
                 (SELECT COUNT(*) FROM event_evidence)"""
        ).fetchone())
        activity = connection.execute(
            "SELECT current_state,start_time,end_time FROM activities"
        ).fetchone()
        version = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
        connection.close()

        self.assertEqual(counts, (2, 1, 1, 1, 2))
        self.assertEqual(activity, ("complete", None, "15.0"))
        self.assertEqual(version, 2)

    def test_retry_is_idempotent_and_conflicting_event_is_reported(self) -> None:
        self.write(self.base_lines() + [self.event_line()])
        first = import_jsonl(self.input, self.db)
        retry = import_jsonl(self.input, self.db)
        self.assertEqual(first.errors, ())
        self.assertEqual(retry.errors, ())

        self.write(self.base_lines() + [self.event_line(payload={"changed": True})])
        conflict = import_jsonl(self.input, self.db)
        self.assertEqual(len(conflict.errors), 1)
        self.assertIn("different content", conflict.errors[0].message)
        connection = sqlite3.connect(self.db)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM events").fetchone()[0], 1)
        connection.close()

    def test_malformed_line_does_not_discard_later_valid_lines_or_seal_run(self) -> None:
        lines = self.base_lines()
        lines.insert(1, "{not-json")
        lines.append(self.event_line())
        self.write(lines)
        result = import_jsonl(self.input, self.db, seal=True)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.errors[0].line_number, 2)

        connection = sqlite3.connect(self.db)
        event_count = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        status = connection.execute(
            "SELECT status FROM runs WHERE run_id=?", (RUN_ID,)
        ).fetchone()[0]
        connection.close()
        self.assertEqual(event_count, 1)
        self.assertEqual(status, "open")

    def test_version_one_database_migrates_without_losing_history(self) -> None:
        schema = Path(__file__).parents[2] / "operations" / "storage" / "schema.sql"
        connection = sqlite3.connect(self.db)
        connection.executescript(schema.read_text(encoding="utf-8"))
        connection.execute(
            "INSERT INTO schema_migrations(version,applied_at_utc) VALUES (1,?)",
            ("2026-10-08T00:00:00+00:00",),
        )
        connection.commit()
        connection.close()

        with EventRecorder(self.db) as recorder:
            self.assertEqual(recorder.integrity_check(), "ok")
        connection = sqlite3.connect(self.db)
        tables = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        version = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
        connection.close()
        self.assertIn("observation_sources", tables)
        self.assertIn("event_evidence", tables)
        self.assertEqual(version, 2)
        self.assertTrue(
            Path(f"{self.db}.pre_v2_from_v1.sqlite3").exists(),
            "a v1 backup must exist before the migration",
        )


if __name__ == "__main__":
    unittest.main()
