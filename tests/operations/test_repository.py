from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from operations.domain.models import (
    Channel,
    Container,
    ContainerContent,
    CustomerVisit,
    Evidence,
    FulfillmentComponent,
    FulfillmentMode,
    MenuOffer,
    OfferComponent,
    Order,
    OrderLine,
    Product,
    Run,
    RunKind,
    RunStatus,
)
from operations.storage.recorder import EventRecorder
from operations.storage.repository import OperationsRepository


class RepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "entities.sqlite3"
        with EventRecorder(self.db) as recorder:
            recorder.create_run(Run(
                "run:test", RunKind.SIMULATED, "scenario:test", RunStatus.OPEN,
                "ops_db_v1", "dispatch_v1", "architecture_v1", {},
                datetime.now(timezone.utc), seed=42, is_test=True,
            ))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_offer_components_do_not_become_revenue_lines(self) -> None:
        with OperationsRepository(self.db) as repo:
            repo.add_product(Product("product:morcilla", "Morcilla", "food", "portion"))
            repo.add_product(Product("product:arepa", "Arepa", "food", "unit"))
            repo.add_offer(MenuOffer("offer:test", "v1", "Synthetic combo", 50000))
            repo.add_offer_component(OfferComponent(
                "offer:test", "v1", "product:morcilla", 2, "portion"
            ))
            repo.add_offer_component(OfferComponent(
                "offer:test", "v1", "product:arepa", 1, "unit"
            ))
            repo.add_visit(CustomerVisit("visit:1", "run:test", party_size=6, queue_participants=1))
            repo.add_order(Order(
                "order:1", "run:test", Channel.WALK_IN, FulfillmentMode.TAKEAWAY,
                visit_id="visit:1",
            ))
            repo.add_order_line(OrderLine(
                "line:1", "order:1", 1, "offer", offer_id="offer:test", offer_version="v1",
                unit_price_cop=50000,
            ))
            repo.add_fulfillment_component(FulfillmentComponent(
                "component:morcilla", "line:1", "product:morcilla", 2, "portion"
            ))
            repo.add_fulfillment_component(FulfillmentComponent(
                "component:arepa", "line:1", "product:arepa", 1, "unit"
            ))
        connection = sqlite3.connect(self.db)
        revenue = connection.execute(
            "SELECT SUM(quantity * unit_price_cop - discount_cop) FROM order_lines"
        ).fetchone()[0]
        components = connection.execute(
            "SELECT COUNT(*) FROM fulfillment_components"
        ).fetchone()[0]
        connection.close()
        self.assertEqual(revenue, 50000)
        self.assertEqual(components, 2)

    def test_component_can_split_across_siblings_but_not_parent(self) -> None:
        with OperationsRepository(self.db) as repo:
            repo.add_product(Product("product:morcilla", "Morcilla", "food", "portion"))
            repo.add_visit(CustomerVisit("visit:1", "run:test"))
            repo.add_order(Order(
                "order:1", "run:test", Channel.WALK_IN, FulfillmentMode.TAKEAWAY,
                visit_id="visit:1",
            ))
            repo.add_order_line(OrderLine(
                "line:1", "order:1", 1, "portion", product_id="product:morcilla"
            ))
            repo.add_fulfillment_component(FulfillmentComponent(
                "component:1", "line:1", "product:morcilla", 2, "portion"
            ))
            repo.add_container(Container("bag:1", "run:test", "bag"))
            repo.add_container(Container("basket:1", "run:test", "basket", "bag:1"))
            repo.add_container(Container("basket:2", "run:test", "basket", "bag:1"))
            repo.add_container_content(ContainerContent(
                "content:1", "basket:1", "component:1", 1, "portion"
            ))
            repo.add_container_content(ContainerContent(
                "content:2", "basket:2", "component:1", 1, "portion"
            ))
            with self.assertRaises(sqlite3.IntegrityError):
                repo.add_container_content(ContainerContent(
                    "content:3", "bag:1", "component:1", 1, "portion"
                ))


if __name__ == "__main__":
    unittest.main()
