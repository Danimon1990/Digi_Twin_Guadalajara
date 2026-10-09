from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import simpy


@dataclass(frozen=True, slots=True)
class ServiceRequest:
    request_id: str
    requested_at_s: float
    duration_s: float


@dataclass(frozen=True, slots=True)
class ServiceInterval:
    request_id: str
    requested_at_s: float
    started_at_s: float
    completed_at_s: float

    @property
    def wait_s(self) -> float:
        return self.started_at_s - self.requested_at_s


def simulate_capacity_resource(
    requests: Iterable[ServiceRequest], *, capacity: int = 1
) -> list[ServiceInterval]:
    """Small engine-level probe used to verify resource scheduling semantics."""
    env = simpy.Environment()
    resource = simpy.Resource(env, capacity=capacity)
    results: list[ServiceInterval] = []

    def serve(item: ServiceRequest):
        yield env.timeout(item.requested_at_s)
        requested = env.now
        with resource.request() as claim:
            yield claim
            started = env.now
            yield env.timeout(item.duration_s)
            results.append(ServiceInterval(
                item.request_id, requested, started, env.now
            ))

    for request in requests:
        env.process(serve(request))
    env.run()
    return sorted(results, key=lambda item: item.request_id)
