from __future__ import annotations

import sys
import threading
from typing import Callable, TextIO

from ifg_guardian.core.dashboard.model import DashboardState
from ifg_guardian.core.dashboard.parser import parse_progress_line
from ifg_guardian.core.progress.protocol import GWO_PROGRESS_PREFIX


class ProgressStderrSink:
    """Intercept stderr writes and feed parsed [GWO_PROGRESS] lines to dashboard state."""

    def __init__(
        self,
        real_stderr: TextIO,
        state: DashboardState,
        *,
        suppress_progress_lines: bool = True,
    ) -> None:
        self._real = real_stderr
        self._state = state
        self._suppress_progress_lines = suppress_progress_lines
        self._buffer = ""
        self._lock = threading.Lock()

    def write(self, data: str) -> int:
        if not data:
            return 0
        if not self._suppress_progress_lines:
            return self._real.write(data)

        with self._lock:
            self._buffer += data
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                self._handle_line(line)
        return len(data)

    def flush(self) -> None:
        with self._lock:
            if self._buffer:
                self._handle_line(self._buffer.rstrip("\n"))
                self._buffer = ""
        self._real.flush()

    def fileno(self) -> int:
        return self._real.fileno()

    def isatty(self) -> bool:
        return self._real.isatty()

    @property
    def encoding(self) -> str:
        return getattr(self._real, "encoding", "utf-8")

    def _handle_line(self, line: str) -> None:
        if line.startswith(GWO_PROGRESS_PREFIX):
            event = parse_progress_line(line)
            if event is not None:
                self._state.apply_event(event)
            return
        if line.strip():
            self._real.write(line + "\n")
