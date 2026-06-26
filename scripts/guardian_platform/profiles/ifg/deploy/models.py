from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StepStatus(str, Enum):
    PENDING = "PENDING"
    SIMULATED = "SIMULATED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class RollbackPoint:
    commit_before: str = ""
    alembic_before: str = ""
    images_before: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "commit_before": self.commit_before,
            "alembic_before": self.alembic_before,
            "images_before": self.images_before,
        }


@dataclass
class DeployStep:
    order: int
    action: str
    command: str
    required: bool = True
    status: StepStatus = StepStatus.PENDING
    output: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "action": self.action,
            "command": self.command,
            "required": self.required,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
        }


@dataclass
class DeployRunState:
    dry_run: bool = True
    assume_yes: bool = False
    remote_host: str = ""
    remote_path: str = ""
    rollback_available: bool = False
    rollback_point: RollbackPoint = field(default_factory=RollbackPoint)
    steps: list[DeployStep] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    health: str = ""
    smoke_ok: bool = False
    halted: bool = False
    halt_reason: str = ""
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "assume_yes": self.assume_yes,
            "remote_host": self.remote_host,
            "remote_path": self.remote_path,
            "rollback_available": self.rollback_available,
            "rollback_point": self.rollback_point.to_dict(),
            "steps": [s.to_dict() for s in self.steps],
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "health": self.health,
            "smoke_ok": self.smoke_ok,
            "halted": self.halted,
            "halt_reason": self.halt_reason,
            "summary": dict(self.summary),
        }
