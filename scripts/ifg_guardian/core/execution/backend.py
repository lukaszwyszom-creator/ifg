from __future__ import annotations

from typing import Protocol

from ifg_guardian.core.execution.models import DeployContext, OperationResult


class ExecutionBackend(Protocol):
    """Platform adapter for Guardian operations (canonical name, v1.0)."""

    name: str

    def deploy(self, ctx: DeployContext) -> OperationResult: ...

    def restart(self, ctx: DeployContext, *, services: list[str] | None = None) -> OperationResult: ...

    def stop(self, ctx: DeployContext) -> OperationResult: ...

    def start(self, ctx: DeployContext) -> OperationResult: ...

    def status(self, ctx: DeployContext) -> OperationResult: ...

    def logs(self, ctx: DeployContext) -> OperationResult: ...

    def health(self, ctx: DeployContext) -> OperationResult: ...

    def rollback(self, ctx: DeployContext) -> OperationResult: ...


# Backward-compatible alias (Etap 1 — deprecated from v4 per architecture doc).
DeploymentBackend = ExecutionBackend
