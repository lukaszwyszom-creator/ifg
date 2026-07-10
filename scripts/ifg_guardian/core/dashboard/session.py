from __future__ import annotations

import sys
import threading
import time
from collections.abc import Callable

from ifg_guardian.core.dashboard.model import DashboardState
from ifg_guardian.core.dashboard.renderer import render_dashboard_rich
from ifg_guardian.core.dashboard.stderr_sink import ProgressStderrSink


REFRESH_HZ = 1.0


def _require_rich():
    try:
        from rich.console import Console
        from rich.live import Live
    except ImportError as exc:
        raise RuntimeError(
            "Guardian Live Dashboard requires the 'rich' package. "
            "Install with: pip install 'rich>=13.7,<14.0'"
        ) from exc
    return Console, Live


def run_with_live_dashboard(workflow_fn: Callable[[], int]) -> int:
    """
    Run a Guardian workflow function with fullscreen live dashboard.

    Progress lines are intercepted from stderr; the standard Guardian report
    is printed after the dashboard closes (by workflow_fn on stdout).
    """
    Console, Live = _require_rich()

    state = DashboardState()
    real_stderr = sys.stderr
    sink = ProgressStderrSink(real_stderr, state, suppress_progress_lines=True)
    sys.stderr = sink  # type: ignore[assignment]

    console = Console(stderr=True, force_terminal=True)
    result: dict[str, int] = {}
    error: dict[str, BaseException] = {}

    def worker() -> None:
        try:
            result["code"] = workflow_fn()
        except BaseException as exc:
            error["exc"] = exc
            result["code"] = 1

    thread = threading.Thread(target=worker, name="gwo-dashboard-workflow", daemon=False)
    thread.start()

    try:
        with Live(
            render_dashboard_rich(state),
            console=console,
            refresh_per_second=REFRESH_HZ,
            screen=True,
            transient=True,
        ) as live:
            while thread.is_alive():
                state.advance_spinner()
                live.update(render_dashboard_rich(state))
                time.sleep(1.0 / REFRESH_HZ)
            state.advance_spinner()
            live.update(render_dashboard_rich(state))
    finally:
        sink.flush()
        sys.stderr = real_stderr

    if "exc" in error:
        raise error["exc"]

    return int(result.get("code", 1))
