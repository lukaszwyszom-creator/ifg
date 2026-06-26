from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DeployStepStatus(str, Enum):
    PENDING = "PENDING"
    SIMULATED = "SIMULATED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    BLOCKED = "BLOCKED"


@dataclass
class RollbackPoint:
    commit_before: str = ""
    images_before: str = ""
    alembic_before: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "commit_before": self.commit_before,
            "images_before": self.images_before,
            "alembic_before": self.alembic_before,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RollbackPoint:
        return cls(
            commit_before=data.get("commit_before", ""),
            images_before=data.get("images_before", ""),
            alembic_before=data.get("alembic_before", ""),
        )


@dataclass
class DeployStep:
    order: int
    action: str
    description: str
    reason: str
    required: bool
    skipped: bool = False
    command: str = ""
    status: DeployStepStatus = DeployStepStatus.PENDING
    simulated: bool = False
    duration_ms: int = 0
    output: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "action": self.action,
            "description": self.description,
            "reason": self.reason,
            "required": self.required,
            "skipped": self.skipped,
            "command": self.command,
            "status": self.status.value,
            "simulated": self.simulated,
            "duration_ms": self.duration_ms,
            "output": self.output,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeployStep:
        return cls(
            order=data.get("order", 0),
            action=data.get("action", ""),
            description=data.get("description", ""),
            reason=data.get("reason", ""),
            required=data.get("required", True),
            skipped=data.get("skipped", False),
            command=data.get("command", ""),
            status=DeployStepStatus(data.get("status", DeployStepStatus.PENDING.value)),
            simulated=data.get("simulated", False),
            duration_ms=data.get("duration_ms", 0),
            output=data.get("output", ""),
            error=data.get("error", ""),
        )


@dataclass
class DeployRunState:
    release_plan_workflow_id: str = ""
    deployment_risk: str = ""
    doctor_status: str = ""
    blockers: list[str] = field(default_factory=list)
    steps: list[DeployStep] = field(default_factory=list)
    dry_run: bool = True
    rollback_point: RollbackPoint = field(default_factory=RollbackPoint)
    executed_commands: list[str] = field(default_factory=list)
    containers: str = ""
    health: str = ""
    warnings: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "release_plan_workflow_id": self.release_plan_workflow_id,
            "deployment_risk": self.deployment_risk,
            "doctor_status": self.doctor_status,
            "blockers": list(self.blockers),
            "steps": [s.to_dict() for s in self.steps],
            "dry_run": self.dry_run,
            "rollback_point": self.rollback_point.to_dict(),
            "executed_commands": list(self.executed_commands),
            "containers": self.containers,
            "health": self.health,
            "warnings": list(self.warnings),
            "summary": dict(self.summary),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeployRunState:
        return cls(
            release_plan_workflow_id=data.get("release_plan_workflow_id", ""),
            deployment_risk=data.get("deployment_risk", ""),
            doctor_status=data.get("doctor_status", ""),
            blockers=list(data.get("blockers", [])),
            steps=[DeployStep.from_dict(s) for s in data.get("steps", [])],
            dry_run=data.get("dry_run", True),
            rollback_point=RollbackPoint.from_dict(data.get("rollback_point", {})),
            executed_commands=list(data.get("executed_commands", [])),
            containers=data.get("containers", ""),
            health=data.get("health", ""),
            warnings=list(data.get("warnings", [])),
            summary=dict(data.get("summary", {})),
        )
