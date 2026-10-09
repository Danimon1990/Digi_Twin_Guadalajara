"""SQLite persistence for operational events and projections."""

from .recorder import EventRecorder, IdempotencyConflict, RecorderError

__all__ = ["EventRecorder", "IdempotencyConflict", "RecorderError"]
