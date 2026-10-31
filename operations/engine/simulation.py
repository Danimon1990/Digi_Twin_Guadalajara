from __future__ import annotations

import random
import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import simpy

from ..domain.events import DomainEvent, EventObject, Lifecycle
from ..domain.models import (
    Channel,
    CustomerVisit,
    Evidence,
    FulfillmentComponent,
    FulfillmentMode,
    Order,
    OrderLine,
    Product,
    Queue,
    Resource,
    Role,
    RoleAssignment,
    Run,
    RunKind,
    RunStatus,
    Station,
    Shift,
    Worker,
)
from ..storage.recorder import EventRecorder
from ..storage.repository import OperationsRepository
from .scenario import Scenario
from ..domain.timing import sample_duration, sample_portions
from .space import FloorSpace, FlexibleSpace


@dataclass(frozen=True, slots=True)
class SimulationResult:
    run_id: str
    database: Path
    stop_time_s: float
    event_count: int
    incomplete_activity_count: int
    status: RunStatus


class DispatchSimulator:
    def __init__(self, scenario: Scenario, recorder: EventRecorder, run_id: str, seed: int) -> None:
        self.scenario = scenario
        self.config = scenario.config
        self.recorder = recorder
        self.run_id = run_id
        self.seed = seed
        self.rng = random.Random(seed)
        self.product_config = {
            item["product_id"]: item for item in self.config["products"]
        }
        self.env = simpy.Environment()
        space_class = FlexibleSpace if self.config.get("space", {}).get("movement_mode") == "flexible" else FloorSpace
        self.floor_space = space_class(self.env, self.config["space"]) if self.config.get("space") else None
        self.server_pool = simpy.FilterStore(self.env)
        self.worker_attention: dict[str, simpy.Resource] = {}
        self.resources: dict[str, simpy.Resource] = {}
        self._source_sequence = 0
        for worker in self.config["workers"]:
            worker_id = worker["worker_id"]
            self.worker_attention[worker_id] = simpy.Resource(self.env, capacity=1)
            if "ORDER_SERVER" in worker["eligible_roles"]:
                self.server_pool.put(worker_id)
        for resource in self.config["resources"]:
            self.resources[resource["resource_id"]] = simpy.Resource(
                self.env, capacity=resource["capacity"]
            )

    def _instance_id(self, local_id: str) -> str:
        return f"{self.run_id}.{local_id}"

    def run(self) -> SimulationResult:
        for visit in self.config["visits"]:
            self.env.process(self._visit_process(visit))
        for task in self.config.get("cashier_assistance", []):
            self.env.process(self._cashier_assistance(task))
        self.env.run(until=self.scenario.stop_time_s)
        incomplete = self._incomplete_count()
        status = RunStatus.INTERRUPTED if incomplete else RunStatus.SEALED
        self.recorder.seal_run(
            self.run_id,
            analysis_cutoff_s=self.scenario.stop_time_s,
            reason="analysis_cutoff" if incomplete else "completed",
            status=status,
        )
        count = len(self.recorder.events_after(self.run_id))
        return SimulationResult(
            self.run_id, Path(self.recorder.database), self.scenario.stop_time_s,
            count, incomplete, status,
        )

    def _visit_process(self, visit: dict[str, Any]):
        yield self.env.timeout(float(visit["arrival_s"]))
        visit_id = self._instance_id(visit["visit_id"])
        self._instant("visit_arrival", [("visit", visit_id, "subject")], {
            "party_size": visit.get("party_size"),
            "queue_participants": visit.get("queue_participants"),
        })
        queue_activity = f"activity:queue:{visit_id}"
        self._event("ordering_queue", Lifecycle.REQUEST, queue_activity,
                    [("visit", visit_id, "subject"), ("queue", "queue:ordering", "queue")])
        server_get = self.server_pool.get()
        outcome = yield server_get | self.env.timeout(float(visit["patience_s"]))
        if server_get not in outcome:
            server_get.cancel()
            self._event("ordering_queue", Lifecycle.CANCEL, queue_activity,
                        [("visit", visit_id, "subject"), ("queue", "queue:ordering", "queue")],
                        {"reason": "abandoned"})
            self._instant("visit_abandoned", [("visit", visit_id, "subject")],
                          {"reason": "ordering_wait_exceeded"})
            return
        worker_id = outcome[server_get]
        self._event("ordering_queue", Lifecycle.START, queue_activity,
                    [("visit", visit_id, "subject"), ("worker", worker_id, "server")])
        self._event("ordering_queue", Lifecycle.COMPLETE, queue_activity,
                    [("visit", visit_id, "subject"), ("worker", worker_id, "server")])
        order = visit["order"]
        order_id = self._instance_id(order["order_id"])
        worker_claim = self.worker_attention[worker_id].request()
        yield worker_claim
        worker_released = False
        workflow_complete = False
        payment_process = None
        service_started_at = float(self.env.now)
        customer_flow = self.config.get("customer_flow", False)
        if customer_flow:
            self._instant("service_assigned", [("order", order_id, "subject"),
                ("visit", visit_id, "customer"), ("worker", worker_id, "server")])

        def release_worker() -> None:
            nonlocal worker_released
            if not worker_released:
                self._instant("server_released", [("order", order_id, "subject"),
                                                    ("worker", worker_id, "server")])
                self.worker_attention[worker_id].release(worker_claim)
                self.server_pool.put(worker_id)
                worker_released = True

        try:
            yield from self._timed("order_taking", order_id, worker_id,
                                   self._duration("order_taking_s"))
            self._instant(
                "order_created",
                [("order", order_id, "subject"), ("visit", visit_id, "source")],
                {"order_size": order.get("size_label")},
            )
            for line in order["lines"]:
                yield from self._select_product(order_id, worker_id, line)
            self._instant("items_selected", [("order", order_id, "subject")])
            cutting_spec = self.config["durations"].get("cutting_per_portion_s")
            cut_quantity = sum(
                float(line["quantity"]) for line in order["lines"]
                if self.product_config[line["product_id"]]["category"] in {"carne", "embutido"}
            )
            cutting_duration = (
                sample_portions(cutting_spec, cut_quantity, self._case_rng(order_id, "cutting")) if cutting_spec is not None and cut_quantity
                else 0.0 if cutting_spec is not None else self._duration("cutting_s")
            )
            yield from self._timed_with_resource(
                "cutting", order_id, worker_id, "resource:cutting",
                cutting_duration, Role.ORDER_SERVER, {"cut_portions": cut_quantity},
            )
            yield from self._timed("seasoning", order_id, worker_id,
                                   self._duration("seasoning_s"))
            yield from self._timed("basket_splitting", order_id, worker_id,
                                   self._duration("basket_splitting_s"))
            if order["fulfillment_mode"] == "takeaway":
                separation = any(line["product_id"] == "product:chicharron"
                                 for line in order["lines"])
                yield from self._timed_with_resource(
                    "packaging", order_id, worker_id, "resource:packing",
                    self._duration("packaging_s"), Role.ORDER_SERVER,
                    {"separate_chicharron": separation},
                )
            self._instant("order_ready", [("order", order_id, "subject")])
            relationships = self.config["relationships"]
            if relationships["payment_start"] == "after_ready":
                payment_process = self.env.process(self._payment(order, visit_id))
            if relationships["server_release"] == "after_ready" and not customer_flow:
                release_worker()
            if relationships.get("handover_start") == "after_payment":
                yield payment_process
            if worker_released:
                yield from self._timed_without_worker(
                    "handover", order_id, self._duration("handover_s")
                )
            else:
                yield from self._timed("handover", order_id, worker_id,
                                       self._duration("handover_s"))
            if relationships["payment_start"] == "after_handover":
                payment_process = self.env.process(self._payment(order, visit_id))
            if relationships["server_release"] == "after_handover" and not customer_flow:
                release_worker()
            elif relationships["server_release"] == "after_payment" and not customer_flow:
                yield payment_process
                release_worker()
            if payment_process is not None and not payment_process.triggered:
                yield payment_process
            if customer_flow:
                self._instant("service_completed", [("order", order_id, "subject"),
                    ("visit", visit_id, "customer"), ("worker", worker_id, "server")],
                    {"service_elapsed_s": float(self.env.now) - service_started_at,
                     "paid": True, "basket_received": True})
            if order["fulfillment_mode"] == "dine_in":
                self._instant(
                    "visit_to_dining",
                    [("visit", visit_id, "subject"), ("order", order_id, "received_order")],
                    {"via": "Mesas_trabajo 1.004", "destination": "comedor"},
                )
            else:
                self._instant(
                    "visit_departure",
                    [("visit", visit_id, "subject"), ("order", order_id, "received_order")],
                    {"destination": "exit"},
                )
            workflow_complete = True
        finally:
            if workflow_complete:
                release_worker()

    def _select_product(self, order_id: str, worker_id: str, line: dict[str, Any]):
        product_id = line["product_id"]
        yield from self._timed("selection_travel", order_id, worker_id,
                               self._duration("travel_s"), payload={"distance_m": None})
        resource_id = line["resource_id"]
        timing = self.product_config[product_id]["handling_time"]
        duration = sample_duration(timing["selection_setup_s"], self._case_rng(order_id, product_id + ":setup")) + sample_portions(
            timing["selection_per_unit_s"], float(line["quantity"]), self._case_rng(order_id, product_id)
        )
        payload = {"quantity": line["quantity"], "unit": line["unit"]}
        handler = line.get("service_worker_id", worker_id)
        claim = None
        if handler != worker_id:
            claim = self.worker_attention[handler].request()
            yield claim
        yield from self._timed_with_resource(
            "product_pick", order_id, handler, resource_id, duration,
            Role.SOUP_SERVER if handler != worker_id else Role.ORDER_SERVER, payload, product_id=product_id,
        )
        if claim is not None:
            self.worker_attention[handler].release(claim)
        yield from self._timed("product_deposit", order_id, worker_id,
                               self._duration("deposit_s"), payload=payload,
                               product_id=product_id)

    def _payment(self, order: dict[str, Any], visit_id: str):
        delay = self._duration("payment_delay_s")
        yield self.env.timeout(delay)
        cashier_id = self.config["cashier_worker_id"]
        order_id = self._instance_id(order["order_id"])
        queue_id = self._new_activity_id("payment_queue", order_id)
        queue_objects = [("order", order_id, "subject"), ("visit", visit_id, "customer")]
        if self.config.get("customer_flow"):
            self._event("payment_queue", Lifecycle.REQUEST, queue_id, queue_objects)
        worker_claim = self.worker_attention[cashier_id].request()
        yield worker_claim
        if self.config.get("customer_flow"):
            self._event("payment_queue", Lifecycle.START, queue_id, queue_objects)
            self._event("payment_queue", Lifecycle.COMPLETE, queue_id, queue_objects)
        payment_payload: dict[str, Any] = {
            "method": "synthetic",
            "pricing_status": order["price_status"],
        }
        if order["amount_cop"] is None:
            payment_payload["amount_missing"] = True
        else:
            payment_payload["amount_cop"] = order["amount_cop"]
        try:
            yield from self._timed_with_resource(
                "payment", self._instance_id(order["order_id"]), cashier_id, "resource:register",
                sample_duration(self.config["durations"]["payment_s"], self._case_rng(self._instance_id(order["order_id"]), "payment")), Role.CASHIER,
                payment_payload,
            )
        finally:
            self.worker_attention[cashier_id].release(worker_claim)
        confirmed_payload = dict(payment_payload)
        self._instant("payment_confirmed", [
            ("order", self._instance_id(order["order_id"]), "paid_order"),
            ("visit", visit_id, "customer_visit"),
        ], confirmed_payload)

    def _cashier_assistance(self, task: dict[str, Any]):
        yield self.env.timeout(float(task["start_s"]))
        cashier_id = self.config["cashier_worker_id"]
        worker_claim = self.worker_attention[cashier_id].request()
        yield worker_claim
        try:
            yield from self._timed_with_resource(
                "cashier_assistance", None, cashier_id, "resource:register",
                float(task["duration_s"]), Role.CASHIER,
                {"reason": task["reason"], "amount_cop": 0},
            )
        finally:
            self.worker_attention[cashier_id].release(worker_claim)

    def _timed(self, activity: str, order_id: str | None, worker_id: str,
               duration: float, role: Role = Role.ORDER_SERVER,
               payload: dict[str, Any] | None = None, product_id: str | None = None):
        if self.floor_space:
            target = self.config["space"]["activity_locations"].get(activity, "aisle")
            yield from self._move_to(worker_id, order_id, target)
        activity_id = self._new_activity_id(activity, order_id)
        objects = [("worker", worker_id, "actor")]
        if order_id:
            objects.append(("order", order_id, "subject"))
        if product_id:
            objects.append(("product", product_id, "selected_product"))
        data = {"role": role.value, "duration_s": duration, **(payload or {})}
        self._event(activity, Lifecycle.START, activity_id, objects, data)
        if self.floor_space:
            self.floor_space.set_busy(worker_id, True)
        yield self.env.timeout(duration)
        self._event(activity, Lifecycle.COMPLETE, activity_id, objects, data)
        if self.floor_space:
            self.floor_space.set_busy(worker_id, False)

    def _timed_without_worker(self, activity: str, order_id: str, duration: float):
        activity_id = self._new_activity_id(activity, order_id)
        objects = [("order", order_id, "subject")]
        data = {"duration_s": duration, "role": None}
        self._event(activity, Lifecycle.START, activity_id, objects, data)
        yield self.env.timeout(duration)
        self._event(activity, Lifecycle.COMPLETE, activity_id, objects, data)

    def _timed_with_resource(
        self, activity: str, order_id: str | None, worker_id: str,
        resource_id: str, duration: float, role: Role,
        payload: dict[str, Any] | None = None, product_id: str | None = None,
    ):
        activity_id = self._new_activity_id(activity, order_id)
        objects = [("worker", worker_id, "actor"), ("resource", resource_id, "required")]
        if order_id:
            objects.append(("order", order_id, "subject"))
        if product_id:
            objects.append(("product", product_id, "selected_product"))
        data = {"role": role.value, "duration_s": duration, **(payload or {})}
        self._event(activity, Lifecycle.REQUEST, activity_id, objects, data)
        with self.resources[resource_id].request() as claim:
            yield claim
            acquired_at = float(self.env.now)
            if self.floor_space:
                self._instant("resource_access_acquired", objects, {"reservation_activity_id": activity_id})
                target = self.config["space"]["resource_locations"].get(resource_id, "aisle")
                yield from self._move_to(worker_id, order_id, target)
            if self.floor_space:
                data = {**data, "resource_acquired_s": acquired_at}
            self._event(activity, Lifecycle.START, activity_id, objects, data)
            if self.floor_space:
                self.floor_space.set_busy(worker_id, True)
            yield self.env.timeout(duration)
            self._event(activity, Lifecycle.COMPLETE, activity_id, objects, data)
            if self.floor_space:
                self.floor_space.set_busy(worker_id, False)

    def _move_to(self, worker_id, order_id, target):
        activity_id = self._new_activity_id("space_wait", order_id)
        objects = [("worker", worker_id, "actor")]
        if order_id:
            objects.append(("order", order_id, "subject"))
        self._event("space_wait", Lifecycle.START, activity_id, objects)
        yield from self.floor_space.move(worker_id, target, self._space_step, order_id)
        self._event("space_wait", Lifecycle.COMPLETE, activity_id, objects)

    def _space_step(self, worker_id, order_id, start, end, duration):
        activity_id = self._new_activity_id("space_move", order_id)
        objects = [("worker", worker_id, "actor")]
        if order_id:
            objects.append(("order", order_id, "subject"))
        payload = {"from_xy_m": start, "to_xy_m": end, "duration_s": duration,
                   "distance_m": self.config["space"]["pitch_m"]}
        self._event("space_move", Lifecycle.START, activity_id, objects, payload)
        yield self.env.timeout(duration)
        self._event("space_move", Lifecycle.COMPLETE, activity_id, objects, payload)

    def _instant(self, activity: str, objects: list[tuple[str, str, str]],
                 payload: dict[str, Any] | None = None) -> None:
        self._event(activity, Lifecycle.INSTANT, None, objects, payload)

    def _event(self, activity: str, lifecycle: Lifecycle, activity_id: str | None,
               objects: list[tuple[str, str, str]], payload: dict[str, Any] | None = None) -> None:
        self._source_sequence += 1
        self.recorder.record(DomainEvent.create(
            schema_version="ops_event_v1", run_id=self.run_id, activity=activity,
            lifecycle=lifecycle, activity_id=activity_id, sim_time_s=float(self.env.now),
            source_id="sim:dispatch", source_event_id=f"event:{self._source_sequence:06d}",
            evidence=Evidence.SYNTHETIC,
            objects=tuple(EventObject(*obj) for obj in objects), payload=payload or {},
        ))

    def _new_activity_id(self, activity: str, order_id: str | None) -> str:
        self._source_sequence += 1
        subject = order_id or "shared"
        return f"activity:{activity}:{subject}:{self._source_sequence:06d}"

    def _case_rng(self, order_id: str, phase: str) -> random.Random:
        local_id = order_id.removeprefix(self.run_id + ".")
        digest = hashlib.sha256(f"{self.seed}:{local_id}:{phase}".encode()).digest()
        return random.Random(int.from_bytes(digest[:8], "big"))

    def _duration(self, name: str) -> float:
        return sample_duration(self.config["durations"][name], self.rng)

    def _incomplete_count(self) -> int:
        connection = sqlite3.connect(self.recorder.database)
        count = connection.execute(
            """SELECT COUNT(*) FROM activities
               WHERE run_id=? AND current_state IN ('request', 'start')""",
            (self.run_id,),
        ).fetchone()[0]
        connection.close()
        return int(count)


