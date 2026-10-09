from __future__ import annotations

import math
import unittest
from datetime import datetime, timezone

from operations.domain.events import DomainEvent, EventObject, Lifecycle
from operations.domain.models import (
    Channel,
    Container,
    Evidence,
    FulfillmentMode,
    Order,
    OrderLine,
    Product,
    RunKind,
)


class DomainValidationTests(unittest.TestCase):
    def test_order_channels_and_fulfillment_are_independent(self) -> None:
        order = Order(
            "order:online-pickup", "run:test", Channel.ONLINE,
            FulfillmentMode.TAKEAWAY,
        )
        self.assertEqual(order.channel, Channel.ONLINE)
        self.assertEqual(order.fulfillment_mode, FulfillmentMode.TAKEAWAY)

    def test_order_line_requires_product_xor_offer(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly one"):
            OrderLine("line:1", "order:1", 1, "portion")
        line = OrderLine(
            "line:offer", "order:1", 1, "offer", offer_id="offer:picada",
            offer_version="v1", unit_price_cop=50000,
        )
        self.assertIsNone(line.product_id)
        self.assertEqual(line.unit_price_cop, 50000)

    def test_unknown_values_remain_none(self) -> None:
        product = Product("product:morcilla", "Morcilla", "food", "portion")
        self.assertIsNone(product.default_price_cop)
        self.assertIsNone(product.portion_mass_g)

    def test_cop_amounts_must_be_integers(self) -> None:
        with self.assertRaisesRegex(ValueError, "integer COP"):
            Product("product:morcilla", "Morcilla", "food", "portion", 1.5)  # type: ignore[arg-type]

    def test_invalid_ids_and_nonfinite_numbers_fail(self) -> None:
        with self.assertRaisesRegex(ValueError, "stable ASCII"):
            Product("morcilla con espacio", "Morcilla", "food", "portion")
        with self.assertRaisesRegex(ValueError, "finite"):
            DomainEvent.create(
                schema_version="ops_event_v1", run_id="run:test", activity="pick",
                lifecycle=Lifecycle.INSTANT, source_id="sim", source_event_id="bad",
                evidence=Evidence.SYNTHETIC, sim_time_s=math.inf,
            )

    def test_container_cannot_parent_itself(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot contain itself"):
            Container("container:1", "run:test", "bag", "container:1")

    def test_clock_rules_are_run_specific(self) -> None:
        event = DomainEvent.create(
            schema_version="ops_event_v1", run_id="run:test", activity="arrival",
            lifecycle=Lifecycle.INSTANT, source_id="sim", source_event_id="arrival:1",
            evidence=Evidence.SYNTHETIC, sim_time_s=0,
            objects=(EventObject("visit", "visit:1", "subject"),),
        )
        event.validate_for_run(RunKind.SIMULATED)
        with self.assertRaisesRegex(ValueError, "observed events"):
            event.validate_for_run(RunKind.OBSERVED)

        observed = DomainEvent.create(
            schema_version="ops_event_v1", run_id="run:obs", activity="arrival",
            lifecycle=Lifecycle.INSTANT, source_id="manual", source_event_id="line:1",
            evidence=Evidence.OBSERVED,
            occurred_at_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        observed.validate_for_run(RunKind.OBSERVED)

    def test_instant_events_cannot_claim_activity_correlation(self) -> None:
        with self.assertRaisesRegex(ValueError, "instant events"):
            DomainEvent.create(
                schema_version="ops_event_v1", run_id="run:test", activity="arrival",
                lifecycle=Lifecycle.INSTANT, activity_id="activity:wrong",
                source_id="sim", source_event_id="arrival:1",
                evidence=Evidence.SYNTHETIC, sim_time_s=0,
            )


if __name__ == "__main__":
    unittest.main()
