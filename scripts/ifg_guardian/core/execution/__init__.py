"""Guardian execution layer (Etap 1 — Operation Engine + Execution Backend)."""

from ifg_guardian.core.execution.backend import DeploymentBackend, ExecutionBackend
from ifg_guardian.core.execution.compose_backend import ComposeBackend
from ifg_guardian.core.execution.deployment_engine import DeploymentEngine
from ifg_guardian.core.execution.models import (
    DeployContext,
    DeploymentResult,
    Operation,
    OperationResult,
)
from ifg_guardian.core.execution.operation_engine import OperationEngine

__all__ = [
    "ComposeBackend",
    "DeployContext",
    "DeploymentBackend",
    "DeploymentEngine",
    "DeploymentResult",
    "ExecutionBackend",
    "Operation",
    "OperationEngine",
    "OperationResult",
]
