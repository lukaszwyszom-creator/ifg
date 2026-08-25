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
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    failure_reason: str = ""

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
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "failure_reason": self.failure_reason,
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
            exit_code=data.get("exit_code"),
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            failure_reason=data.get("failure_reason", ""),
        )


@dataclass
class DeployRunState:
    release_plan_workflow_id: str = ""
    release_evaluate_workflow_id: str = ""
    release_decision: str = ""
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
    failed_step: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    allow_dirty_build_override: bool = False
    build_commit: str = ""
    build_snapshot_path: str = ""
    build_source: str = ""
    build_manifest_sha256: str = ""
    source_wip_detected: bool = False
    source_wip_excluded: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "release_plan_workflow_id": self.release_plan_workflow_id,
            "release_evaluate_workflow_id": self.release_evaluate_workflow_id,
            "release_decision": self.release_decision,
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
            "failed_step": dict(self.failed_step),
            "summary": dict(self.summary),
            "allow_dirty_build_override": self.allow_dirty_build_override,
            "build_commit": self.build_commit,
            "build_snapshot_path": self.build_snapshot_path,
            "build_source": self.build_source,
            "build_manifest_sha256": self.build_manifest_sha256,
            "source_wip_detected": self.source_wip_detected,
            "source_wip_excluded": self.source_wip_excluded,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeployRunState:
        return cls(
            release_plan_workflow_id=data.get("release_plan_workflow_id", ""),
            release_evaluate_workflow_id=data.get("release_evaluate_workflow_id", ""),
            release_decision=data.get("release_decision", ""),
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
            failed_step=dict(data.get("failed_step", {})),
            summary=dict(data.get("summary", {})),
            allow_dirty_build_override=bool(data.get("allow_dirty_build_override", False)),
            build_commit=data.get("build_commit", ""),
            build_snapshot_path=data.get("build_snapshot_path", ""),
            build_source=data.get("build_source", ""),
            build_manifest_sha256=data.get("build_manifest_sha256", ""),
            source_wip_detected=bool(data.get("source_wip_detected", False)),
            source_wip_excluded=bool(data.get("source_wip_excluded", True)),
        )
