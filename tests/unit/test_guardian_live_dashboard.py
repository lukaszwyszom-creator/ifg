from __future__ import annotations

from ifg_guardian.core.dashboard.eta import estimate_eta_seconds, format_duration
from ifg_guardian.core.dashboard.model import DashboardState, PhaseDisplayStatus, WorkflowRunStatus
from ifg_guardian.core.dashboard.parser import parse_elapsed_seconds, parse_progress_line
from ifg_guardian.core.dashboard.renderer import phase_icon, render_dashboard_plain
from ifg_guardian.core.progress.protocol import format_progress_line, ProgressStatus


def _line(**kwargs) -> str:
    defaults = {
        "step": 1,
        "total": 10,
        "phase": "repo_status",
        "status": ProgressStatus.STARTED,
        "elapsed_seconds": 0.0,
        "message": "test",
    }
    defaults.update(kwargs)
    return format_progress_line(**defaults)


class TestParser:
    def test_parse_progress_line_roundtrip(self):
        raw = _line(
            step=6,
            total=10,
            phase="remote_build",
            status=ProgressStatus.RUNNING,
            elapsed_seconds=494.0,
            message="alive; last_action=docker build worker",
        )
        event = parse_progress_line(raw)
        assert event is not None
        assert event.step == 6
        assert event.total == 10
        assert event.phase == "remote_build"
        assert event.status == "running"
        assert event.elapsed == "8m14s"
        assert event.elapsed_seconds == 494
        assert event.is_heartbeat is True

    def test_parse_elapsed_variants(self):
        assert parse_elapsed_seconds("45s") == 45
        assert parse_elapsed_seconds("2m5s") == 125
        assert parse_elapsed_seconds("1h1m1s") == 3661

    def test_parse_invalid_line_returns_none(self):
        assert parse_progress_line("not progress") is None


class TestEta:
    def test_estimate_eta_linear(self):
        assert estimate_eta_seconds(elapsed_seconds=100, step=5, total=10) == 100

    def test_estimate_eta_none_at_start(self):
        assert estimate_eta_seconds(elapsed_seconds=0, step=1, total=10) is None


class TestFormatDuration:
    def test_format_duration(self):
        assert format_duration(494) == "08m 14s"
        assert format_duration(45) == "00m 45s"


class TestDashboardState:
    def test_workflow_start_and_finish(self):
        state = DashboardState()
        start = parse_progress_line(
            _line(
                message="Workflow ifg.deploy.run (DRY_RUN)",
                phase="repo_status",
                status=ProgressStatus.STARTED,
            )
        )
        finish = parse_progress_line(
            _line(
                step=10,
                phase="report_write",
                status=ProgressStatus.DONE,
                elapsed_seconds=600.0,
                message="Workflow ifg.deploy.run finished (SUCCESS)",
            )
        )
        assert start is not None and finish is not None
        state.apply_event(start)
        assert state.workflow_type == "ifg.deploy.run"
        assert state.run_status == WorkflowRunStatus.RUNNING

        state.apply_event(finish)
        assert state.run_status == WorkflowRunStatus.SUCCESS
        assert state.progress_percent == 100

    def test_phase_progression(self):
        state = DashboardState()
        for phase, step in (
            ("repo_status", 1),
            ("tests", 2),
            ("remote_pull", 5),
            ("remote_build", 6),
        ):
            started = parse_progress_line(
                _line(step=step, phase=phase, status=ProgressStatus.STARTED, message=f"Stage {phase}")
            )
            done = parse_progress_line(
                _line(
                    step=step,
                    phase=phase,
                    status=ProgressStatus.DONE,
                    elapsed_seconds=float(step * 10),
                    message=f"{phase} ok",
                )
            )
            assert started is not None and done is not None
            state.apply_event(started)
            state.apply_event(done)

        active = [p for p in state.phases if p.status == PhaseDisplayStatus.ACTIVE]
        done = [p for p in state.phases if p.status == PhaseDisplayStatus.DONE]
        assert not active
        assert len(done) >= 4

    def test_heartbeat_updates_last_action(self):
        state = DashboardState()
        event = parse_progress_line(
            _line(
                step=6,
                phase="remote_build",
                status=ProgressStatus.RUNNING,
                elapsed_seconds=30.0,
                message="alive; last_action=docker build worker",
            )
        )
        assert event is not None
        state.apply_event(event)
        assert state.heartbeat_alive is True
        assert state.last_action == "docker build worker"

    def test_event_history_capped_at_20(self):
        state = DashboardState()
        for idx in range(25):
            event = parse_progress_line(
                _line(
                    step=1,
                    phase="repo_status",
                    status=ProgressStatus.STARTED,
                    message=f"event-{idx}",
                )
            )
            assert event is not None
            state.apply_event(event)
        assert len(state.events) == 20
        assert state.events[0].message == "event-5"

    def test_progress_bar_percent(self):
        state = DashboardState()
        event = parse_progress_line(
            _line(step=6, total=10, status=ProgressStatus.STARTED, elapsed_seconds=1.0)
        )
        assert event is not None
        state.apply_event(event)
        assert state.progress_percent == 60
        assert "██████" in state.progress_bar


class TestRenderer:
    def test_render_dashboard_plain_contains_sections(self):
        state = DashboardState()
        state.workflow_type = "ifg.deploy.run"
        state.run_status = WorkflowRunStatus.RUNNING
        state.step = 6
        state.total = 10
        state.current_phase = "remote_build"
        state.elapsed_seconds = 494
        state.eta_seconds = 182
        state.last_action = "docker build worker"
        state.heartbeat_alive = True
        state.phases[5].status = PhaseDisplayStatus.ACTIVE
        for idx in range(5):
            state.phases[idx].status = PhaseDisplayStatus.DONE

        text = render_dashboard_plain(state)
        assert "Guardian" in text
        assert "ifg.deploy.run" in text
        assert "RUNNING" in text
        assert "remote_build" in text
        assert "6 / 10" in text
        assert "08m 14s" in text
        assert "03m 02s" in text
        assert "docker build worker" in text
        assert "▶ remote_build" in text
        assert "✔ repo_status" in text
        assert "Heartbeat" in text
        assert "Ostatnie zdarzenia" in text

    def test_phase_icons(self):
        assert phase_icon(PhaseDisplayStatus.DONE) == "✔"
        assert phase_icon(PhaseDisplayStatus.ACTIVE) == "▶"
        assert phase_icon(PhaseDisplayStatus.PENDING) == "○"
