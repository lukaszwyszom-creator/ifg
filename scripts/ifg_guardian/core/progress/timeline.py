from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TimelineEntry:
    phase: str
    status: str
    message: str
    step: int
    total: int
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_ms: int = 0
    last_action: str = ""

    def to_dict(self) -> dict:
        return {
            "phase": self.phase,
            "status": self.status,
            "message": self.message,
            "step": self.step,
            "total": self.total,
            "started_at": self.started_at.isoformat().replace("+00:00", "Z") if self.started_at else None,
            "ended_at": self.ended_at.isoformat().replace("+00:00", "Z") if self.ended_at else None,
            "duration_ms": self.duration_ms,
            "last_action": self.last_action,
        }


@dataclass
class ProgressTimeline:
    workflow_id: str
    workflow_type: str
    entries: list[TimelineEntry] = field(default_factory=list)

    def add(self, entry: TimelineEntry) -> None:
        self.entries.append(entry)

    def to_dict(self) -> dict:
        return {
            "workflow_id": self.workflow_id,
            "workflow_type": self.workflow_type,
            "entries": [e.to_dict() for e in self.entries],
        }
