from __future__ import annotations

from ifg_guardian.core.execution.models import DeployContext, OperationResult


class SynologyProjectBackend:
    """DSM Container Manager Project backend — Etap 2 (not implemented)."""

    name = "synology_project"

    def deploy(self, ctx: DeployContext) -> OperationResult:
        raise NotImplementedError("SynologyProjectBackend — planned for Etap 2")
