"""Notification sink for Guardian runtime monitor (extensible, no secrets in repo)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ifg_guardian.core.runtime_store import STATE_DIR, ensure_state_dir

NOTIFY_LOG = STATE_DIR / "runtime_notifications.log"


@dataclass(frozen=True)
class RuntimeNotification:
    level: str
    title: str
    body: str

    def format_line(self) -> str:
        stamp = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        return f"{stamp} [{self.level}] {self.title}: {self.body}\n"


class RuntimeNotifier:
    """Default sink: append-only local log. External channels plug in here."""

    def __init__(self, log_path: Path = NOTIFY_LOG) -> None:
        self.log_path = log_path

    def send(self, notification: RuntimeNotification) -> bool:
        ensure_state_dir()
        line = notification.format_line()
        try:
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.flush()
            return True
        except OSError:
            return False

    @property
    def channel_name(self) -> str:
        return "local_log"


def default_notifier() -> RuntimeNotifier:
    return RuntimeNotifier()
