from __future__ import annotations

import subprocess
from pathlib import Path

from ifg_guardian.core.workflow.intents import GitFetchIntent, GitRevParseIntent, GitStatusIntent
from ifg_guardian.core.workflow.results import IntentResult


class GitExecutor:
    def __init__(self, *, root: Path) -> None:
        self.root = root

    def _run_git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )

    def execute_rev_parse(self, intent: GitRevParseIntent) -> IntentResult:
        result = self._run_git("rev-parse", intent.ref)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            return IntentResult(intent=intent, ok=False, error=detail or "git rev-parse failed")
        sha = result.stdout.strip()
        return IntentResult(
            intent=intent,
            ok=True,
            output=sha,
            data={"ref": intent.ref, "sha": sha},
        )

    def execute_fetch(self, intent: GitFetchIntent) -> IntentResult:
        result = self._run_git("fetch", intent.remote, intent.branch, "--quiet")
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            return IntentResult(intent=intent, ok=False, error=detail or "git fetch failed")
        return IntentResult(intent=intent, ok=True, output="fetch ok")

    def execute_status(self, intent: GitStatusIntent) -> IntentResult:
        args = ("status", "--porcelain") if intent.porcelain else ("status",)
        result = self._run_git(*args)
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
