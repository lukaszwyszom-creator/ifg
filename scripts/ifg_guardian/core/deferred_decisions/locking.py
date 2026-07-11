"""Local file lock for GDD registry writes (Mac mini orchestration host)."""
from __future__ import annotations

import fcntl
import os
import time
from pathlib import Path

from ifg_guardian.config import ROOT

LOCK_PATH = ROOT / ".state" / "gdd_registry.lock"
DEFAULT_TIMEOUT_SECONDS = 10.0
POLL_INTERVAL_SECONDS = 0.05


class GddRegistryLockError(RuntimeError):
    pass


class GddRegistryLock:
    def __init__(
        self,
        *,
        lock_path: Path = LOCK_PATH,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        blocking: bool = True,
    ) -> None:
        self.lock_path = lock_path
        self.timeout_seconds = timeout_seconds
        self.blocking = blocking
        self._fd: int | None = None

    def __enter__(self) -> GddRegistryLock:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR, 0o600)
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except BlockingIOError as exc:
                if not self.blocking or time.monotonic() >= deadline:
                    os.close(self._fd)
                    self._fd = None
                    raise GddRegistryLockError(
                        f"GDD registry lock timeout after {self.timeout_seconds}s"
                    ) from exc
                time.sleep(POLL_INTERVAL_SECONDS)

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            finally:
                os.close(self._fd)
                self._fd = None
