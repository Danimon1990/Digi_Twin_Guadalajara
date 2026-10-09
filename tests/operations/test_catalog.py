from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from operations.domain.catalog import ProductCatalog
from operations.engine.scenario import Scenario
from operations.engine.simulation import run_scenario


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "config/operations/product_catalog.json"
SCENARIO = ROOT / "config/operations/synthetic_test.json"


class ProductCatalogTests(unittest.TestCase):
    def test_catalog_keeps_unknown_prices_null_and_times_replaceable(self) -> None:
        catalog = ProductCatalog.load(CATALOG)
        products = catalog.by_id()
        self.assertEqual(len(products), 7)
        self.assertIsNone(products["product:morcilla"].product.default_price_cop)
        self.assertEqual(products["product:papa_criolla"].product.default_price_cop, 5000)
        for item in products.values():
            self.assertTrue(item.handling_time["replaceable"])
            self.assertEqual(item.handling_time["evidence"], "synthetic")

    def test_scenario_embeds_catalog_snapshot(self) -> None:
        scenario = Scenario.load(SCENARIO)
        self.assertEqual(len(scenario.config["products"]), 7)
        self.assertEqual(
            scenario.config["product_catalog_snapshot"]["schema_version"],
            "operations_product_catalog_v1",
        )

    def test_product_specific_time_changes_simulated_pick(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
            morcilla = next(
                item for item in catalog["products"]
                if item["product_id"] == "product:morcilla"
            )
            morcilla["handling_time"]["selection_per_unit_s"] = 7
            (root / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
            scenario = json.loads(SCENARIO.read_text(encoding="utf-8"))
            scenario["product_catalog_file"] = "catalog.json"
            scenario_path = root / "scenario.json"
            scenario_path.write_text(json.dumps(scenario), encoding="utf-8")
            database = root / "test.sqlite3"
            run_scenario(scenario_path, database, seed=42, run_id="run:catalog_time")
            connection = sqlite3.connect(database)
            payload = connection.execute(
                """SELECT payload_json FROM events e JOIN event_objects o
                     ON o.recording_cursor=e.recording_cursor
                   WHERE e.activity='product_pick' AND e.lifecycle='start'
                     AND o.object_type='product' AND o.object_id='product:morcilla'
                   ORDER BY e.sim_time_s LIMIT 1"""
            ).fetchone()[0]
            papa_price = connection.execute(
                "SELECT default_price_cop FROM products WHERE product_id='product:papa_criolla'"
            ).fetchone()[0]
            connection.close()
            self.assertEqual(json.loads(payload)["duration_s"], 15.0)
            self.assertEqual(papa_price, 5000)


if __name__ == "__main__":
    unittest.main()
