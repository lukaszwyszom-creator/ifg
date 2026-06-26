from __future__ import annotations

from guardian_platform.profiles.ifg.deploy.models import DeployRunState


def get_deploy_state(ctx) -> DeployRunState:
    state = ctx.data.get("deploy_run")
    if not isinstance(state, DeployRunState):
        raise RuntimeError("deploy run state not initialized")
    return state
