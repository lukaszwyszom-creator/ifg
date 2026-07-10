from __future__ import annotations

from ifg_guardian.core.execution.backend import ExecutionBackend
from ifg_guardian.core.execution.models import DeployContext, Operation, OperationResult
from ifg_guardian.core.execution.operation_engine import OperationEngine


class DeploymentEngine:
    """Legacy facade — deploy() delegates to OperationEngine (§5.6, Etap 1)."""

    def __init__(
        self,
        *,
        backend: ExecutionBackend | None = None,
        operation_engine: OperationEngine | None = None,
    ) -> None:
        if operation_engine is not None:
            self._ops = operation_engine
        elif backend is not None:
            self._ops = OperationEngine(backend)
        else:
            raise ValueError("DeploymentEngine requires backend or operation_engine")

    def deploy(self, ctx: DeployContext) -> OperationResult:
        return self._ops.execute(Operation.Deploy, ctx)

    @property
    def operation_engine(self) -> OperationEngine:
        return self._ops
