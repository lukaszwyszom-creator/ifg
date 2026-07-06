from __future__ import annotations

from ifg_guardian.core.plugins.base import GuardianPlugin
from ifg_guardian.core.plugins.context import PluginContext
from ifg_guardian.core.workflow.definition import WorkflowDefinition
from ifg_guardian.plugins.ifg.container_cutover import IFG_CONTAINER_CUTOVER_WORKFLOW
from ifg_guardian.plugins.ifg.deploy_run import IFG_DEPLOY_RUN_WORKFLOW
from ifg_guardian.plugins.ifg.doctor import IFG_DOCTOR_WORKFLOW
from ifg_guardian.plugins.ifg.release_plan import IFG_RELEASE_PLAN_WORKFLOW


class IFGPlugin(GuardianPlugin):
    """IFG domain plugin — workflows added in future sprints."""

    @property
    def name(self) -> str:
        return "ifg"

    @property
    def version(self) -> str:
        return "1.0.0"

    def workflows(self) -> list[WorkflowDefinition]:
        return [IFG_DOCTOR_WORKFLOW, IFG_RELEASE_PLAN_WORKFLOW, IFG_DEPLOY_RUN_WORKFLOW, IFG_CONTAINER_CUTOVER_WORKFLOW]

    def initialize(self, ctx: PluginContext) -> None:
        ctx.logger.info("IFG plugin initialized")

    def shutdown(self) -> None:
        pass
