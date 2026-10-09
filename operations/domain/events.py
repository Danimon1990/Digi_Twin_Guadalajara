from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from .models import Evidence, RunKind
from .validation import (
    aware_utc,
    finite_nonnegative,
    optional_id,
    require_id,
    require_unit,
    validate_json_value,
)


class Lifecycle(StrEnum):
    REQUEST = "request"
    START = "start"
    COMPLETE = "complete"
    CANCEL = "cancel"
    INSTANT = "instant"


@dataclass(frozen=True, slots=True)
class EventObject:
    object_type: str
    object_id: str
    qualifier: str

    def __post_init__(self) -> None:
        require_id(self.object_type, "object_type")
        require_id(self.object_id, "object_id")
        require_id(self.qualifier, "qualifier")


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    source_id: str
    confidence: float
    observation_kind: str = "direct"
    clip_start_offset_s: float | None = None
    clip_end_offset_s: float | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        require_id(self.source_id, "evidence source_id")
        if not 0 <= self.confidence <= 1:
            raise ValueError("evidence confidence must be between 0 and 1")
        if self.observation_kind not in {"direct", "inferred"}:
            raise ValueError("observation_kind must be direct or inferred")
        for field in ("clip_start_offset_s", "clip_end_offset_s"):
            value = getattr(self, field)
            if value is not None:
                finite_nonnegative(value, field)
        if self.clip_start_offset_s is not None and self.clip_end_offset_s is not None:
            if self.clip_end_offset_s < self.clip_start_offset_s:
                raise ValueError("evidence clip end cannot precede start")


@dataclass(frozen=True, slots=True)
class DomainEvent:
    event_id: str
    schema_version: str
    run_id: str
    activity: str
    lifecycle: Lifecycle
    source_id: str
    source_event_id: str
    evidence: Evidence
    objects: tuple[EventObject, ...] = ()
    evidence_refs: tuple[EvidenceReference, ...] = ()
    payload: dict[str, Any] = field(default_factory=dict)
    activity_id: str | None = None
    sim_time_s: float | None = None
    occurred_at_utc: datetime | None = None
    recorded_at_utc: datetime | None = None
    source_ref: str | None = None
    source_offset_s: float | None = None
    correction_of_event_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("event_id", "schema_version", "run_id", "activity", "source_id", "source_event_id"):
            require_id(getattr(self, name), name)
        optional_id(self.activity_id, "activity_id")
        optional_id(self.correction_of_event_id, "correction_of_event_id")
        for name in ("sim_time_s", "source_offset_s"):
            value = getattr(self, name)
            if value is not None:
                finite_nonnegative(value, name)
        aware_utc(self.occurred_at_utc, "occurred_at_utc")
        aware_utc(self.recorded_at_utc, "recorded_at_utc")
        validate_json_value(self.payload)
        if not isinstance(self.lifecycle, Lifecycle):
            raise ValueError("lifecycle must be a Lifecycle value")
        if not isinstance(self.evidence, Evidence):
            raise ValueError("evidence must be an Evidence value")
        if self.lifecycle is not Lifecycle.INSTANT and self.activity_id is None:
            raise ValueError("multi-stage events require activity_id")
        if self.lifecycle is Lifecycle.INSTANT and self.activity_id is not None:
            raise ValueError("instant events must not set activity_id")
        seen = set()
        for obj in self.objects:
            key = (obj.object_type, obj.object_id, obj.qualifier)
            if key in seen:
                raise ValueError(f"duplicate event object link: {key}")
            seen.add(key)
        evidence_seen = set()
        for ref in self.evidence_refs:
            key = (ref.source_id, ref.clip_start_offset_s)
            if key in evidence_seen:
                raise ValueError(f"duplicate evidence reference: {key}")
            evidence_seen.add(key)
        self._validate_known_payload()

    def _validate_known_payload(self) -> None:
        for key in ("quantity", "duration_s", "wait_s", "amount_cop", "units"):
            if key in self.payload:
                finite_nonnegative(self.payload[key], f"payload.{key}")
        if "quantity" in self.payload and "unit" not in self.payload:
            raise ValueError("payload.unit is required with payload.quantity")
        if "unit" in self.payload:
            require_unit(self.payload["unit"], "payload.unit")

    def validate_for_run(self, kind: RunKind) -> None:
        if kind is RunKind.SIMULATED:
            if self.sim_time_s is None:
                raise ValueError("simulated events require sim_time_s")
            if self.occurred_at_utc is not None:
                raise ValueError("simulated events must not set occurred_at_utc")
        else:
            if self.sim_time_s is not None:
                raise ValueError("observed events must not set sim_time_s")
            if self.occurred_at_utc is None and self.source_offset_s is None:
                raise ValueError("observed events need occurred_at_utc or source_offset_s")

    def with_recorded_time(self, value: datetime | None = None) -> "DomainEvent":
        if self.recorded_at_utc is not None:
            return self
        return replace(self, recorded_at_utc=value or datetime.now(timezone.utc))

    @classmethod
    def create(cls, **kwargs: Any) -> "DomainEvent":
        return cls(event_id=f"evt:{uuid4().hex}", **kwargs)
