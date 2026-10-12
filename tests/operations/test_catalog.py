from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from operations.domain.catalog import ProductCatalog
from operations.domain.pricing import MenuPriceCatalog
from operations.engine.scenario import Scenario
from operations.engine.simulation import run_scenario


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "config/operations/product_catalog.json"
PRICES = ROOT / "config/operations/menu_prices.json"
SCENARIO = ROOT / "config/operations/synthetic_test.json"


class ProductCatalogTests(unittest.TestCase):
    def test_catalog_keeps_unknown_prices_null_and_times_replaceable(self) -> None:
        catalog = ProductCatalog.load(CATALOG)
        products = catalog.by_id()
        self.assertEqual(len(products), 14)
        self.assertIsNone(products["product:morcilla"].product.default_price_cop)
        self.assertIsNone(products["product:papa_criolla"].product.default_price_cop)
        self.assertEqual(products["product:gallina"].product.name, "Gallina")
        self.assertEqual(
            products["product:costilla_cerdo"].product.name, "Costilla de cerdo"
        )
        for item in products.values():
            self.assertTrue(item.handling_time["replaceable"])
            self.assertEqual(item.handling_time["evidence"], "synthetic")

    def test_scenario_embeds_catalog_snapshot(self) -> None:
        scenario = Scenario.load(SCENARIO)
        self.assertEqual(len(scenario.config["products"]), 14)
        self.assertEqual(
            scenario.config["product_catalog_snapshot"]["schema_version"],
            "operations_product_catalog_v2",
        )
        self.assertEqual(
            scenario.config["menu_price_catalog_snapshot"]["schema_version"],
            "operations_menu_price_catalog_v1",
        )

    def test_corrected_price_catalog_has_no_unconfirmed_numeric_prices(self) -> None:
        catalog = MenuPriceCatalog.load(PRICES)
        self.assertEqual(len(catalog.items), 14)
        self.assertTrue(all(item.price_cop is None for item in catalog.items))
        self.assertTrue(all(
            item.price_status == "pending_confirmation" for item in catalog.items
        ))

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
            scenario["menu_price_catalog_file"] = str(PRICES)
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
            self.assertIsNone(papa_price)

    def test_confirmed_menu_prices_drive_line_and_payment_amounts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prices = json.loads(PRICES.read_text(encoding="utf-8"))
            confirmed = {
                "sale:morcilla:portion": 6000,
                "sale:chicharron:portion": 10000,
                "sale:arepa:unit": 2000,
            }
            for item in prices["items"]:
                if item["sale_option_id"] in confirmed:
                    item["price_cop"] = confirmed[item["sale_option_id"]]
                    item["price_status"] = "confirmed"
                    item["price_source_ref"] = "test:confirmed_menu"
            price_path = root / "prices.json"
            price_path.write_text(json.dumps(prices), encoding="utf-8")
            scenario = json.loads(SCENARIO.read_text(encoding="utf-8"))
            scenario["product_catalog_file"] = str(CATALOG)
            scenario["menu_price_catalog_file"] = str(price_path)
            scenario_path = root / "scenario.json"
            scenario_path.write_text(json.dumps(scenario), encoding="utf-8")
            database = root / "priced.sqlite3"
            run_scenario(scenario_path, database, seed=42, run_id="run:priced")
            connection = sqlite3.connect(database)
            totals = [json.loads(row[0])["amount_cop"] for row in connection.execute(
                """SELECT payload_json FROM events
                   WHERE activity='payment_confirmed' ORDER BY sim_time_s"""
            ).fetchall()]
            line_prices = [row[0] for row in connection.execute(
                "SELECT unit_price_cop FROM order_lines ORDER BY line_id"
            ).fetchall()]
            connection.close()
            self.assertEqual(sorted(totals), [10000, 22000])
            self.assertEqual(sorted(line_prices), [2000, 6000, 6000, 10000])


if __name__ == "__main__":
    unittest.main()
