from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import CoverageInterval, ObservationSource, SourceAlignment
from ..domain.events import DomainEvent, EventObject, EvidenceReference, Lifecycle
from ..domain.models import Evidence, Run, RunKind, RunStatus
from ..storage.recorder import EventRecorder


@dataclass(frozen=True, slots=True)
class ImportErrorDetail:
    line_number: int
    message: str


@dataclass(frozen=True, slots=True)
class ImportResult:
    accepted_lines: int
    event_lines: int
    errors: tuple[ImportErrorDetail, ...]
    run_ids: tuple[str, ...]


def _datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamps must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def import_jsonl(
    input_path: str | Path,
    database: str | Path,
    *,
    seal: bool = False,
) -> ImportResult:
    accepted = 0
    event_lines = 0
    errors: list[ImportErrorDetail] = []
    run_ids: list[str] = []
    current_run_id: str | None = None

    with EventRecorder(database) as recorder:
        for line_number, text in enumerate(
            Path(input_path).read_text(encoding="utf-8").splitlines(), 1
        ):
            if not text.strip():
                continue
            try:
                raw = json.loads(text)
                record_type = raw["record_type"]
                if record_type == "run":
                    current_run_id = raw["run_id"]
                    existing = recorder.run_info(current_run_id)
                    if existing is None:
                        recorder.create_run(Run(
                            run_id=current_run_id,
                            kind=RunKind.OBSERVED,
                            scenario_id=raw.get("scenario_id", "scenario:observed_service"),
                            status=RunStatus.OPEN,
                            schema_version="ops_db_v2",
                            model_version=raw.get("model_version", "observation_v1"),
                            layout_version=raw.get("layout_version", "architecture_v1"),
                            effective_config=raw.get("effective_config", {}),
                            created_at_utc=_datetime(raw.get("created_at_utc"))
                            or datetime.now(timezone.utc),
                            source_ref=raw.get("source_ref"),
                            parent_run_id=raw.get("parent_run_id"),
                            is_test=bool(raw.get("is_test", False)),
                        ))
                    else:
                        _validate_existing_run(existing, raw)
                    if current_run_id not in run_ids:
                        run_ids.append(current_run_id)
                else:
                    run_id = raw.get("run_id") or current_run_id
                    if run_id is None:
                        raise ValueError("a run record must precede this line")
                    if record_type == "source":
                        recorder.add_observation_source(ObservationSource(
                            run_id=run_id,
                            source_id=raw["source_id"],
                            source_type=raw["source_type"],
                            file_name=raw.get("file_name"),
                            sha256=raw.get("sha256"),
                            viewpoint=raw.get("viewpoint"),
                            visible_zones=tuple(raw.get("visible_zones", [])),
                            timezone=raw.get("timezone"),
                            wall_clock_start_utc=_datetime(raw.get("wall_clock_start_utc")),
                            duration_s=raw.get("duration_s"),
                            notes=raw.get("notes"),
                        ))
                    elif record_type == "alignment":
                        recorder.add_source_alignment(SourceAlignment(
                            run_id=run_id,
                            alignment_id=raw["alignment_id"],
                            source_a_id=raw["source_a_id"],
                            source_b_id=raw["source_b_id"],
                            offset_b_minus_a_s=raw["offset_b_minus_a_s"],
                            method=raw["method"],
                            confidence=raw["confidence"],
                            notes=raw.get("notes"),
                        ))
                    elif record_type == "coverage":
                        recorder.add_coverage_interval(CoverageInterval(
                            run_id=run_id,
                            coverage_id=raw["coverage_id"],
                            source_id=raw["source_id"],
                            start_offset_s=raw["start_offset_s"],
                            end_offset_s=raw["end_offset_s"],
                            state=raw["state"],
                            zones=tuple(raw.get("zones", [])),
                            notes=raw.get("notes"),
                        ))
                    elif record_type == "entity":
                        recorder.register_entity(
                            raw["object_type"], raw["object_id"], run_scope=run_id
                        )
                    elif record_type == "event":
                        _record_event(recorder, run_id, raw)
                        event_lines += 1
                    else:
                        raise ValueError(f"unsupported record_type {record_type!r}")
                accepted += 1
            except Exception as exc:
                errors.append(ImportErrorDetail(line_number, str(exc)))

        if seal and not errors:
            for run_id in run_ids:
                info = recorder.run_info(run_id)
                if info is not None and info["status"] == RunStatus.OPEN.value:
                    recorder.seal_run(run_id, reason="observation_import_sealed")

    return ImportResult(accepted, event_lines, tuple(errors), tuple(run_ids))


def _validate_existing_run(existing: Any, raw: dict[str, Any]) -> None:
    expected = {
        "kind": RunKind.OBSERVED.value,
        "scenario_id": raw.get("scenario_id", "scenario:observed_service"),
        "model_version": raw.get("model_version", "observation_v1"),
        "layout_version": raw.get("layout_version", "architecture_v1"),
        "effective_config_json": json.dumps(
            raw.get("effective_config", {}), sort_keys=True, separators=(",", ":")
        ),
        "source_ref": raw.get("source_ref"),
        "parent_run_id": raw.get("parent_run_id"),
        "is_test": int(bool(raw.get("is_test", False))),
    }
    mismatched = [key for key, value in expected.items() if existing[key] != value]
    if mismatched:
        raise ValueError(
            f"existing run has different content in {', '.join(mismatched)}"
        )


def _record_event(recorder: EventRecorder, run_id: str, raw: dict[str, Any]) -> int:
    refs_raw = raw.get("evidence_refs")
    if refs_raw is None:
        refs_raw = [{
            "source_id": raw["source_id"],
            "clip_start_offset_s": raw.get("source_offset_s"),
            "clip_end_offset_s": raw.get("source_offset_s"),
            "confidence": raw.get("confidence", 1.0),
            "observation_kind": raw.get("observation_kind", "direct"),
        }]
    kwargs: dict[str, Any] = dict(
        schema_version=raw.get("schema_version", "ops_event_v1"),
        run_id=run_id,
        activity=raw["activity"],
        lifecycle=Lifecycle(raw["lifecycle"]),
        activity_id=raw.get("activity_id"),
        occurred_at_utc=_datetime(raw.get("occurred_at_utc")),
        source_id=raw["source_id"],
        source_event_id=raw["source_event_id"],
        source_ref=raw.get("source_ref"),
        source_offset_s=raw.get("source_offset_s"),
        evidence=Evidence(raw.get("evidence", "observed")),
        correction_of_event_id=raw.get("correction_of_event_id"),
        objects=tuple(EventObject(
            item["object_type"], item["object_id"], item["qualifier"]
        ) for item in raw.get("objects", [])),
        evidence_refs=tuple(EvidenceReference(
            source_id=item["source_id"],
            confidence=item["confidence"],
            observation_kind=item.get("observation_kind", "direct"),
            clip_start_offset_s=item.get("clip_start_offset_s"),
            clip_end_offset_s=item.get("clip_end_offset_s"),
            notes=item.get("notes"),
        ) for item in refs_raw),
        payload=raw.get("payload", {}),
    )
    if raw.get("event_id"):
        return recorder.record(DomainEvent(event_id=raw["event_id"], **kwargs))
    return recorder.record(DomainEvent.create(**kwargs))
