from __future__ import annotations

from ifg_guardian.core.workflow.context import WorkflowContext
from ifg_guardian.core.workflow.state import WorkflowState
from ifg_guardian.plugins.ifg.doctor.models import DoctorState
from ifg_guardian.plugins.ifg.release_plan.models import ReleasePlanState


def get_plan_state(ctx: WorkflowContext) -> ReleasePlanState:
    state = ctx.data.get("release_plan")
    if not isinstance(state, ReleasePlanState):
        raise RuntimeError("release plan state not initialized")
    return state


def get_doctor_dependency(ctx: WorkflowContext) -> DoctorState:
    deps = ctx.data.get("dependency_contexts", {})
    doctor_ctx = deps.get("ifg.doctor")
    if doctor_ctx is None:
        raise RuntimeError("ifg.doctor dependency was not executed by Workflow Engine")
    if doctor_ctx.state_machine.state != WorkflowState.SUCCESS:
        raise RuntimeError(
            f"ifg.doctor dependency failed: {doctor_ctx.transaction.outcome}"
        )
    payload = doctor_ctx.transaction.doctor
    if not payload:
        raise RuntimeError("ifg.doctor dependency produced no doctor snapshot")
    return DoctorState.from_dict(payload)
