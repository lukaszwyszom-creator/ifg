from __future__ import annotations

import re
from dataclasses import dataclass

from ifg_guardian.core.progress.protocol import GWO_PROGRESS_PREFIX, ProgressStatus


_PROGRESS_LINE_RE = re.compile(
    r"^"
    + re.escape(GWO_PROGRESS_PREFIX)
    + r" step=(\d+)/(\d+) phase=(\S+) status=(\S+) elapsed=(\S+) message=(.+)$"
)

_WORKFLOW_MESSAGE_RE = re.compile(r"^Workflow\s+(\S+)\s+\(([^)]+)\)")

_ELAPSED_RE = re.compile(r"^(?:(\d+)h)?(?:(\d+)m)?(\d+)s$")


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    step: int
    total: int
    phase: str
    status: str
    elapsed: str
    message: str
    elapsed_seconds: int = 0

    @property
    def is_heartbeat(self) -> bool:
        return self.status == ProgressStatus.RUNNING.value and self.message.startswith("alive;")

    @property
    def is_workflow_start(self) -> bool:
        return self.message.startswith("Workflow ") and " finished (" not in self.message

    @property
    def is_workflow_finish(self) -> bool:
        return self.message.startswith("Workflow ") and " finished (" in self.message


def parse_elapsed_seconds(elapsed: str) -> int:
    match = _ELAPSED_RE.match(elapsed.strip())
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3))
    return hours * 3600 + minutes * 60 + seconds


def parse_progress_line(line: str) -> ProgressEvent | None:
    text = (line or "").strip()
    if not text.startswith(GWO_PROGRESS_PREFIX):
        return None
    match = _PROGRESS_LINE_RE.match(text)
    if not match:
        return None
    elapsed = match.group(5)
    return ProgressEvent(
        step=int(match.group(1)),
        total=int(match.group(2)),
        phase=match.group(3),
        status=match.group(4),
        elapsed=elapsed,
        message=match.group(6),
        elapsed_seconds=parse_elapsed_seconds(elapsed),
    )


def parse_workflow_from_message(message: str) -> tuple[str, str] | None:
    match = _WORKFLOW_MESSAGE_RE.match(message)
    if not match:
        return None
    return match.group(1), match.group(2)
