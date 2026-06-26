from __future__ import annotations

from pathlib import Path

from guardian_platform.core.workflow.intents import (
    ActionIntent,
    FsExistsIntent,
    GitRevParseIntent,
    GitStatusIntent,
    NoOpIntent,
)
from guardian_platform.core.runtime.mode import ExecutionMode
from guardian_platform.core.workflow.results import IntentResult
from guardian_platform.core.shell.runner import run_command


class IntentExecutor:
    def __init__(self, *, root: Path) -> None:
        self.root = root

    def execute(self, intent: ActionIntent, mode: ExecutionMode) -> IntentResult:
        if mode.simulates_mutations and intent.mutating:
            return IntentResult(
                intent=intent,
                ok=True,
                simulated=True,
                output=f"[dry-run] would: {intent.describe()}",
            )

        if isinstance(intent, NoOpIntent):
            return IntentResult(intent=intent, ok=True, output=intent.reason or "ok")

        if isinstance(intent, FsExistsIntent):
            path = self.root / intent.path
            exists = path.exists()
            return IntentResult(
                intent=intent,
                ok=True,
                output=f"exists={exists}",
                data={"path": str(path), "exists": exists},
            )

        if isinstance(intent, GitRevParseIntent):
            return self._git_rev_parse(intent)

        if isinstance(intent, GitStatusIntent):
            return self._git_status(intent)

        return IntentResult(intent=intent, ok=False, error=f"unknown intent: {intent.intent_type}")

    def _git_rev_parse(self, intent: GitRevParseIntent) -> IntentResult:
        result = run_command(["git", "rev-parse", intent.ref], cwd=self.root)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            return IntentResult(intent=intent, ok=False, error=detail or "git rev-parse failed")
        sha = result.stdout.strip()
        return IntentResult(intent=intent, ok=True, output=sha, data={"ref": intent.ref, "sha": sha})

    def _git_status(self, intent: GitStatusIntent) -> IntentResult:
        args = ["git", "status", "--porcelain"] if intent.porcelain else ["git", "status"]
        result = run_command(args, cwd=self.root)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            return IntentResult(intent=intent, ok=False, error=detail or "git status failed")
        porcelain = result.stdout.strip()
        return IntentResult(
            intent=intent,
            ok=True,
            output=porcelain,
            data={"porcelain": porcelain, "dirty": bool(porcelain)},
        )
