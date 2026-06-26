from __future__ import annotations

from ifg_guardian.plugins.ifg.doctor.models import DoctorState


def get_doctor_state(ctx) -> DoctorState:
    state = ctx.data.get("doctor")
    if not isinstance(state, DoctorState):
        raise RuntimeError("doctor state not initialized")
    return state


def add_checks(state: DoctorState, checks) -> None:
    state.checks.extend(checks)
