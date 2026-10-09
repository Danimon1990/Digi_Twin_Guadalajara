from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime

from ..domain.validation import aware_utc, finite_nonnegative, require_id


@dataclass(frozen=True, slots=True)
class ObservationSource:
    run_id: str
    source_id: str
    source_type: str
    file_name: str | None = None
    sha256: str | None = None
    viewpoint: str | None = None
    visible_zones: tuple[str, ...] = ()
    timezone: str | None = None
    wall_clock_start_utc: datetime | None = None
    duration_s: float | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        require_id(self.run_id, "run_id")
        require_id(self.source_id, "source_id")
        if self.source_type not in {"camera_video", "manual", "other"}:
            raise ValueError("unsupported observation source_type")
        if self.sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", self.sha256):
            raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
        for zone in self.visible_zones:
            require_id(zone, "visible_zone")
        aware_utc(self.wall_clock_start_utc, "wall_clock_start_utc")
        if self.duration_s is not None:
            finite_nonnegative(self.duration_s, "duration_s")


@dataclass(frozen=True, slots=True)
class SourceAlignment:
    run_id: str
    alignment_id: str
    source_a_id: str
    source_b_id: str
    offset_b_minus_a_s: float
    method: str
    confidence: float
    notes: str | None = None

    def __post_init__(self) -> None:
        for field in ("run_id", "alignment_id", "source_a_id", "source_b_id"):
            require_id(getattr(self, field), field)
        if not math.isfinite(self.offset_b_minus_a_s):
            raise ValueError("offset_b_minus_a_s must be finite")
        if not math.isfinite(self.confidence) or not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class CoverageInterval:
    run_id: str
    coverage_id: str
    source_id: str
    start_offset_s: float
    end_offset_s: float
    state: str
    zones: tuple[str, ...]
    notes: str | None = None

    def __post_init__(self) -> None:
        for field in ("run_id", "coverage_id", "source_id"):
            require_id(getattr(self, field), field)
        finite_nonnegative(self.start_offset_s, "start_offset_s")
        finite_nonnegative(self.end_offset_s, "end_offset_s")
        if self.end_offset_s < self.start_offset_s:
            raise ValueError("coverage end cannot precede start")
        if self.state not in {"visible", "partial", "occluded", "missing"}:
            raise ValueError("unsupported coverage state")
        for zone in self.zones:
            require_id(zone, "coverage zone")
