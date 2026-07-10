from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ifg_guardian.core.workflow.executors.context import DeployExecutorContext
from ifg_guardian.core.workflow.intents import ActionIntent, LocalExecIntent
from ifg_guardian.core.workflow.results import IntentResult


class Operation(str, Enum):
    """Guardian operations (Etap 1: Deploy only)."""

    Deploy = "deploy"
    Update = "update"
    Restart = "restart"
    Start = "start"
    Stop = "stop"
    Backup = "backup"
    Restore = "restore"
    Verify = "verify"
    Health = "health"
    Snapshot = "snapshot"
    Cleanup = "cleanup"
    Inventory = "inventory"
    Audit = "audit"
    Repair = "repair"
    Rollback = "rollback"


@dataclass
class DeployContext:
    """Context for deploy / runtime operations."""

    executor_context: DeployExecutorContext
    intent: LocalExecIntent | None = None
    shell_cmd: str = ""
    dry_run: bool = False
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class OperationResult:
    ok: bool
    operation: Operation
    message: str = ""
    output: str = ""
    error: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def to_intent_result(self, intent: ActionIntent) -> IntentResult:
        return IntentResult(
            intent=intent,
            ok=self.ok,
            output=self.output,
            error=self.error,
            data=dict(self.data),
        )

    @classmethod
    def from_intent_result(cls, result: IntentResult, *, operation: Operation) -> OperationResult:
        return cls(
            ok=result.ok,
            operation=operation,
            output=result.output,
            error=result.error,
            data=dict(result.data),
        )


# Backward-compatible alias (v0.1 terminology).
DeploymentResult = OperationResult
