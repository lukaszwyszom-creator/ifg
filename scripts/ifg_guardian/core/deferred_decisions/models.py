from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from enum import Enum
from typing import Any


class DeferredDecisionType(str, Enum):
    ARCHITECTURE = "Architecture"
    UX = "UX"
    PERFORMANCE = "Performance"
    REFACTOR = "Refactor"
    TECHNICAL_DEBT = "Technical Debt"
    PROCESS = "Process"
    OTHER = "Other"


class DeferredPriority(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class DeferredDecisionStatus(str, Enum):
    OPEN = "OPEN"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


_TYPE_ALIASES: dict[str, DeferredDecisionType] = {
    "architecture": DeferredDecisionType.ARCHITECTURE,
    "ux": DeferredDecisionType.UX,
    "performance": DeferredDecisionType.PERFORMANCE,
    "refactor": DeferredDecisionType.REFACTOR,
    "technical": DeferredDecisionType.TECHNICAL_DEBT,
    "technical_debt": DeferredDecisionType.TECHNICAL_DEBT,
    "process": DeferredDecisionType.PROCESS,
    "other": DeferredDecisionType.OTHER,
}

_PRIORITY_ALIASES: dict[str, DeferredPriority] = {
    "low": DeferredPriority.LOW,
    "medium": DeferredPriority.MEDIUM,
    "high": DeferredPriority.HIGH,
}

_STATUS_ALIASES: dict[str, DeferredDecisionStatus] = {
    "open": DeferredDecisionStatus.OPEN,
    "done": DeferredDecisionStatus.DONE,
    "cancelled": DeferredDecisionStatus.CANCELLED,
}


def coerce_decision_type(raw: str) -> DeferredDecisionType:
    key = str(raw or "").strip().lower().replace("-", "_")
    if key in _TYPE_ALIASES:
        return _TYPE_ALIASES[key]
    for item in DeferredDecisionType:
        if item.value.lower() == key.replace("_", " "):
            return item
    raise ValueError(f"unknown GDD type: {raw!r}")


def coerce_priority(raw: str) -> DeferredPriority:
    key = str(raw or "medium").strip().lower()
    if key in _PRIORITY_ALIASES:
        return _PRIORITY_ALIASES[key]
    for item in DeferredPriority:
        if item.value.lower() == key:
            return item
    raise ValueError(f"unknown GDD priority: {raw!r}")


def coerce_status(raw: str) -> DeferredDecisionStatus:
    key = str(raw or "open").strip().lower()
    if key in _STATUS_ALIASES:
        return _STATUS_ALIASES[key]
    for item in DeferredDecisionStatus:
        if item.value.lower() == key:
            return item
    raise ValueError(f"unknown GDD status: {raw!r}")


@dataclass
class DeferredDecision:
    id: str
    project: str
    module: str
    type: DeferredDecisionType
    priority: DeferredPriority
    status: DeferredDecisionStatus
    defer_reason: str
    description: str
    review_when: str
    source: str
    created_at: str
    closed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["type"] = self.type.value
        payload["priority"] = self.priority.value
        payload["status"] = self.status.value
        return payload

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> DeferredDecision:
        return cls(
            id=str(raw["id"]),
            project=str(raw["project"]),
            module=str(raw["module"]),
            type=coerce_decision_type(str(raw["type"])),
            priority=coerce_priority(str(raw.get("priority", "Medium"))),
            status=coerce_status(str(raw.get("status", "OPEN"))),
            defer_reason=str(raw["defer_reason"]),
            description=str(raw["description"]),
            review_when=str(raw["review_when"]),
            source=str(raw["source"]),
            created_at=str(raw["created_at"]),
            closed_at=str(raw["closed_at"]) if raw.get("closed_at") else None,
        )


@dataclass
class DeferredDecisionStore:
    schema_version: int = 1
    next_id: int = 1
    items: list[DeferredDecision] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "next_id": self.next_id,
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> DeferredDecisionStore:
        items = [DeferredDecision.from_dict(entry) for entry in raw.get("items", [])]
        return cls(
            schema_version=int(raw.get("schema_version", 1)),
            next_id=int(raw.get("next_id", 1)),
            items=items,
        )
