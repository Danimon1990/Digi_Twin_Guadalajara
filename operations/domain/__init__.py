"""Domain records and event contracts."""

from .events import DomainEvent, EventObject
from .models import *  # noqa: F403

__all__ = ["DomainEvent", "EventObject"]
