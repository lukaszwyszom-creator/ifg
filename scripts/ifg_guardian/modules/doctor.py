from __future__ import annotations

from ifg_guardian.modules.ifg_doctor import run_ifg_doctor


def run_doctor(*, do_fetch: bool = False) -> int:
    """Legacy entry — delegates to ifg.doctor workflow."""
    return run_ifg_doctor(do_fetch=do_fetch)
