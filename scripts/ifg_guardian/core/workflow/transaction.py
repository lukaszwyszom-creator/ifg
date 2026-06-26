from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ifg_guardian.core.workflow.mode import ExecutionMode
from ifg_guardian.core.workflow.stage import BuildReason
from ifg_guardian.core.workflow.state import WorkflowState

SCHEMA_VERSION = "workflow_transaction_v1"


@dataclass
class StageRecord:
    id: str
    status: str
    duration_ms: int = 0
    reasons: list[BuildReason] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "reasons": [r.to_dict() for r in self.reasons],
            "message": self.message,
        }


@dataclass
class ArtifactRecord:
    type: str
    path: str

    def to_dict(self) -> dict[str, str]:
        return {"type": self.type, "path": self.path}


@dataclass
class WorkflowTransaction:
    workflow_id: str
    workflow_type: str
    plugin: str | None
    execution_mode: ExecutionMode
    state: WorkflowState = WorkflowState.UNKNOWN
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_ms: int = 0
    host_local: str = ""
    host_remote: str = ""
    remote_path: str = ""
    commit_before: str = ""
    commit_after: str = ""
    branch: str = ""
    image_before: str = ""
    image_after: str = ""
    containers_restarted: list[str] = field(default_factory=list)
    alembic_before: str = ""
    alembic_after: str = ""
    bundle_hash_before: str = ""
    bundle_hash_after: str = ""
    frontend_built: bool = False
    frontend_synced: bool = False
    stages: list[StageRecord] = field(default_factory=list)
    artifacts: list[ArtifactRecord] = field(default_factory=list)
    outcome: str = ""
    rollback_possible: bool = False
    rollback_executed: bool = False
    warnings: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    audit: dict[str, Any] = field(default_factory=dict)
    doctor: dict[str, Any] = field(default_factory=dict)
    dependencies: dict[str, Any] = field(default_factory=dict)
    release_plan: dict[str, Any] = field(default_factory=dict)
    deploy_run: dict[str, Any] = field(default_factory=dict)

    def mark_started(self) -> None:
        self.started_at = datetime.now(UTC)

    def mark_ended(self, *, state: WorkflowState) -> None:
        self.ended_at = datetime.now(UTC)
        self.state = state
        if self.started_at is not None:
            delta = self.ended_at - self.started_at
            self.duration_ms = int(delta.total_seconds() * 1000)
        if state == WorkflowState.SUCCESS:
            self.outcome = "SUCCESS"
        elif state == WorkflowState.FAILED:
            self.outcome = "FAILED"
        elif state == WorkflowState.ABORTED:
            self.outcome = "ABORTED"
        elif state == WorkflowState.ROLLED_BACK:
            self.outcome = "ROLLED_BACK"

    def to_dict(self) -> dict[str, Any]:
        lifecycle: dict[str, Any] = {
            "state": self.state.value,
            "started_at": self.started_at.isoformat().replace("+00:00", "Z") if self.started_at else None,
            "ended_at": self.ended_at.isoformat().replace("+00:00", "Z") if self.ended_at else None,
            "duration_ms": self.duration_ms,
        }
        return {
            "schema": SCHEMA_VERSION,
            "workflow_id": self.workflow_id,
            "workflow_type": self.workflow_type,
            "plugin": self.plugin,
            "execution_mode": self.execution_mode.value,
            "lifecycle": lifecycle,
            "host": {
                "local": self.host_local,
                "remote": self.host_remote,
                "remote_path": self.remote_path,
            },
            "git": {
                "commit_before": self.commit_before,
                "commit_after": self.commit_after,
                "branch": self.branch,
            },
            "docker": {
                "image_before": self.image_before,
                "image_after": self.image_after,
                "containers_restarted": list(self.containers_restarted),
            },
            "alembic": {
                "revision_before": self.alembic_before,
                "revision_after": self.alembic_after,
            },
            "frontend": {
                "bundle_hash_before": self.bundle_hash_before,
                "bundle_hash_after": self.bundle_hash_after,
                "built": self.frontend_built,
                "synced": self.frontend_synced,
            },
            "stages": [s.to_dict() for s in self.stages],
            "artifacts": [a.to_dict() for a in self.artifacts],
            "outcome": self.outcome,
            "rollback_possible": self.rollback_possible,
            "rollback_executed": self.rollback_executed,
            "warnings": list(self.warnings),
            "recommended_actions": list(self.recommended_actions),
            "audit": dict(self.audit),
            "doctor": dict(self.doctor),
            "dependencies": dict(self.dependencies),
            "release_plan": dict(self.release_plan),
            "deploy_run": dict(self.deploy_run),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowTransaction:
        lifecycle = data.get("lifecycle", {})
        host = data.get("host", {})
        git = data.get("git", {})
        docker = data.get("docker", {})
        alembic = data.get("alembic", {})
        frontend = data.get("frontend", {})
        stages = [
            StageRecord(
                id=s["id"],
                status=s.get("status", ""),
                duration_ms=s.get("duration_ms", 0),
                reasons=[
                    BuildReason(
                        decision=r.get("decision", ""),
                        because=list(r.get("because", [])),
                        confidence=r.get("confidence", "HIGH"),
                        source_stage=r.get("source_stage", ""),
                    )
                    for r in s.get("reasons", [])
                ],
                message=s.get("message", ""),
            )
            for s in data.get("stages", [])
        ]
        return cls(
            workflow_id=data.get("workflow_id", ""),
            workflow_type=data.get("workflow_type", ""),
            plugin=data.get("plugin"),
            execution_mode=ExecutionMode(data.get("execution_mode", ExecutionMode.LIVE.value)),
            state=WorkflowState(lifecycle.get("state", WorkflowState.UNKNOWN.value)),
            started_at=_parse_dt(lifecycle.get("started_at")),
            ended_at=_parse_dt(lifecycle.get("ended_at")),
            duration_ms=lifecycle.get("duration_ms", 0),
            host_local=host.get("local", ""),
            host_remote=host.get("remote", ""),
            remote_path=host.get("remote_path", ""),
            commit_before=git.get("commit_before", ""),
            commit_after=git.get("commit_after", ""),
            branch=git.get("branch", ""),
            image_before=docker.get("image_before", ""),
            image_after=docker.get("image_after", ""),
            containers_restarted=list(docker.get("containers_restarted", [])),
            alembic_before=alembic.get("revision_before", ""),
            alembic_after=alembic.get("revision_after", ""),
            bundle_hash_before=frontend.get("bundle_hash_before", ""),
            bundle_hash_after=frontend.get("bundle_hash_after", ""),
            frontend_built=frontend.get("built", False),
            frontend_synced=frontend.get("synced", False),
            stages=stages,
            artifacts=[
                ArtifactRecord(type=a.get("type", ""), path=a.get("path", ""))
                for a in data.get("artifacts", [])
            ],
            outcome=data.get("outcome", ""),
            rollback_possible=data.get("rollback_possible", False),
            rollback_executed=data.get("rollback_executed", False),
            warnings=list(data.get("warnings", [])),
            recommended_actions=list(data.get("recommended_actions", [])),
            audit=dict(data.get("audit", {})),
            doctor=dict(data.get("doctor", {})),
            dependencies=dict(data.get("dependencies", {})),
            release_plan=dict(data.get("release_plan", {})),
            deploy_run=dict(data.get("deploy_run", {})),
        )


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)
