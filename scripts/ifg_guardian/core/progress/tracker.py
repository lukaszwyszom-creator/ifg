from __future__ import annotations

import sys
import threading
from datetime import datetime
from time import perf_counter

from ifg_guardian.core.progress.protocol import ProgressStatus, format_progress_line, sanitize_message
from ifg_guardian.core.progress.timeline import ProgressTimeline, TimelineEntry
from ifg_guardian.core.time_compat import UTC
from ifg_guardian.core.workflow.stage import StageStatus


HEARTBEAT_INTERVAL_SECONDS = 30


class ProgressTracker:
    """Emit [GWO_PROGRESS] lines and collect execution timeline (observability only)."""

    def __init__(
        self,
        *,
        workflow_id: str,
        workflow_type: str,
        enabled: bool = True,
        total_steps: int = 10,
        heartbeat_interval: float = HEARTBEAT_INTERVAL_SECONDS,
        output=None,
    ) -> None:
        self.workflow_id = workflow_id
        self.workflow_type = workflow_type
        self.enabled = enabled
        self.total_steps = max(1, total_steps)
        self.heartbeat_interval = heartbeat_interval
        self._output = output or sys.stderr
        self.timeline = ProgressTimeline(workflow_id=workflow_id, workflow_type=workflow_type)
        self._workflow_started = perf_counter()
        self._stage_started: float | None = None
        self._current_phase: str | None = None
        self._current_step = 0
        self._last_action = ""
        self._lock = threading.Lock()
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None
        self._open_entry: TimelineEntry | None = None

    def workflow_started(self, message: str) -> None:
        self._emit(
            step=1,
            phase="repo_status",
            status=ProgressStatus.STARTED,
            elapsed=self._workflow_elapsed(),
            message=message,
            record_timeline=False,
        )

    def workflow_finished(self, *, success: bool, message: str) -> None:
        self._stop_heartbeat()
        status = ProgressStatus.DONE if success else ProgressStatus.FAILED
        self._emit(
            step=self.total_steps,
            phase="report_write",
            status=status,
            elapsed=self._workflow_elapsed(),
            message=message,
            record_timeline=True,
            close_open=True,
        )

    def stage_started(self, *, phase: str, step: int | None, message: str) -> None:
        self._stop_heartbeat()
        self._current_phase = phase
        self._current_step = step if step is not None else max(1, self._current_step + 1)
        self._stage_started = perf_counter()
        self._open_entry = TimelineEntry(
            phase=phase,
            status=ProgressStatus.STARTED.value,
            message=sanitize_message(message),
            step=self._current_step,
            total=self.total_steps,
            started_at=datetime.now(UTC),
        )
        self._emit(
            step=self._current_step,
            phase=phase,
            status=ProgressStatus.STARTED,
            elapsed=self._stage_elapsed(),
            message=message,
            record_timeline=False,
        )
        self._start_heartbeat()

    def stage_finished(
        self,
        *,
        phase: str | None,
        status: ProgressStatus,
        message: str,
        step: int | None = None,
    ) -> None:
        self._stop_heartbeat()
        resolved_phase = phase or self._current_phase or "repo_status"
        resolved_step = step if step is not None else self._current_step or 1
        self._emit(
            step=resolved_step,
            phase=resolved_phase,
            status=status,
            elapsed=self._stage_elapsed(),
            message=message,
            record_timeline=True,
            close_open=True,
        )
        self._current_phase = None
        self._stage_started = None

    def stage_from_result(self, *, phase: str, step: int | None, stage_status: StageStatus, message: str) -> None:
        if stage_status == StageStatus.SKIP:
            self.stage_finished(phase=phase, step=step, status=ProgressStatus.SKIPPED, message=message)
        elif stage_status == StageStatus.FAIL:
            self.stage_finished(phase=phase, step=step, status=ProgressStatus.FAILED, message=message)
        else:
            self.stage_finished(phase=phase, step=step, status=ProgressStatus.DONE, message=message)

    def intent_started(self, *, phase: str, message: str, step: int | None = None) -> None:
        resolved_step = step if step is not None else self._current_step or deploy_step_for_phase(phase)
        self.stage_started(phase=phase, step=resolved_step, message=message)

    def intent_finished(self, *, phase: str, ok: bool, message: str, step: int | None = None) -> None:
        status = ProgressStatus.DONE if ok else ProgressStatus.FAILED
        self.stage_finished(phase=phase, step=step, status=status, message=message)

    def note_action(self, action: str) -> None:
        with self._lock:
            self._last_action = sanitize_message(action, max_len=160)

    def error(self, *, phase: str, message: str, step: int | None = None) -> None:
        self._stop_heartbeat()
        resolved_step = step if step is not None else self._current_step or 1
        self._emit(
            step=resolved_step,
            phase=phase,
            status=ProgressStatus.FAILED,
            elapsed=self._stage_elapsed(),
            message=message,
            record_timeline=True,
            close_open=True,
        )

    def _workflow_elapsed(self) -> float:
        return perf_counter() - self._workflow_started

    def _stage_elapsed(self) -> float:
        if self._stage_started is None:
            return self._workflow_elapsed()
        return perf_counter() - self._stage_started

    def _emit(
        self,
        *,
        step: int,
        phase: str,
        status: ProgressStatus,
        elapsed: float,
        message: str,
        record_timeline: bool,
        close_open: bool = False,
    ) -> None:
        line = format_progress_line(
            step=step,
            total=self.total_steps,
            phase=phase,
            status=status,
            elapsed_seconds=elapsed,
            message=message,
        )
        if self.enabled:
            print(line, file=self._output, flush=True)

        if record_timeline:
            now = datetime.now(UTC)
            entry = TimelineEntry(
                phase=phase,
                status=status.value,
                message=sanitize_message(message),
                step=step,
                total=self.total_steps,
                last_action=self._last_action,
                ended_at=now,
            )
            if self._open_entry is not None and close_open:
                entry.started_at = self._open_entry.started_at
                entry.duration_ms = int(elapsed * 1000)
            elif close_open:
                entry.duration_ms = int(elapsed * 1000)
            self.timeline.add(entry)
            if close_open:
                self._open_entry = None

    def _heartbeat_loop(self) -> None:
        while not self._heartbeat_stop.wait(self.heartbeat_interval):
            with self._lock:
                phase = self._current_phase
                action = self._last_action
                step = self._current_step
            if not phase:
                continue
            msg = f"alive; last_action={action or 'n/a'}"
            self._emit(
                step=step or 1,
                phase=phase,
                status=ProgressStatus.RUNNING,
                elapsed=self._stage_elapsed(),
                message=msg,
                record_timeline=False,
            )

    def _start_heartbeat(self) -> None:
        if not self.enabled:
            return
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name=f"gwo-progress-{self.workflow_id}",
            daemon=True,
        )
        self._heartbeat_thread.start()

    def _stop_heartbeat(self) -> None:
        self._heartbeat_stop.set()
        thread = self._heartbeat_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=0.5)
        self._heartbeat_thread = None


def deploy_step_for_phase(phase: str) -> int:
    from ifg_guardian.core.progress.mapping import DEPLOY_PHASES

    try:
        return DEPLOY_PHASES.index(phase) + 1
    except ValueError:
        return 1


def create_progress_tracker(
    *,
    workflow_id: str,
    workflow_type: str,
    enabled: bool,
    total_steps: int = 10,
) -> ProgressTracker:
    return ProgressTracker(
        workflow_id=workflow_id,
        workflow_type=workflow_type,
        enabled=enabled,
        total_steps=total_steps,
    )
