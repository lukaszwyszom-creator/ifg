from __future__ import annotations

from guardian_platform.profiles.ifg.recover.models import RecoverState


def get_recover_state(ctx) -> RecoverState:
    state = ctx.data.get("recover")
    if not isinstance(state, RecoverState):
        raise RuntimeError("recover state not initialized")
    return state
