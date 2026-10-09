from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from .validation import (
    aware_utc,
    finite_nonnegative,
    optional_id,
    require_cop,
    require_id,
    require_unit,
    validate_json_value,
)


class RunKind(StrEnum):
    SIMULATED = "simulated"
    OBSERVED = "observed"


class RunStatus(StrEnum):
    OPEN = "open"
    SEALED = "sealed"
    INTERRUPTED = "interrupted"


class Evidence(StrEnum):
    SYNTHETIC = "synthetic"
    OBSERVED = "observed"
    REPORTED = "reported"
    INFERRED = "inferred"


class Channel(StrEnum):
    WALK_IN = "walk_in"
    ONLINE = "online"
    PHONE = "phone"


class FulfillmentMode(StrEnum):
    DINE_IN = "dine_in"
    TAKEAWAY = "takeaway"
    DELIVERY = "delivery"


class Role(StrEnum):
    ORDER_SERVER = "ORDER_SERVER"
    CASHIER = "CASHIER"
    FRY_OPERATOR = "FRY_OPERATOR"
    SOUP_SERVER = "SOUP_SERVER"
    RUNNER = "RUNNER"
    SUPPORT = "SUPPORT"


class OrderState(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class Run:
    run_id: str
    kind: RunKind
    scenario_id: str
    status: RunStatus
    schema_version: str
    model_version: str
    layout_version: str
    effective_config: dict[str, Any]
    created_at_utc: datetime
    seed: int | None = None
    source_ref: str | None = None
    parent_run_id: str | None = None
    is_test: bool = False
    analysis_cutoff_s: float | None = None
    stopped_at_utc: datetime | None = None
    stop_reason: str | None = None

    def __post_init__(self) -> None:
        for name in ("run_id", "scenario_id", "schema_version", "model_version", "layout_version"):
            require_id(getattr(self, name), name)
        optional_id(self.parent_run_id, "parent_run_id")
        aware_utc(self.created_at_utc, "created_at_utc")
        aware_utc(self.stopped_at_utc, "stopped_at_utc")
        validate_json_value(self.effective_config, "effective_config")
        if not isinstance(self.kind, RunKind) or not isinstance(self.status, RunStatus):
            raise ValueError("kind and status must use RunKind and RunStatus")
        if self.analysis_cutoff_s is not None:
            finite_nonnegative(self.analysis_cutoff_s, "analysis_cutoff_s")
        if self.kind is RunKind.OBSERVED and self.seed is not None:
            raise ValueError("observed runs cannot have a simulation seed")


@dataclass(frozen=True, slots=True)
class Product:
    product_id: str
    name: str
    category: str
    sale_unit: str
    default_price_cop: int | None = None
    portion_mass_g: float | None = None
    portion_mass_evidence: Evidence | None = None
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_id(self.product_id, "product_id")
        require_unit(self.sale_unit, "sale_unit")
        if self.default_price_cop is not None:
            require_cop(self.default_price_cop, "default_price_cop")
        if self.portion_mass_g is not None:
            finite_nonnegative(self.portion_mass_g, "portion_mass_g")
            if self.portion_mass_evidence is None:
                raise ValueError("portion_mass_evidence is required with portion_mass_g")


@dataclass(frozen=True, slots=True)
class MenuOffer:
    offer_id: str
    version: str
    name: str
    price_cop: int | None = None

    def __post_init__(self) -> None:
        require_id(self.offer_id, "offer_id")
        require_id(self.version, "version")
        if self.price_cop is not None:
            require_cop(self.price_cop, "price_cop")


@dataclass(frozen=True, slots=True)
class OfferComponent:
    offer_id: str
    offer_version: str
    product_id: str
    quantity: float
    unit: str
    choice_group: str | None = None

    def __post_init__(self) -> None:
        require_id(self.offer_id, "offer_id")
        require_id(self.offer_version, "offer_version")
        require_id(self.product_id, "product_id")
        finite_nonnegative(self.quantity, "quantity")
        if self.quantity == 0:
            raise ValueError("quantity must be positive")
        require_unit(self.unit)


@dataclass(frozen=True, slots=True)
class Worker:
    worker_id: str
    eligible_roles: frozenset[Role]
    display_code: str | None = None

    def __post_init__(self) -> None:
        require_id(self.worker_id, "worker_id")
        if not self.eligible_roles:
            raise ValueError("eligible_roles cannot be empty")


@dataclass(frozen=True, slots=True)
class Shift:
    shift_id: str
    run_id: str
    worker_id: str
    planned_start_s: float | None = None
    planned_end_s: float | None = None
    observed_start_utc: datetime | None = None
    observed_end_utc: datetime | None = None
    breaks: tuple[tuple[float, float], ...] = ()

    def __post_init__(self) -> None:
        for name in ("shift_id", "run_id", "worker_id"):
            require_id(getattr(self, name), name)
        for name in ("planned_start_s", "planned_end_s"):
            value = getattr(self, name)
            if value is not None:
                finite_nonnegative(value, name)
        aware_utc(self.observed_start_utc, "observed_start_utc")
        aware_utc(self.observed_end_utc, "observed_end_utc")
        for index, interval in enumerate(self.breaks):
            if len(interval) != 2:
                raise ValueError(f"breaks[{index}] must contain start and end")
            finite_nonnegative(interval[0], f"breaks[{index}].start")
            finite_nonnegative(interval[1], f"breaks[{index}].end")
            if interval[1] < interval[0]:
                raise ValueError(f"breaks[{index}] ends before it starts")
        if self.planned_start_s is not None and self.planned_end_s is not None:
            if self.planned_end_s < self.planned_start_s:
                raise ValueError("planned_end_s cannot precede planned_start_s")
        if self.observed_start_utc is not None and self.observed_end_utc is not None:
            if self.observed_end_utc < self.observed_start_utc:
                raise ValueError("observed_end_utc cannot precede observed_start_utc")


@dataclass(frozen=True, slots=True)
class RoleAssignment:
    assignment_id: str
    run_id: str
    worker_id: str
    role: Role
    start_s: float | None = None
    end_s: float | None = None
    station_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("assignment_id", "run_id", "worker_id"):
            require_id(getattr(self, name), name)
        optional_id(self.station_id, "station_id")
        for name in ("start_s", "end_s"):
            value = getattr(self, name)
            if value is not None:
                finite_nonnegative(value, name)
        if self.start_s is not None and self.end_s is not None and self.end_s < self.start_s:
            raise ValueError("end_s cannot precede start_s")


@dataclass(frozen=True, slots=True)
class Station:
    station_id: str
    zone_id: str
    layout_version: str
    usd_prim_path: str | None = None
    access_points: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("station_id", "zone_id", "layout_version"):
            require_id(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class Resource:
    resource_id: str
    station_id: str | None
    resource_type: str
    capacity: int
    available: bool = True
    evidence: Evidence = Evidence.SYNTHETIC

    def __post_init__(self) -> None:
        require_id(self.resource_id, "resource_id")
        optional_id(self.station_id, "station_id")
        if isinstance(self.capacity, bool) or not isinstance(self.capacity, int) or self.capacity < 1:
            raise ValueError("capacity must be a positive integer")


@dataclass(frozen=True, slots=True)
class CustomerVisit:
    visit_id: str
    run_id: str
    party_size: int | None = None
    queue_participants: int | None = None
    arrival_s: float | None = None
    departure_s: float | None = None
    outcome: str | None = None

    def __post_init__(self) -> None:
        require_id(self.visit_id, "visit_id")
        require_id(self.run_id, "run_id")
        for name in ("party_size", "queue_participants"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 1):
                raise ValueError(f"{name} must be a positive integer or null")
        for name in ("arrival_s", "departure_s"):
            value = getattr(self, name)
            if value is not None:
                finite_nonnegative(value, name)
        if self.arrival_s is not None and self.departure_s is not None:
            if self.departure_s < self.arrival_s:
                raise ValueError("departure_s cannot precede arrival_s")


@dataclass(frozen=True, slots=True)
class Queue:
    queue_id: str
    queue_type: str

    def __post_init__(self) -> None:
        require_id(self.queue_id, "queue_id")


@dataclass(frozen=True, slots=True)
class QueueVisit:
    queue_visit_id: str
    run_id: str
    queue_id: str
    visit_id: str | None = None
    order_id: str | None = None
    entered_s: float | None = None
    service_start_s: float | None = None
    departure_s: float | None = None
    outcome: str | None = None

    def __post_init__(self) -> None:
        for name in ("queue_visit_id", "run_id", "queue_id"):
            require_id(getattr(self, name), name)
        optional_id(self.visit_id, "visit_id")
        optional_id(self.order_id, "order_id")
        if self.visit_id is None and self.order_id is None:
            raise ValueError("queue visit needs a visit_id or order_id")
        for name in ("entered_s", "service_start_s", "departure_s"):
            value = getattr(self, name)
            if value is not None:
                finite_nonnegative(value, name)
        known = [x for x in (self.entered_s, self.service_start_s, self.departure_s) if x is not None]
        if known != sorted(known):
            raise ValueError("queue visit times are not chronological")


@dataclass(frozen=True, slots=True)
class Order:
    order_id: str
    run_id: str
    channel: Channel
    fulfillment_mode: FulfillmentMode
    visit_id: str | None = None
    primary_server_id: str | None = None
    preparation_state: OrderState = OrderState.PENDING
    payment_state: OrderState = OrderState.PENDING
    fulfillment_state: OrderState = OrderState.PENDING

    def __post_init__(self) -> None:
        require_id(self.order_id, "order_id")
        require_id(self.run_id, "run_id")
        optional_id(self.visit_id, "visit_id")
        optional_id(self.primary_server_id, "primary_server_id")


@dataclass(frozen=True, slots=True)
class OrderLine:
    line_id: str
    order_id: str
    quantity: float
    unit: str
    product_id: str | None = None
    offer_id: str | None = None
    offer_version: str | None = None
    unit_price_cop: int | None = None
    discount_cop: int = 0
    selected_options: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_id(self.line_id, "line_id")
        require_id(self.order_id, "order_id")
        optional_id(self.product_id, "product_id")
        optional_id(self.offer_id, "offer_id")
        optional_id(self.offer_version, "offer_version")
        if (self.product_id is None) == (self.offer_id is None):
            raise ValueError("exactly one of product_id or offer_id is required")
        if (self.offer_id is None) != (self.offer_version is None):
            raise ValueError("offer_id and offer_version must be supplied together")
        finite_nonnegative(self.quantity, "quantity")
        if self.quantity == 0:
            raise ValueError("quantity must be positive")
        require_unit(self.unit)
        validate_json_value(self.selected_options, "selected_options")
        if self.unit_price_cop is not None:
            require_cop(self.unit_price_cop, "unit_price_cop")
        require_cop(self.discount_cop, "discount_cop")


@dataclass(frozen=True, slots=True)
class FulfillmentComponent:
    component_id: str
    line_id: str
    product_id: str
    required_quantity: float
    unit: str

    def __post_init__(self) -> None:
        for name in ("component_id", "line_id", "product_id"):
            require_id(getattr(self, name), name)
        finite_nonnegative(self.required_quantity, "required_quantity")
        if self.required_quantity == 0:
            raise ValueError("required_quantity must be positive")
        require_unit(self.unit)


@dataclass(frozen=True, slots=True)
class ActivityInstance:
    activity_id: str
    run_id: str
    activity_type: str
    state: str
    order_id: str | None = None
    component_id: str | None = None
    worker_id: str | None = None
    role: Role | None = None
    request_s: float | None = None
    start_s: float | None = None
    end_s: float | None = None
    quantity: float | None = None
    unit: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        require_id(self.activity_id, "activity_id")
        require_id(self.run_id, "run_id")
        for name in ("order_id", "component_id", "worker_id"):
            optional_id(getattr(self, name), name)
        if self.quantity is not None:
            finite_nonnegative(self.quantity, "quantity")
            if self.unit is None:
                raise ValueError("unit is required with quantity")
        if self.unit is not None:
            require_unit(self.unit)
        for name in ("request_s", "start_s", "end_s"):
            value = getattr(self, name)
            if value is not None:
                finite_nonnegative(value, name)


@dataclass(frozen=True, slots=True)
class ResourceAllocation:
    allocation_id: str
    run_id: str
    resource_id: str
    activity_id: str
    units: int
    acquired_s: float | None = None
    released_s: float | None = None

    def __post_init__(self) -> None:
        for name in ("allocation_id", "run_id", "resource_id", "activity_id"):
            require_id(getattr(self, name), name)
        if isinstance(self.units, bool) or not isinstance(self.units, int) or self.units < 1:
            raise ValueError("units must be a positive integer")
        for name in ("acquired_s", "released_s"):
            value = getattr(self, name)
            if value is not None:
                finite_nonnegative(value, name)
        if self.acquired_s is not None and self.released_s is not None:
            if self.released_s < self.acquired_s:
                raise ValueError("released_s cannot precede acquired_s")


@dataclass(frozen=True, slots=True)
class Container:
    container_id: str
    run_id: str
    container_type: str
    parent_container_id: str | None = None
    packaging_state: str = "open"

    def __post_init__(self) -> None:
        require_id(self.container_id, "container_id")
        require_id(self.run_id, "run_id")
        optional_id(self.parent_container_id, "parent_container_id")
        if self.parent_container_id == self.container_id:
            raise ValueError("a container cannot contain itself")


@dataclass(frozen=True, slots=True)
class ContainerContent:
    content_id: str
    container_id: str
    component_id: str
    quantity: float
    unit: str

    def __post_init__(self) -> None:
        for name in ("content_id", "container_id", "component_id"):
            require_id(getattr(self, name), name)
        finite_nonnegative(self.quantity, "quantity")
        if self.quantity == 0:
            raise ValueError("quantity must be positive")
        require_unit(self.unit)


@dataclass(frozen=True, slots=True)
class Payment:
    payment_id: str
    run_id: str
    amount_cop: int
    method: str
    status: str
    cashier_id: str | None = None
    register_resource_id: str | None = None
    confirmed_s: float | None = None

    def __post_init__(self) -> None:
        require_id(self.payment_id, "payment_id")
        require_id(self.run_id, "run_id")
        require_cop(self.amount_cop, "amount_cop")
        optional_id(self.cashier_id, "cashier_id")
        optional_id(self.register_resource_id, "register_resource_id")
        if self.confirmed_s is not None:
            finite_nonnegative(self.confirmed_s, "confirmed_s")


@dataclass(frozen=True, slots=True)
class PaymentAllocation:
    allocation_id: str
    payment_id: str
    order_id: str
    amount_cop: int

    def __post_init__(self) -> None:
        for name in ("allocation_id", "payment_id", "order_id"):
            require_id(getattr(self, name), name)
        require_cop(self.amount_cop, "amount_cop")
