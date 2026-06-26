from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from guardian_platform.core.runtime.mode import ExecutionMode
from guardian_platform.core.workflow.stage import BuildReason, StageResult
from guardian_platform.core.workflow.state import WorkflowState, WorkflowStateMachine


@dataclass
class StageRecord:
    id: str
    status: str
    duration_ms: int = 0
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "status": self.status, "duration_ms": self.duration_ms, "message": self.message}


@dataclass
class WorkflowTransaction:
    workflow_id: str
    workflow_type: str
    profile: str
    execution_mode: ExecutionMode
    state: WorkflowState = WorkflowState.UNKNOWN
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_ms: int = 0
    host_local: str = ""
    commit_before: str = ""
    commit_after: str = ""
    branch: str = ""
    stages: list[StageRecord] = field(default_factory=list)
    outcome: str = ""
    warnings: list[str] = field(default_factory=list)
    profile_data: dict[str, Any] = field(default_factory=dict)

    def mark_started(self) -> None:
        self.started_at = datetime.now(UTC)

    def mark_ended(self, *, state: WorkflowState) -> None:
        self.ended_at = datetime.now(UTC)
        self.state = state
        if self.started_at is not None:
            self.duration_ms = int((self.ended_at - self.started_at).total_seconds() * 1000)
        self.outcome = "SUCCESS" if state == WorkflowState.SUCCESS else "FAILED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "workflow_type": self.workflow_type,
            "profile": self.profile,
            "execution_mode": self.execution_mode.value,
            "state": self.state.value,
            "duration_ms": self.duration_ms,
            "outcome": self.outcome,
            "commit_before": self.commit_before,
            "commit_after": self.commit_after,
            "branch": self.branch,
            "warnings": list(self.warnings),
            "stages": [s.to_dict() for s in self.stages],
            "profile_data": dict(self.profile_data),
        }


@dataclass
class WorkflowContext:
    root: Path
    workflow_id: str
    workflow_type: str
    transaction: WorkflowTransaction
    mode: ExecutionMode
    state_machine: WorkflowStateMachine
    data: dict[str, Any] = field(default_factory=dict)
    stage_results: list[StageResult] = field(default_factory=list)
