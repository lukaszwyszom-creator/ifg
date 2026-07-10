from __future__ import annotations

import sys
from io import StringIO

from ifg_guardian.core.dashboard.model import DashboardState
from ifg_guardian.core.dashboard.stderr_sink import ProgressStderrSink
from ifg_guardian.core.progress.protocol import ProgressStatus, format_progress_line


def test_stderr_sink_parses_progress_and_suppresses_lines():
    state = DashboardState()
    real = StringIO()
    sink = ProgressStderrSink(real, state, suppress_progress_lines=True)
    line = format_progress_line(
        step=1,
        total=10,
        phase="repo_status",
        status=ProgressStatus.STARTED,
        elapsed_seconds=0,
        message="Workflow ifg.deploy.run (DRY_RUN)",
    )
    sink.write(line + "\n")
    sink.flush()
    assert state.workflow_type == "ifg.deploy.run"
    assert real.getvalue() == ""

    sink.write("real error\n")
    sink.flush()
    assert "real error" in real.getvalue()

    sys.stderr = sys.__stderr__
