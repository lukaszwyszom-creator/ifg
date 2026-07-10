from __future__ import annotations

import io
import re

from ifg_guardian.core.progress.mapping import (
    DEPLOY_PHASES,
    LONG_WORKFLOW_IDS,
    default_progress_enabled,
    deploy_phase_index,
    phase_for_shell_command,
    phase_for_workflow_stage,
)
from ifg_guardian.core.progress.protocol import (
    GWO_PROGRESS_PREFIX,
    ProgressStatus,
    format_elapsed,
    format_progress_line,
    sanitize_message,
)
from ifg_guardian.core.progress.report import render_timeline_section
from ifg_guardian.core.progress.tracker import ProgressTracker


PROGRESS_LINE_RE = re.compile(
    r"^\[GWO_PROGRESS\] step=\d+/\d+ phase=[a-z0-9_]+ status=(started|running|done|failed|skipped) "
    r"elapsed=[0-9]+[hms0-9]* message=.+$"
)


class TestFormatElapsed:
    def test_seconds_only(self):
        assert format_elapsed(0) == "0s"
        assert format_elapsed(45) == "45s"

    def test_minutes_and_seconds(self):
        assert format_elapsed(125) == "2m5s"

    def test_hours(self):
        assert format_elapsed(3661) == "1h1m1s"


class TestSanitizeMessage:
    def test_collapses_whitespace(self):
        assert sanitize_message("  hello   world  ") == "hello world"

    def test_truncates_long_messages(self):
        long_text = "x" * 300
        result = sanitize_message(long_text, max_len=50)
        assert len(result) == 50
        assert result.endswith("...")


class TestFormatProgressLine:
    def test_canonical_format(self):
        line = format_progress_line(
            step=3,
            total=10,
            phase="tests",
            status=ProgressStatus.STARTED,
            elapsed_seconds=12.4,
            message="pytest collect",
        )
        assert line.startswith(GWO_PROGRESS_PREFIX)
        assert "step=3/10" in line
        assert "phase=tests" in line
        assert "status=started" in line
        assert "elapsed=12s" in line
        assert "message=pytest collect" in line
        assert PROGRESS_LINE_RE.match(line)

    def test_accepts_string_status(self):
        line = format_progress_line(
            step=1,
            total=10,
            phase="repo_status",
            status="running",
            elapsed_seconds=30,
            message="alive; last_action=git status",
        )
        assert "status=running" in line
        assert PROGRESS_LINE_RE.match(line)

    def test_all_deploy_phases_are_valid_in_line(self):
        for idx, phase in enumerate(DEPLOY_PHASES, start=1):
            line = format_progress_line(
                step=idx,
                total=len(DEPLOY_PHASES),
                phase=phase,
                status=ProgressStatus.DONE,
                elapsed_seconds=1,
                message=f"phase {phase}",
            )
            assert f"phase={phase}" in line
            assert PROGRESS_LINE_RE.match(line)


class TestPhaseMapping:
    def test_long_workflows_default_progress_on(self):
        assert default_progress_enabled("ifg.deploy.run", explicit=None) is True
        assert default_progress_enabled("core.ping", explicit=None) is False

    def test_explicit_override(self):
        assert default_progress_enabled("ifg.deploy.run", explicit=False) is False
        assert default_progress_enabled("core.ping", explicit=True) is True

    def test_shell_command_phases(self):
        assert phase_for_shell_command("pytest tests/unit -q") == "tests"
        assert phase_for_shell_command("git commit -m test") == "commit"
        assert phase_for_shell_command("git push origin production") == "push"
        assert phase_for_shell_command("git pull origin production") == "remote_pull"

    def test_deploy_stage_phase(self):
        assert phase_for_workflow_stage("ifg.deploy.run", "release_evaluate") == "tests"
        assert phase_for_workflow_stage("ifg.deploy.run", "summary") == "report_write"

    def test_deploy_phase_index(self):
        assert deploy_phase_index("health_check") == 8
        assert deploy_phase_index("unknown") == 0

    def test_long_workflow_ids_contains_deploy(self):
        assert "ifg.deploy.run" in LONG_WORKFLOW_IDS


class TestRenderTimelineSection:
    def test_empty_timeline(self):
        assert render_timeline_section(None) == []
        assert render_timeline_section({"entries": []}) == []

    def test_renders_markdown_table(self):
        lines = render_timeline_section(
            {
                "entries": [
                    {
                        "phase": "tests",
                        "status": "done",
                        "message": "pytest ok",
                        "started_at": "2026-07-07T10:00:00Z",
                        "ended_at": "2026-07-07T10:00:05Z",
                        "duration_ms": 5000,
                    }
                ]
            }
        )
        text = "\n".join(lines)
        assert "## Timeline wykonania" in text
        assert "`tests`" in text
        assert "done" in text
        assert "5000ms" in text


class TestProgressTracker:
    def test_emits_to_stderr_when_enabled(self):
        buf = io.StringIO()
        tracker = ProgressTracker(
            workflow_id="wf-1",
            workflow_type="ifg.deploy.run",
            enabled=True,
            total_steps=10,
            heartbeat_interval=999,
            output=buf,
        )
        tracker.workflow_started("start")
        tracker.stage_started(phase="tests", step=2, message="running pytest")
        tracker.stage_finished(phase="tests", step=2, status=ProgressStatus.DONE, message="ok")
        tracker.workflow_finished(success=True, message="done")

        output = buf.getvalue()
        assert output.count(GWO_PROGRESS_PREFIX) >= 4
        assert "phase=tests" in output
        assert "status=started" in output
        assert "status=done" in output

    def test_disabled_tracker_is_silent(self):
        buf = io.StringIO()
        tracker = ProgressTracker(
            workflow_id="wf-2",
            workflow_type="ifg.deploy.run",
            enabled=False,
            output=buf,
        )
        tracker.workflow_started("start")
        assert buf.getvalue() == ""

    def test_timeline_collects_stage_bounds(self):
        tracker = ProgressTracker(
            workflow_id="wf-3",
            workflow_type="ifg.doctor",
            enabled=False,
            total_steps=10,
        )
        tracker.stage_started(phase="repo_status", step=1, message="init")
        tracker.stage_finished(
            phase="repo_status",
            step=1,
            status=ProgressStatus.DONE,
            message="ready",
        )
        payload = tracker.timeline.to_dict()
        assert len(payload["entries"]) == 1
        entry = payload["entries"][0]
        assert entry["phase"] == "repo_status"
        assert entry["status"] == "done"
        assert entry["started_at"] is not None
        assert entry["ended_at"] is not None
