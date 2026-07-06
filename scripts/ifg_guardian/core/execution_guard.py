"""Block mutating production workflows when Guardian runs on the DS723+ target host."""
from __future__ import annotations

import socket
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from ifg_guardian.config import DEFAULT_REMOTE_PATH, ROOT
from ifg_guardian.core.workflow.definition import WorkflowDefinition
from ifg_guardian.core.workflow.mode import ExecutionMode

LIVE_BLOCKED_MESSAGE = (
    "This workflow must be executed from the orchestration host (Mac mini). "
    "DS723+ is an execution target only. Run this command from Mac mini."
)

DRY_RUN_WARNING_MESSAGE = (
    "Dry-run on DS723+ is diagnostic only. LIVE execution must be started from Mac mini."
)

DS723_HOSTNAME_MARKERS = ("ds723",)


class ExecutionGuardStatus(str, Enum):
    GO = "GO"
    NO_GO = "NO_GO"
    WARN = "WARN"


class ExecutionGuardError(RuntimeError):
    """Mutating workflow blocked on DS723+ execution target."""

    def __init__(self, message: str, *, signals: list[str] | None = None) -> None:
        super().__init__(message)
        self.signals = list(signals or [])


@dataclass(frozen=True)
class ExecutionGuardDecision:
    status: ExecutionGuardStatus
    message: str | None = None
    signals: list[str] = field(default_factory=list)

    @property
    def allowed(self) -> bool:
        return self.status != ExecutionGuardStatus.NO_GO


def detect_ds723_target_signals(
    *,
    hostname: str | None = None,
    root: Path | None = None,
    cwd: Path | None = None,
    remote_path: str | None = None,
) -> list[str]:
    """Return stable environment signals indicating Guardian runs on DS723+."""
    signals: list[str] = []
    resolved_hostname = hostname or socket.gethostname()
    host = resolved_hostname.lower()

    for marker in DS723_HOSTNAME_MARKERS:
        if marker in host:
            signals.append(f"hostname={resolved_hostname}")
            break

    prod_repo = Path(remote_path or DEFAULT_REMOTE_PATH)
    candidates: list[Path] = []
    if root is not None:
        candidates.append(Path(root))
    if cwd is not None:
        candidates.append(Path(cwd))
    else:
        try:
            candidates.append(Path.cwd())
        except OSError:
            pass

    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        resolved_str = str(resolved)
        prod_str = str(prod_repo)
        if resolved_str == prod_str or resolved_str.startswith(prod_str + "/"):
            signals.append(f"repo_path={resolved_str}")
        elif resolved_str.startswith("/volume1/"):
            signals.append(f"synology_volume={resolved_str}")

    return signals


def is_ds723_target_host(**kwargs) -> bool:
    return bool(detect_ds723_target_signals(**kwargs))


def check_execution_guard(
    *,
    workflow: WorkflowDefinition,
    mode: ExecutionMode,
    root: Path | None = None,
    hostname: str | None = None,
    cwd: Path | None = None,
    remote_path: str | None = None,
) -> ExecutionGuardDecision:
    if not workflow.mutating:
        return ExecutionGuardDecision(status=ExecutionGuardStatus.GO)

    signals = detect_ds723_target_signals(
        hostname=hostname,
        root=root or ROOT,
        cwd=cwd,
        remote_path=remote_path,
    )
    if not signals:
        return ExecutionGuardDecision(status=ExecutionGuardStatus.GO)

    if mode == ExecutionMode.LIVE:
        return ExecutionGuardDecision(
            status=ExecutionGuardStatus.NO_GO,
            message=LIVE_BLOCKED_MESSAGE,
            signals=signals,
        )

    if mode.simulates_mutations:
        return ExecutionGuardDecision(
            status=ExecutionGuardStatus.WARN,
            message=DRY_RUN_WARNING_MESSAGE,
            signals=signals,
        )

    return ExecutionGuardDecision(status=ExecutionGuardStatus.GO, signals=signals)


def enforce_execution_guard(
    *,
    workflow: WorkflowDefinition,
    mode: ExecutionMode,
    root: Path | None = None,
    hostname: str | None = None,
    cwd: Path | None = None,
    remote_path: str | None = None,
    emit_warnings: bool = True,
) -> ExecutionGuardDecision:
    decision = check_execution_guard(
        workflow=workflow,
        mode=mode,
        root=root,
        hostname=hostname,
        cwd=cwd,
        remote_path=remote_path,
    )
    if decision.status == ExecutionGuardStatus.NO_GO:
        raise ExecutionGuardError(decision.message or LIVE_BLOCKED_MESSAGE, signals=decision.signals)
    if emit_warnings and decision.status == ExecutionGuardStatus.WARN and decision.message:
        print(f"⚠️  {decision.message}", file=sys.stderr)
    return decision


def enforce_mutating_live_orchestration(
    *,
    dry_run: bool = False,
    root: Path | None = None,
    hostname: str | None = None,
    remote_path: str | None = None,
    emit_warnings: bool = True,
) -> None:
    """Guard mutating CLI paths that bypass WorkflowDefinition (rollback, prod recover)."""
    signals = detect_ds723_target_signals(
        hostname=hostname,
        root=root,
        remote_path=remote_path,
    )
    if not signals:
        return

    if dry_run:
        if emit_warnings:
            print(f"⚠️  {DRY_RUN_WARNING_MESSAGE}", file=sys.stderr)
        return

    raise ExecutionGuardError(LIVE_BLOCKED_MESSAGE, signals=signals)
