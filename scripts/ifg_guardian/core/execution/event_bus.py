from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class GuardianEvent:
    """Event envelope (architecture §18 — not wired in Etap 1)."""

    event: str
    correlation_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


EventHandler = Callable[[GuardianEvent], None]


class EventBus:
    """In-process event dispatch — Etap 3+ (stub only)."""

    def publish(self, event: GuardianEvent) -> None:
        raise NotImplementedError("Event Bus — planned for Etap 3+")

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        raise NotImplementedError("Event Bus — planned for Etap 3+")
