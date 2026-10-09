from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from operations.adapters import export_schematic_2d
from operations.engine.simulation import run_scenario


ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "config/operations/synthetic_test.json"
LAYOUT = ROOT / "config/operations/layout_2d_schematic.json"


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

            self.assertEqual(result.event_count, 84)
            self.assertEqual(result.stop_time_s, 52)
            self.assertIn("run:visual_test", html)
            self.assertNotIn("run:other", html)
            self.assertIn("schematic_not_measured", html)
            self.assertIn("resource:morcilla_access_2p", html)
            self.assertIn('"orders":["run:visual_test.order:001"', html)
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


if __name__ == "__main__":
    unittest.main()
