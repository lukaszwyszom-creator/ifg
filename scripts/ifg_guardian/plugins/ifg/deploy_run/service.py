from __future__ import annotations

from ifg_guardian.core.workflow.context import WorkflowContext
from ifg_guardian.core.workflow.state import WorkflowState
from ifg_guardian.plugins.ifg.deploy_run.models import DeployRunState
from ifg_guardian.plugins.ifg.release_plan.models import ReleasePlanState


def get_deploy_state(ctx: WorkflowContext) -> DeployRunState:
    state = ctx.data.get("deploy_run")
    if not isinstance(state, DeployRunState):
        raise RuntimeError("deploy run state not initialized")
    return state


def get_release_plan_dependency(ctx: WorkflowContext) -> ReleasePlanState:
    deps = ctx.data.get("dependency_contexts", {})
    plan_ctx = deps.get("ifg.release.plan")
    if plan_ctx is None:
        raise RuntimeError("ifg.release.plan dependency was not executed by Workflow Engine")
    if plan_ctx.state_machine.state != WorkflowState.SUCCESS:
        raise RuntimeError(
            f"ifg.release.plan dependency failed: {plan_ctx.transaction.outcome}"
        )
    payload = plan_ctx.transaction.release_plan
    if not payload:
        raise RuntimeError("ifg.release.plan dependency produced no release_plan snapshot")
    return ReleasePlanState.from_dict(payload)
