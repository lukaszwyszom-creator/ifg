from __future__ import annotations

from pathlib import Path

from ifg_guardian.core.execution.models import DeployContext, Operation, OperationResult
from ifg_guardian.core.workflow.executors.compose_executor import ComposeExecutor
from ifg_guardian.core.workflow.executors.context import DeployExecutorContext
from ifg_guardian.core.workflow.intents import LocalExecIntent


class ComposeBackend:
    """Legacy compose backend — wraps ComposeExecutor without changing behavior."""

    name = "compose"

    def __init__(self, *, root: Path, deploy_context: DeployExecutorContext | None = None) -> None:
        self._executor = ComposeExecutor(root=root, deploy_context=deploy_context)

    def deploy(self, ctx: DeployContext) -> OperationResult:
        intent = ctx.intent
        if intent is None:
            return OperationResult(
                ok=False,
                operation=Operation.Deploy,
                error="deploy requires LocalExecIntent",
            )
        result = self._executor.execute_up(intent, ctx.shell_cmd)
        return OperationResult.from_intent_result(result, operation=Operation.Deploy)

    def logs(self, ctx: DeployContext) -> OperationResult:
        intent = ctx.intent
        if intent is None:
            return OperationResult(
                ok=False,
                operation=Operation.Verify,
                error="logs requires LocalExecIntent",
            )
        result = self._executor.execute_logs(intent, ctx.shell_cmd)
        return OperationResult.from_intent_result(result, operation=Operation.Verify)

    def restart(self, ctx: DeployContext, *, services: list[str] | None = None) -> OperationResult:
        return _not_implemented(Operation.Restart)

    def stop(self, ctx: DeployContext) -> OperationResult:
        return _not_implemented(Operation.Stop)

    def start(self, ctx: DeployContext) -> OperationResult:
        return _not_implemented(Operation.Start)

    def status(self, ctx: DeployContext) -> OperationResult:
        return _not_implemented(Operation.Inventory)

    def health(self, ctx: DeployContext) -> OperationResult:
        return _not_implemented(Operation.Health)

    def rollback(self, ctx: DeployContext) -> OperationResult:
        return _not_implemented(Operation.Rollback)

    def execute_up(self, intent: LocalExecIntent, shell_cmd: str):
        """Direct delegate for backward compatibility with ComposeExecutor callers."""
        return self._executor.execute_up(intent, shell_cmd)

    def execute_logs(self, intent: LocalExecIntent, shell_cmd: str):
        """Direct delegate for backward compatibility with ComposeExecutor callers."""
        return self._executor.execute_logs(intent, shell_cmd)


def _not_implemented(operation: Operation) -> OperationResult:
    return OperationResult(
        ok=False,
        operation=operation,
        error=f"{operation.value} not implemented in ComposeBackend (Etap 1)",
    )
