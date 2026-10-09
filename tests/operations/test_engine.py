from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from operations.domain.models import RunStatus
from operations.engine.resources import ServiceRequest, simulate_capacity_resource
from operations.engine.simulation import run_scenario


ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "config/operations/synthetic_test.json"


class ResourceEngineTests(unittest.TestCase):
    def test_capacity_one_exact_schedule(self) -> None:
        intervals = simulate_capacity_resource([
            ServiceRequest("a", 0, 10),
            ServiceRequest("b", 3, 12),
        ])
        self.assertEqual(
            [(x.started_at_s, x.completed_at_s, x.wait_s) for x in intervals],
            [(0, 10, 0), (10, 22, 7)],
        )


class DispatchSimulationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "demo.sqlite3"
        self.result = run_scenario(SCENARIO, self.db, seed=42, run_id="run:test_sim")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def rows(self, sql: str, parameters: tuple = ()) -> list[sqlite3.Row]:
        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        result = connection.execute(sql, parameters).fetchall()
        connection.close()
        return result

    def test_full_run_is_persisted_and_sealed(self) -> None:
        self.assertEqual(self.result.status, RunStatus.SEALED)
        self.assertEqual(self.result.incomplete_activity_count, 0)
        self.assertGreater(self.result.event_count, 0)
        self.assertEqual(self.rows("PRAGMA integrity_check")[0][0], "ok")

    def test_shared_morcilla_resource_allows_two_workers_without_exceeding_capacity(self) -> None:
        rows = self.rows(
            """SELECT e.activity_id, e.lifecycle, e.sim_time_s
               FROM events e JOIN event_objects o
                 ON o.recording_cursor=e.recording_cursor
               WHERE o.object_type='resource' AND o.object_id='resource:morcilla_access_2p'
               ORDER BY e.sim_time_s, e.recording_cursor"""
        )
        intervals: dict[str, dict[str, float]] = {}
        for row in rows:
            intervals.setdefault(row["activity_id"], {})[row["lifecycle"]] = row["sim_time_s"]
        occupied = [(x["start"], x["complete"]) for x in intervals.values()]
        boundaries = sorted({value for interval in occupied for value in interval})
        concurrency = [
            sum(start <= point < end for start, end in occupied)
            for point in boundaries
        ]
        self.assertEqual(max(concurrency), 2)
        self.assertLessEqual(max(concurrency), 2)

    def test_worker_attention_activities_do_not_overlap(self) -> None:
        rows = self.rows(
            """SELECT o.object_id AS worker_id,e.activity_id,e.lifecycle,e.sim_time_s
               FROM events e JOIN event_objects o
                 ON o.recording_cursor=e.recording_cursor
               WHERE o.object_type='worker' AND e.lifecycle IN ('start','complete')
                 AND e.activity NOT IN ('ordering_queue')
               ORDER BY o.object_id,e.sim_time_s,e.recording_cursor"""
        )
        by_worker: dict[str, dict[str, dict[str, float]]] = {}
        for row in rows:
            by_worker.setdefault(row["worker_id"], {}).setdefault(
                row["activity_id"], {}
            )[row["lifecycle"]] = row["sim_time_s"]
        for activities in by_worker.values():
            intervals = sorted((x["start"], x["complete"]) for x in activities.values())
            self.assertTrue(all(a[1] <= b[0] for a, b in zip(intervals, intervals[1:])))

    def test_operational_milestones_are_distinct(self) -> None:
        activities = {row[0] for row in self.rows(
            """SELECT DISTINCT e.activity FROM events e JOIN event_objects o
                 ON o.recording_cursor=e.recording_cursor
               WHERE o.object_type='order' AND o.object_id LIKE '%.order:001'"""
        )}
        expected = {
            "product_pick", "cutting", "seasoning", "basket_splitting",
            "packaging", "order_ready", "handover", "payment",
            "payment_confirmed", "server_released",
        }
        self.assertTrue(expected.issubset(activities))

    def test_abandonment_needs_no_order_and_party_does_not_create_orders(self) -> None:
        self.assertEqual(self.rows("SELECT COUNT(*) FROM visits")[0][0], 3)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM orders")[0][0], 2)
        abandon = self.rows(
            """SELECT e.recording_cursor FROM events e JOIN event_objects o
                 ON o.recording_cursor=e.recording_cursor
               WHERE e.activity='visit_abandoned' AND o.object_type='visit'
                 AND o.object_id LIKE '%.visit:003'"""
        )
        self.assertEqual(len(abandon), 1)

    def test_cashier_assistance_uses_capacity_without_sales(self) -> None:
        rows = self.rows(
            "SELECT activity, lifecycle, payload_json FROM events WHERE activity IN ('cashier_assistance','payment_confirmed')"
        )
        assistance = [json.loads(row["payload_json"])["amount_cop"] for row in rows
                      if row["activity"] == "cashier_assistance"]
        receipts = [json.loads(row["payload_json"])["amount_cop"] for row in rows
                    if row["activity"] == "payment_confirmed"]
        self.assertEqual(set(assistance), {0})
        self.assertEqual(sum(receipts), 80000)

    def test_chicharron_separation_rule_is_explicit(self) -> None:
        payloads = [json.loads(row[0]) for row in self.rows(
            "SELECT payload_json FROM events WHERE activity='packaging' AND lifecycle='start'"
        )]
        self.assertEqual(payloads, [{
            "duration_s": 5.0,
            "role": "ORDER_SERVER",
            "separate_chicharron": True,
        }])

    def test_same_seed_reproduces_logical_history(self) -> None:
        other = Path(self.temp.name) / "repeat.sqlite3"
        run_scenario(SCENARIO, other, seed=42, run_id="run:test_sim")

        def logical(path: Path):
            connection = sqlite3.connect(path)
            rows = connection.execute(
                """SELECT activity,lifecycle,activity_id,sim_time_s,source_event_id,payload_json
                   FROM events ORDER BY recording_cursor"""
            ).fetchall()
            connection.close()
            return rows

        self.assertEqual(logical(self.db), logical(other))

    def test_two_runs_can_share_one_database(self) -> None:
        second = run_scenario(SCENARIO, self.db, seed=42, run_id="run:test_sim_2")
        self.assertEqual(second.status, RunStatus.SEALED)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM runs")[0][0], 2)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM visits")[0][0], 6)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM orders")[0][0], 4)

    def test_cutoff_preserves_incomplete_work(self) -> None:
        config = json.loads(SCENARIO.read_text(encoding="utf-8"))
        config["stop_time_s"] = 10
        config["product_catalog_file"] = str(ROOT / "config/operations/product_catalog.json")
        short_path = Path(self.temp.name) / "short.json"
        short_path.write_text(json.dumps(config), encoding="utf-8")
        short_db = Path(self.temp.name) / "short.sqlite3"
        result = run_scenario(short_path, short_db, seed=42, run_id="run:short")
        self.assertEqual(result.status, RunStatus.INTERRUPTED)
        self.assertGreater(result.incomplete_activity_count, 0)
        connection = sqlite3.connect(short_db)
        maximum = connection.execute("SELECT MAX(sim_time_s) FROM events").fetchone()[0]
        connection.close()
        self.assertLessEqual(maximum, 10)

    def test_server_can_be_configured_to_wait_for_payment(self) -> None:
        config = json.loads(SCENARIO.read_text(encoding="utf-8"))
        config["product_catalog_file"] = str(ROOT / "config/operations/product_catalog.json")
        config["relationships"] = {
            "payment_start": "after_ready",
            "server_release": "after_payment",
        }
        path = Path(self.temp.name) / "relationships.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        database = Path(self.temp.name) / "relationships.sqlite3"
        run_scenario(path, database, seed=42, run_id="run:relationships")
        connection = sqlite3.connect(database)
        paid = connection.execute(
            """SELECT sim_time_s FROM events WHERE activity='payment_confirmed'
               ORDER BY sim_time_s LIMIT 1"""
        ).fetchone()[0]
        released = connection.execute(
            """SELECT sim_time_s FROM events WHERE activity='server_released'
               ORDER BY sim_time_s LIMIT 1"""
        ).fetchone()[0]
        connection.close()
        self.assertGreaterEqual(released, paid)


if __name__ == "__main__":
    unittest.main()
