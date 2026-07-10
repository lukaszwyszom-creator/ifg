from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from ifg_guardian.core.dashboard.eta import estimate_eta_seconds, format_duration
from ifg_guardian.core.dashboard.parser import ProgressEvent, parse_workflow_from_message
from ifg_guardian.core.progress.mapping import DEPLOY_PHASES
from ifg_guardian.core.progress.protocol import ProgressStatus
from ifg_guardian.core.time_compat import UTC


class WorkflowRunStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class PhaseDisplayStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


PHASE_LABELS: dict[str, str] = {
    "repo_status": "repo_status",
    "tests": "tests",
    "commit": "commit",
    "push": "push",
    "remote_pull": "remote_pull",
    "remote_build": "remote_build",
    "restart_services": "restart_services",
    "health_check": "health_check",
    "post_deploy_verification": "verification",
    "report_write": "report",
}


@dataclass(slots=True)
class PhaseView:
    phase_id: str
    label: str
    status: PhaseDisplayStatus = PhaseDisplayStatus.PENDING


@dataclass(slots=True)
class EventView:
    timestamp: str
    message: str


def _default_phases() -> list[PhaseView]:
    return [
        PhaseView(phase_id=phase_id, label=PHASE_LABELS.get(phase_id, phase_id))
        for phase_id in DEPLOY_PHASES
    ]


@dataclass
class DashboardState:
    workflow_type: str = ""
    workflow_mode: str = ""
    run_status: WorkflowRunStatus = WorkflowRunStatus.PENDING
    step: int = 0
    total: int = len(DEPLOY_PHASES)
    current_phase: str = ""
    elapsed_seconds: int = 0
    eta_seconds: int | None = None
    last_action: str = ""
    heartbeat_alive: bool = False
    heartbeat_elapsed_seconds: int = 0
    spinner_frame: int = 0
    phases: list[PhaseView] = field(default_factory=_default_phases)
    events: list[EventView] = field(default_factory=list)
    _phase_status: dict[str, PhaseDisplayStatus] = field(default_factory=dict)

    def advance_spinner(self) -> None:
        self.spinner_frame += 1

    def apply_event(self, event: ProgressEvent) -> None:
        self.step = event.step
        self.total = max(event.total, 1)
        self.current_phase = event.phase
        self.elapsed_seconds = max(self.elapsed_seconds, event.elapsed_seconds)
        self.eta_seconds = estimate_eta_seconds(
            elapsed_seconds=self.elapsed_seconds,
            step=self.step,
            total=self.total,
        )

        if event.is_workflow_start:
            parsed = parse_workflow_from_message(event.message)
            if parsed:
                self.workflow_type, self.workflow_mode = parsed
            self.run_status = WorkflowRunStatus.RUNNING
            self._append_event(event, prefer_message=event.message)
            return

        if event.is_workflow_finish:
            self.run_status = (
                WorkflowRunStatus.SUCCESS
                if "SUCCESS" in event.message
                else WorkflowRunStatus.FAILED
            )
            self._mark_phase(event.phase, PhaseDisplayStatus.DONE if self.run_status == WorkflowRunStatus.SUCCESS else PhaseDisplayStatus.FAILED)
            self._append_event(event, prefer_message=event.message)
            self._sync_phase_views()
            return

        if event.is_heartbeat:
            self.heartbeat_alive = True
            self.heartbeat_elapsed_seconds = event.elapsed_seconds
            if "last_action=" in event.message:
                self.last_action = event.message.split("last_action=", 1)[1].strip()
            return

        self.heartbeat_alive = event.status == ProgressStatus.RUNNING.value

        if event.status == ProgressStatus.STARTED.value:
            self._mark_phase(event.phase, PhaseDisplayStatus.ACTIVE)
            self._append_event(event, prefer_message=_event_summary(event))
        elif event.status == ProgressStatus.DONE.value:
            self._mark_phase(event.phase, PhaseDisplayStatus.DONE)
            self._append_event(event, prefer_message=_event_summary(event))
        elif event.status == ProgressStatus.FAILED.value:
            self._mark_phase(event.phase, PhaseDisplayStatus.FAILED)
            self.run_status = WorkflowRunStatus.FAILED
            self._append_event(event, prefer_message=_event_summary(event))
        elif event.status == ProgressStatus.SKIPPED.value:
            self._mark_phase(event.phase, PhaseDisplayStatus.SKIPPED)
            self._append_event(event, prefer_message=_event_summary(event))
        elif event.status == ProgressStatus.RUNNING.value:
            self._mark_phase(event.phase, PhaseDisplayStatus.ACTIVE)

        if event.message and not event.message.startswith("Stage "):
            if "last_action=" not in event.message:
                self.last_action = event.message
            elif "last_action=" in event.message:
                self.last_action = event.message.split("last_action=", 1)[1].strip()

        self._sync_phase_views()

    @property
    def progress_percent(self) -> int:
        if self.total <= 0:
            return 0
        if self.run_status in (WorkflowRunStatus.SUCCESS, WorkflowRunStatus.FAILED):
            return 100
        return min(100, max(0, int((self.step / self.total) * 100)))

    @property
    def progress_bar(self) -> str:
        width = 18
        filled = int(width * self.progress_percent / 100)
        return "█" * filled + "░" * (width - filled)

    @property
    def elapsed_label(self) -> str:
        return format_duration(self.elapsed_seconds)

    @property
    def eta_label(self) -> str:
        if self.eta_seconds is None:
            return "—"
        return format_duration(self.eta_seconds)

    def _mark_phase(self, phase: str, status: PhaseDisplayStatus) -> None:
        self._phase_status[phase] = status
        if phase in DEPLOY_PHASES:
            idx = DEPLOY_PHASES.index(phase)
            if status == PhaseDisplayStatus.DONE:
                for earlier in DEPLOY_PHASES[:idx]:
                    if self._phase_status.get(earlier) not in (
                        PhaseDisplayStatus.DONE,
                        PhaseDisplayStatus.SKIPPED,
                        PhaseDisplayStatus.FAILED,
                    ):
                        self._phase_status[earlier] = PhaseDisplayStatus.DONE

    def _sync_phase_views(self) -> None:
        self.phases = []
        for phase_id in DEPLOY_PHASES:
            self.phases.append(
                PhaseView(
                    phase_id=phase_id,
                    label=PHASE_LABELS.get(phase_id, phase_id),
                    status=self._phase_status.get(phase_id, PhaseDisplayStatus.PENDING),
                )
            )

    def _append_event(self, event: ProgressEvent, *, prefer_message: str) -> None:
        ts = datetime.now(UTC).strftime("%H:%M")
        self.events.append(EventView(timestamp=ts, message=prefer_message))
        if len(self.events) > 20:
            self.events = self.events[-20:]


def _event_summary(event: ProgressEvent) -> str:
    if event.message.startswith("Stage "):
        return event.message
    if len(event.message) > 72:
        return event.message[:69] + "..."
    return event.message
