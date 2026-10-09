from __future__ import annotations

import random
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
    Run,
    RunKind,
    RunStatus,
    Station,
    Worker,
)
from ..storage.recorder import EventRecorder
from ..storage.repository import OperationsRepository
from .scenario import Scenario


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
            self._instant("order_created", [("order", order_id, "subject"),
                                              ("visit", visit_id, "source")])
            for line in order["lines"]:
                yield from self._select_product(order_id, worker_id, line)
            self._instant("items_selected", [("order", order_id, "subject")])
            yield from self._timed_with_resource(
                "cutting", order_id, worker_id, "resource:cutting",
                self._duration("cutting_s"), Role.ORDER_SERVER,
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
            if relationships["server_release"] == "after_ready":
                release_worker()
            if worker_released:
                yield from self._timed_without_worker(
                    "handover", order_id, self._duration("handover_s")
                )
            else:
                yield from self._timed("handover", order_id, worker_id,
                                       self._duration("handover_s"))
            if relationships["payment_start"] == "after_handover":
                payment_process = self.env.process(self._payment(order, visit_id))
            if relationships["server_release"] == "after_handover":
                release_worker()
            elif relationships["server_release"] == "after_payment":
                yield payment_process
                release_worker()
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
        duration = float(timing["selection_setup_s"]) + (
            float(line["quantity"]) * float(timing["selection_per_unit_s"])
        )
        payload = {"quantity": line["quantity"], "unit": line["unit"]}
        yield from self._timed_with_resource(
            "product_pick", order_id, worker_id, resource_id, duration,
            Role.ORDER_SERVER, payload, product_id=product_id,
        )
        yield from self._timed("product_deposit", order_id, worker_id,
                               self._duration("deposit_s"), payload=payload,
                               product_id=product_id)

    def _payment(self, order: dict[str, Any], visit_id: str):
        delay = self._duration("payment_delay_s")
        yield self.env.timeout(delay)
        cashier_id = self.config["cashier_worker_id"]
        worker_claim = self.worker_attention[cashier_id].request()
        yield worker_claim
        try:
            yield from self._timed_with_resource(
                "payment", self._instance_id(order["order_id"]), cashier_id, "resource:register",
                self._duration("payment_s"), Role.CASHIER,
                {"amount_cop": order["amount_cop"], "method": "synthetic"},
            )
        finally:
            self.worker_attention[cashier_id].release(worker_claim)
        self._instant("payment_confirmed", [
            ("order", self._instance_id(order["order_id"]), "paid_order"),
            ("visit", visit_id, "customer_visit"),
        ], {"amount_cop": order["amount_cop"]})

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
        activity_id = self._new_activity_id(activity, order_id)
        objects = [("worker", worker_id, "actor")]
        if order_id:
            objects.append(("order", order_id, "subject"))
        if product_id:
            objects.append(("product", product_id, "selected_product"))
        data = {"role": role.value, "duration_s": duration, **(payload or {})}
        self._event(activity, Lifecycle.START, activity_id, objects, data)
        yield self.env.timeout(duration)
        self._event(activity, Lifecycle.COMPLETE, activity_id, objects, data)

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
            self._event(activity, Lifecycle.START, activity_id, objects, data)
            yield self.env.timeout(duration)
            self._event(activity, Lifecycle.COMPLETE, activity_id, objects, data)

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

    def _duration(self, name: str) -> float:
        spec = self.config["durations"][name]
        if isinstance(spec, (int, float)):
            return float(spec)
        if spec.get("distribution") == "uniform":
            return self.rng.uniform(float(spec["min_s"]), float(spec["max_s"]))
        raise ValueError(f"unsupported duration model for {name}")

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
                ))
                repo.add_fulfillment_component(FulfillmentComponent(
                    instance_id(f"component:{order['order_id'].split(':')[-1]}:{index}"), line_id,
                    line["product_id"], line["quantity"], line["unit"],
                ))
