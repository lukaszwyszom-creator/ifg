from __future__ import annotations

from ifg_guardian.core.execution.backend import ExecutionBackend
from ifg_guardian.core.execution.models import DeployContext, Operation, OperationResult


class OperationEngine:
    """Routes operations to ExecutionBackend (Etap 1: Deploy only)."""

    def __init__(self, backend: ExecutionBackend) -> None:
        self._backend = backend

    @property
    def backend(self) -> ExecutionBackend:
        return self._backend

    def execute(self, operation: Operation, ctx: DeployContext) -> OperationResult:
        if operation == Operation.Deploy:
            return self._backend.deploy(ctx)
        return OperationResult(
            ok=False,
            operation=operation,
            error=f"Operation {operation.value} not implemented (Etap 1)",
        )
