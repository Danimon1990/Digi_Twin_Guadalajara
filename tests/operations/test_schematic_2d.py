from __future__ import annotations

import tempfile
import unittest
import sqlite3
from pathlib import Path

from operations.adapters import export_schematic_2d
from operations.engine.simulation import run_scenario


ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "config/operations/synthetic_test.json"
LAYOUT = ROOT / "config/operations/layout_2d_schematic.json"
VISUAL_SCENARIO = ROOT / "config/operations/three_order_visual_test.json"
BLENDER_LAYOUT = ROOT / "config/operations/layout_2d_blender.json"


class Schematic2DTests(unittest.TestCase):
    def test_export_contains_only_requested_run_and_is_self_contained(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            database = root / "simulation.sqlite3"
            output = root / "playback.html"
            run_scenario(SCENARIO, database, seed=42, run_id="run:visual_test")
            run_scenario(SCENARIO, database, seed=42, run_id="run:other")

            result = export_schematic_2d(
                database, "run:visual_test", LAYOUT, output
            )
            html = output.read_text(encoding="utf-8")

            self.assertEqual(result.event_count, 86)
            self.assertEqual(result.stop_time_s, 52)
            self.assertIn("run:visual_test", html)
            self.assertNotIn("run:other", html)
            self.assertIn("schematic_not_measured", html)
            self.assertIn("resource:morcilla_access_2p", html)
            self.assertIn('"order_id":"run:visual_test.order:001"', html)
            self.assertIn('"product_name":"Morcilla / rellena"', html)
            self.assertIn("const workerTracks =", html)
            self.assertIn("const getLocation =", html)
            self.assertNotIn("const location =", html)
            self.assertNotIn("__SIMULATION_DATA__", html)
            self.assertNotIn("__LAYOUT_DATA__", html)

    def test_unknown_run_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            database = root / "simulation.sqlite3"
            run_scenario(SCENARIO, database, seed=42, run_id="run:known")
            with self.assertRaisesRegex(ValueError, "unknown run"):
                export_schematic_2d(
                    database, "run:missing", LAYOUT, root / "playback.html"
                )

    def test_blender_scale_layout_renders_three_non_abandoning_orders(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            database = root / "simulation.sqlite3"
            output = root / "playback.html"
            result = run_scenario(
                VISUAL_SCENARIO, database, seed=42, run_id="run:three_orders"
            )
            exported = export_schematic_2d(
                database, "run:three_orders", BLENDER_LAYOUT, output
            )
            html = output.read_text(encoding="utf-8")

            self.assertEqual(result.incomplete_activity_count, 0)
            self.assertEqual(result.event_count, 190)
            self.assertEqual(exported.stop_time_s, 81)
            self.assertIn('"size_label":"large"', html)
            self.assertIn('"size_label":"small"', html)
            self.assertIn('"size_label":"medium"', html)
            self.assertIn("Blender scene scale", html)
            self.assertIn("separateWorkerPositions", html)
            self.assertIn("shortestRoute", html)
            self.assertIn("Worker distance", html)
            self.assertIn('"display_code":"SO"', html)
            self.assertIn('"display_code":"FR"', html)
            self.assertNotIn('"activity":"visit_abandoned"', html)
            connection = sqlite3.connect(database)
            handoffs = connection.execute(
                """SELECT order_link.object_id, MIN(e.sim_time_s)
                   FROM events e
                   JOIN event_objects order_link USING(recording_cursor)
                   WHERE e.run_id='run:three_orders' AND e.activity='handover'
                     AND e.lifecycle='start' AND order_link.object_type='order'
                   GROUP BY order_link.object_id"""
            ).fetchall()
            payments = dict(connection.execute(
                """SELECT order_link.object_id, MIN(e.sim_time_s)
                   FROM events e
                   JOIN event_objects order_link USING(recording_cursor)
                   WHERE e.run_id='run:three_orders' AND e.activity='payment_confirmed'
                     AND order_link.object_type='order'
                   GROUP BY order_link.object_id"""
            ).fetchall())
            shift_count = connection.execute(
                "SELECT COUNT(*) FROM shifts WHERE run_id='run:three_orders'"
            ).fetchone()[0]
            assignment_count = connection.execute(
                "SELECT COUNT(*) FROM role_assignments WHERE run_id='run:three_orders'"
            ).fetchone()[0]
            connection.close()
            self.assertTrue(all(payments[order_id] <= time for order_id, time in handoffs))
            self.assertEqual(shift_count, 8)
            self.assertEqual(assignment_count, 8)


if __name__ == "__main__":
    unittest.main()
