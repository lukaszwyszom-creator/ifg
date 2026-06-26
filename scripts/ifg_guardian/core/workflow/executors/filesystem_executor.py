from __future__ import annotations

from pathlib import Path

from ifg_guardian.core.workflow.intents import FsExistsIntent
from ifg_guardian.core.workflow.results import IntentResult


class FilesystemExecutor:
    def __init__(self, *, root: Path) -> None:
        self.root = root

    def execute_exists(self, intent: FsExistsIntent) -> IntentResult:
        path = self.root / intent.path
        exists = path.exists()
        return IntentResult(
            intent=intent,
            ok=True,
            output=f"exists={exists}",
            data={"path": str(path), "exists": exists},
        )
