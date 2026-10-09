from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$")
UNIT_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_./-]{0,31}$")


def require_id(value: str, field: str = "id") -> str:
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise ValueError(f"{field} must be a stable ASCII identifier")
    return value


def optional_id(value: str | None, field: str) -> str | None:
    if value is not None:
        require_id(value, field)
    return value


def require_unit(value: str, field: str = "unit") -> str:
    if not isinstance(value, str) or not UNIT_PATTERN.fullmatch(value):
        raise ValueError(f"{field} must be an explicit ASCII unit")
    return value


def finite_nonnegative(value: float | int | Decimal, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(f"{field} must be numeric")
    if not math.isfinite(float(value)) or value < 0:
        raise ValueError(f"{field} must be finite and non-negative")


def require_cop(value: int, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer COP amount")


def aware_utc(value: datetime | None, field: str) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(timezone.utc)


def validate_json_value(value: Any, path: str = "payload") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} contains a non-finite number")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            validate_json_value(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path} keys must be strings")
            validate_json_value(item, f"{path}.{key}")
        return
    raise ValueError(f"{path} contains non-JSON value {type(value).__name__}")
