from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ..domain.models import (
    Container,
    ContainerContent,
    CustomerVisit,
    FulfillmentComponent,
    MenuOffer,
    OfferComponent,
    Order,
    OrderLine,
    Payment,
    PaymentAllocation,
    Product,
    Queue,
    QueueVisit,
    Resource,
    RoleAssignment,
    Shift,
    Station,
    Worker,
)


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class OperationsRepository:
    """Typed entity writer used during run/scenario setup.

    The event recorder remains the only operational-history write path. This
    repository registers static and run-scoped identities so events cannot link
    to invented objects.
    """

    def __init__(self, database: str | Path) -> None:
        self.connection = sqlite3.connect(str(database))
        self.connection.execute("PRAGMA foreign_keys = ON")

    def __enter__(self) -> "OperationsRepository":
        return self

    def __exit__(self, *args: object) -> None:
        if args and args[0] is not None:
            self.connection.rollback()
        else:
            self.connection.commit()
        self.connection.close()

    def _register(self, object_type: str, object_id: str, run_scope: str = "*") -> None:
        self.connection.execute(
            "INSERT OR IGNORE INTO entity_registry VALUES (?, ?, ?)",
            (run_scope, object_type, object_id),
        )

    def _insert_static_exact(
        self, table: str, columns: tuple[str, ...], values: tuple[object, ...],
        key_columns: tuple[str, ...],
    ) -> None:
        placeholders = ", ".join("?" for _ in values)
        column_sql = ", ".join(columns)
        self.connection.execute(
            f"INSERT OR IGNORE INTO {table} ({column_sql}) VALUES ({placeholders})",
            values,
        )
        key_indexes = [columns.index(column) for column in key_columns]
        where = " AND ".join(f"{column}=?" for column in key_columns)
        existing = self.connection.execute(
            f"SELECT {column_sql} FROM {table} WHERE {where}",
            tuple(values[index] for index in key_indexes),
        ).fetchone()
        if existing is None or tuple(existing) != values:
            key = ", ".join(str(values[index]) for index in key_indexes)
            raise ValueError(f"conflicting static definition for {table}: {key}")

    def add_product(self, value: Product) -> None:
        self.connection.execute(
            """INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(product_id) DO UPDATE SET
                 name=excluded.name,
                 category=excluded.category,
                 sale_unit=excluded.sale_unit,
                 default_price_cop=excluded.default_price_cop,
                 portion_mass_g=excluded.portion_mass_g,
                 portion_mass_evidence=excluded.portion_mass_evidence,
                 tags_json=excluded.tags_json""",
            (value.product_id, value.name, value.category, value.sale_unit,
             value.default_price_cop, value.portion_mass_g,
             value.portion_mass_evidence.value if value.portion_mass_evidence else None,
             _json(value.tags)),
        )
        self._register("product", value.product_id)

    def add_offer(self, value: MenuOffer) -> None:
        self.connection.execute(
            "INSERT INTO menu_offers VALUES (?, ?, ?, ?)",
            (value.offer_id, value.version, value.name, value.price_cop),
        )
        self._register("offer", value.offer_id)

    def add_offer_component(self, value: OfferComponent) -> None:
        self.connection.execute(
            "INSERT INTO offer_components VALUES (?, ?, ?, ?, ?, ?)",
            (value.offer_id, value.offer_version, value.product_id, value.quantity,
             value.unit, value.choice_group),
        )

    def add_worker(self, value: Worker) -> None:
        self._insert_static_exact(
            "workers", ("worker_id", "eligible_roles_json", "display_code"),
            (value.worker_id, _json(sorted(role.value for role in value.eligible_roles)),
             value.display_code), ("worker_id",),
        )
        self._register("worker", value.worker_id)

    def add_station(self, value: Station) -> None:
        self._insert_static_exact(
            "stations",
            ("station_id", "zone_id", "layout_version", "usd_prim_path", "access_points_json"),
            (value.station_id, value.zone_id, value.layout_version, value.usd_prim_path,
             _json(value.access_points)), ("station_id",),
        )
        self._register("station", value.station_id)

    def add_resource(self, value: Resource) -> None:
        self._insert_static_exact(
            "resources",
            ("resource_id", "station_id", "resource_type", "capacity", "available", "evidence"),
            (value.resource_id, value.station_id, value.resource_type, value.capacity,
             int(value.available), value.evidence.value), ("resource_id",),
        )
        self._register("resource", value.resource_id)

    def add_shift(self, value: Shift) -> None:
        self.connection.execute(
            "INSERT INTO shifts VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (value.shift_id, value.run_id, value.worker_id, value.planned_start_s,
             value.planned_end_s,
             value.observed_start_utc.isoformat() if value.observed_start_utc else None,
             value.observed_end_utc.isoformat() if value.observed_end_utc else None,
             _json(value.breaks)),
        )
        self._register("shift", value.shift_id, value.run_id)

    def add_role_assignment(self, value: RoleAssignment) -> None:
        self.connection.execute(
            "INSERT INTO role_assignments VALUES (?, ?, ?, ?, ?, ?, ?)",
            (value.assignment_id, value.run_id, value.worker_id, value.role.value,
             value.station_id, value.start_s, value.end_s),
        )
        self._register("role_assignment", value.assignment_id, value.run_id)

    def add_visit(self, value: CustomerVisit) -> None:
        self.connection.execute(
            "INSERT INTO visits VALUES (?, ?, ?, ?, ?, ?, ?)",
            (value.visit_id, value.run_id, value.party_size, value.queue_participants,
             value.arrival_s, value.departure_s, value.outcome),
        )
        self._register("visit", value.visit_id, value.run_id)

    def add_queue(self, value: Queue) -> None:
        self._insert_static_exact(
            "queues", ("queue_id", "queue_type"),
            (value.queue_id, value.queue_type), ("queue_id",),
        )
        self._register("queue", value.queue_id)

    def add_order(self, value: Order) -> None:
        self.connection.execute(
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (value.order_id, value.run_id, value.visit_id, value.channel.value,
             value.fulfillment_mode.value, value.primary_server_id,
             value.preparation_state.value, value.payment_state.value,
             value.fulfillment_state.value),
        )
        self._register("order", value.order_id, value.run_id)

    def add_queue_visit(self, value: QueueVisit) -> None:
        self.connection.execute(
            "INSERT INTO queue_visits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (value.queue_visit_id, value.run_id, value.queue_id, value.visit_id,
             value.order_id, value.entered_s, value.service_start_s,
             value.departure_s, value.outcome),
        )
        self._register("queue_visit", value.queue_visit_id, value.run_id)

    def add_order_line(self, value: OrderLine) -> None:
        self.connection.execute(
            "INSERT INTO order_lines VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (value.line_id, value.order_id, value.product_id, value.offer_id, value.offer_version,
             value.quantity, value.unit, value.unit_price_cop, value.discount_cop,
             _json(value.selected_options)),
        )
        run_id = self.connection.execute(
            "SELECT run_id FROM orders WHERE order_id=?", (value.order_id,)
        ).fetchone()[0]
        self._register("order_line", value.line_id, run_id)

    def add_fulfillment_component(self, value: FulfillmentComponent) -> None:
        self.connection.execute(
            "INSERT INTO fulfillment_components VALUES (?, ?, ?, ?, ?)",
            (value.component_id, value.line_id, value.product_id,
             value.required_quantity, value.unit),
        )
        run_id = self.connection.execute(
            """SELECT o.run_id FROM orders o JOIN order_lines l ON l.order_id=o.order_id
               WHERE l.line_id=?""", (value.line_id,)
        ).fetchone()[0]
        self._register("component", value.component_id, run_id)

    def add_container(self, value: Container) -> None:
        self.connection.execute(
            "INSERT INTO containers VALUES (?, ?, ?, ?, ?)",
            (value.container_id, value.run_id, value.container_type,
             value.parent_container_id, value.packaging_state),
        )
        self._register("container", value.container_id, value.run_id)

    def add_container_content(self, value: ContainerContent) -> None:
        self.connection.execute(
            "INSERT INTO container_contents VALUES (?, ?, ?, ?, ?)",
            (value.content_id, value.container_id, value.component_id,
             value.quantity, value.unit),
        )

    def add_payment(self, value: Payment) -> None:
        self.connection.execute(
            "INSERT INTO payments VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (value.payment_id, value.run_id, value.cashier_id,
             value.register_resource_id, value.amount_cop, value.method,
             value.status, value.confirmed_s),
        )
        self._register("payment", value.payment_id, value.run_id)

    def add_payment_allocation(self, value: PaymentAllocation) -> None:
        self.connection.execute(
            "INSERT INTO payment_allocations VALUES (?, ?, ?, ?)",
            (value.allocation_id, value.payment_id, value.order_id, value.amount_cop),
        )
