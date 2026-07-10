from __future__ import annotations

import re
from enum import StrEnum


GWO_PROGRESS_PREFIX = "[GWO_PROGRESS]"


class ProgressStatus(StrEnum):
    STARTED = "started"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


def format_elapsed(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h{minutes}m{secs}s"
    if minutes:
        return f"{minutes}m{secs}s"
    return f"{secs}s"


def sanitize_message(message: str, *, max_len: int = 240) -> str:
    cleaned = re.sub(r"\s+", " ", (message or "").strip())
    if len(cleaned) > max_len:
        return cleaned[: max_len - 3] + "..."
    return cleaned


def format_progress_line(
    *,
    step: int,
    total: int,
    phase: str,
    status: ProgressStatus | str,
    elapsed_seconds: float,
    message: str,
) -> str:
    status_value = status.value if isinstance(status, ProgressStatus) else str(status)
    return (
        f"{GWO_PROGRESS_PREFIX} "
        f"step={step}/{total} "
        f"phase={phase} "
        f"status={status_value} "
        f"elapsed={format_elapsed(elapsed_seconds)} "
        f"message={sanitize_message(message)}"
    )
