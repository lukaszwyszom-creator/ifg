from __future__ import annotations

from ifg_guardian.core.plugins.base import GuardianPlugin
from ifg_guardian.core.plugins.context import PluginContext
from ifg_guardian.core.workflow.definition import WorkflowDefinition
from ifg_guardian.plugins.core.workflows.ping import CORE_PING_WORKFLOW
from ifg_guardian.plugins.core.workflows.repo_audit import CORE_REPO_AUDIT_WORKFLOW


class CorePlugin(GuardianPlugin):
    """Built-in Core plugin — generic workflows without domain knowledge."""

    @property
    def name(self) -> str:
        return "core"

    @property
    def version(self) -> str:
        return "1.0.0"

    def workflows(self) -> list[WorkflowDefinition]:
        return [CORE_PING_WORKFLOW, CORE_REPO_AUDIT_WORKFLOW]

    def initialize(self, ctx: PluginContext) -> None:
        ctx.logger.info("Core plugin initialized")

    def shutdown(self) -> None:
        pass
