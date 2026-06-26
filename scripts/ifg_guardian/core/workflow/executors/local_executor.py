from __future__ import annotations

import subprocess
from pathlib import Path

from ifg_guardian.core.workflow.intents import LocalExecIntent
from ifg_guardian.core.workflow.results import IntentResult


class LocalExecutor:
    """Execute commands on the local machine (LIVE subprocess)."""

    def __init__(self, *, root: Path) -> None:
        self.root = root

    def execute(self, intent: LocalExecIntent) -> IntentResult:
        cwd = Path(intent.cwd) if intent.cwd else self.root
        try:
            result = subprocess.run(
                intent.command,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            return IntentResult(intent=intent, ok=False, error=str(exc))

        output = (result.stdout or result.stderr or "").strip()
        if result.returncode != 0:
            return IntentResult(
                intent=intent,
                ok=False,
                output=output,
                error=f"exit {result.returncode}",
            )
        return IntentResult(intent=intent, ok=True, output=output)
