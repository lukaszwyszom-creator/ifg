from __future__ import annotations

from ifg_guardian.core.workflow.context import WorkflowContext
from ifg_guardian.plugins.ifg.container_cutover.models import CutoverRunState


def get_cutover_state(ctx: WorkflowContext) -> CutoverRunState:
    state = ctx.data.get("cutover_run")
    if isinstance(state, CutoverRunState):
        return state
    state = CutoverRunState()
    ctx.data["cutover_run"] = state
    return state