def run_scenario(
    scenario_path: str | Path, database: str | Path, *, seed: int = 42,
    run_id: str | None = None,
) -> SimulationResult:
    scenario = Scenario.load(scenario_path)
    database = Path(database)
    database.parent.mkdir(parents=True, exist_ok=True)
    run_id = run_id or f"run:{uuid4().hex}"
    run = Run(
        run_id, RunKind.SIMULATED, scenario.scenario_id, RunStatus.OPEN,
        "ops_db_v2", scenario.model_version, scenario.layout_version,
        scenario.config, datetime.now(timezone.utc), seed=seed, is_test=True,
        source_ref=str(Path(scenario_path)),
    )
    with EventRecorder(database) as recorder:
        recorder.create_run(run)
    try:
        _populate_entities(database, run_id, scenario.config)
    except Exception as exc:
        with EventRecorder(database) as recorder:
            recorder.seal_run(
                run_id, analysis_cutoff_s=0, status=RunStatus.INTERRUPTED,
                reason=f"setup_failed:{type(exc).__name__}",
            )
        raise
    with EventRecorder(database) as recorder:
        return DispatchSimulator(scenario, recorder, run_id, seed).run()


def _populate_entities(database: Path, run_id: str, config: dict[str, Any]) -> None:
    def instance_id(local_id: str) -> str:
        return f"{run_id}.{local_id}"

    with OperationsRepository(database) as repo:
        repo.add_queue(Queue("queue:ordering", "ordering"))
        repo.add_station(Station("station:dispatch", "zone:dispatch", config["layout_version"]))
        for product in config["products"]:
            repo.add_product(Product(
                product["product_id"], product["name"], product["category"],
                product["sale_unit"],
                default_price_cop=product.get("default_price_cop"),
                tags=tuple(product.get("tags", [])),
            ))
        for worker in config["workers"]:
            repo.add_worker(Worker(
                worker["worker_id"], frozenset(Role(role) for role in worker["eligible_roles"]),
                worker.get("display_code"),
            ))
            if config.get("staffing_profile_snapshot"):
                repo.add_shift(Shift(
                    instance_id(f"shift:{worker['worker_id'].split(':')[-1]}"),
                    run_id,
                    worker["worker_id"],
                    planned_start_s=0,
                    planned_end_s=float(config["stop_time_s"]),
                ))
                repo.add_role_assignment(RoleAssignment(
                    instance_id(f"assignment:{worker['worker_id'].split(':')[-1]}"),
                    run_id,
                    worker["worker_id"],
                    Role(worker["primary_role"]),
                    start_s=0,
                    end_s=float(config["stop_time_s"]),
                    station_id="station:dispatch",
                ))
        for resource in config["resources"]:
            repo.add_resource(Resource(
                resource["resource_id"], "station:dispatch", resource["resource_type"],
                resource["capacity"], evidence=Evidence.SYNTHETIC,
            ))
        for visit in config["visits"]:
            repo.add_visit(CustomerVisit(
                instance_id(visit["visit_id"]), run_id, visit.get("party_size"),
                visit.get("queue_participants"), arrival_s=visit["arrival_s"],
            ))
            if "order" not in visit:
                continue
            order = visit["order"]
            repo.add_order(Order(
                instance_id(order["order_id"]), run_id, Channel(order["channel"]),
                FulfillmentMode(order["fulfillment_mode"]),
                visit_id=instance_id(visit["visit_id"]),
            ))
            for index, line in enumerate(order["lines"], 1):
                line_id = instance_id(f"line:{order['order_id'].split(':')[-1]}:{index}")
                repo.add_order_line(OrderLine(
                    line_id, instance_id(order["order_id"]), line["quantity"], line["unit"],
                    product_id=line["product_id"], unit_price_cop=line.get("unit_price_cop"),
                    selected_options={"sale_option_id": line["sale_option_id"]},
                ))
                repo.add_fulfillment_component(FulfillmentComponent(
                    instance_id(f"component:{order['order_id'].split(':')[-1]}:{index}"), line_id,
                    line["product_id"], line["quantity"], line["unit"],
                ))
