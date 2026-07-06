"""Unit tests for Guardian execution guard (Mac orchestration host only)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian.core.execution_guard import (  # noqa: E402
    DRY_RUN_WARNING_MESSAGE,
    LIVE_BLOCKED_MESSAGE,
    ExecutionGuardError,
    ExecutionGuardStatus,
    check_execution_guard,
    detect_ds723_target_signals,
    enforce_execution_guard,
    enforce_mutating_live_orchestration,
)
from ifg_guardian.core.plugins.bootstrap import create_runtime  # noqa: E402
from ifg_guardian.core.workflow.definition import WorkflowDefinition  # noqa: E402
from ifg_guardian.core.workflow.engine import ExecutionEngine  # noqa: E402
from ifg_guardian.core.workflow.mode import ExecutionMode  # noqa: E402
from ifg_guardian.core.workflow.stage import Stage, StagePlan, StageResult, StageStatus  # noqa: E402
from ifg_guardian.modules.ifg_container_cutover import execute_ifg_container_cutover  # noqa: E402


class _NoOpStage(Stage):
    id = "noop"

    def build_plan(self, ctx):
        return StagePlan(intents=[])

    def interpret(self, ctx, results):
        return StageResult(status=StageStatus.PASS)


def _mutating_workflow() -> WorkflowDefinition:
    return WorkflowDefinition(
        id="test.mutating",
        label="test",
        mutating=True,
        stages=[_NoOpStage()],
    )


class TestDs723Detection:
    def test_hostname_ds723plus(self):
        signals = detect_ds723_target_signals(hostname="DS723plus")
        assert any(s.startswith("hostname=") for s in signals)

    def test_prod_repo_path(self, tmp_path: Path):
        repo = tmp_path / "ifg_standalone"
        repo.mkdir()
        signals = detect_ds723_target_signals(root=repo, remote_path=str(repo))
        assert any("repo_path=" in s for s in signals)

    def test_mac_paths_not_detected(self, tmp_path: Path):
        signals = detect_ds723_target_signals(
            hostname="Mac-mini.local",
            root=tmp_path / "projekty" / "ifg_standalone",
        )
        assert signals == []


class TestExecutionGuard:
    def test_live_mutating_blocked_on_ds723_hostname(self):
        decision = check_execution_guard(
            workflow=_mutating_workflow(),
            mode=ExecutionMode.LIVE,
            hostname="DS723plus",
            root=Path("/tmp/guardian-test"),
        )
        assert decision.status == ExecutionGuardStatus.NO_GO
        assert decision.message == LIVE_BLOCKED_MESSAGE

    def test_live_mutating_blocked_on_prod_repo_path(self, tmp_path: Path):
        repo = tmp_path / "ifg_standalone"
        repo.mkdir()
        decision = check_execution_guard(
            workflow=_mutating_workflow(),
            mode=ExecutionMode.LIVE,
            hostname="Mac-mini.local",
            root=repo,
            remote_path=str(repo),
        )
        assert decision.status == ExecutionGuardStatus.NO_GO

    def test_dry_run_allowed_with_warning_on_ds723(self, capsys):
        decision = enforce_execution_guard(
            workflow=_mutating_workflow(),
            mode=ExecutionMode.DRY_RUN,
            hostname="DS723plus",
            root=Path("/tmp/guardian-test"),
        )
        assert decision.status == ExecutionGuardStatus.WARN
        assert decision.allowed is True
        captured = capsys.readouterr()
        assert DRY_RUN_WARNING_MESSAGE in captured.err

    def test_mac_orchestration_host_allowed(self, tmp_path: Path):
        decision = check_execution_guard(
            workflow=_mutating_workflow(),
            mode=ExecutionMode.LIVE,
            hostname="Mac-mini.local",
            root=tmp_path,
        )
        assert decision.status == ExecutionGuardStatus.GO
        assert decision.allowed is True

    def test_non_mutating_workflow_allowed_on_ds723(self):
        workflow = WorkflowDefinition(id="test.readonly", label="test", mutating=False, stages=[])
        decision = check_execution_guard(
            workflow=workflow,
            mode=ExecutionMode.LIVE,
            hostname="DS723plus",
        )
        assert decision.status == ExecutionGuardStatus.GO


class TestExecutionEngineIntegration:
    def test_engine_blocks_live_mutating_on_ds723(self, monkeypatch):
        monkeypatch.setattr(
            "ifg_guardian.core.execution_guard.socket.gethostname",
            lambda: "DS723plus",
        )
        engine = ExecutionEngine()
        with pytest.raises(ExecutionGuardError, match="orchestration host"):
            engine.run(_mutating_workflow(), mode=ExecutionMode.LIVE)

    def test_engine_allows_dry_run_on_ds723_with_warning(self, monkeypatch, capsys):
        monkeypatch.setattr(
            "ifg_guardian.core.execution_guard.socket.gethostname",
            lambda: "DS723plus",
        )
        engine = ExecutionEngine()
        ctx = engine.run(_mutating_workflow(), mode=ExecutionMode.DRY_RUN)
        assert ctx.transaction.outcome == "SUCCESS"
        captured = capsys.readouterr()
        assert DRY_RUN_WARNING_MESSAGE in captured.err


class TestCutoverWorkflowGuard:
    def test_live_cutover_blocked_on_ds723(self, monkeypatch):
        monkeypatch.setattr(
            "ifg_guardian.core.execution_guard.socket.gethostname",
            lambda: "DS723plus",
        )
        with pytest.raises(ExecutionGuardError, match="orchestration host"):
            execute_ifg_container_cutover(dry_run=False, assume_yes=True)

    def test_dry_run_cutover_allowed_on_ds723(self, monkeypatch, capsys):
        monkeypatch.setattr(
            "ifg_guardian.core.execution_guard.socket.gethostname",
            lambda: "DS723plus",
        )
        ctx = execute_ifg_container_cutover(dry_run=True)
        assert ctx.transaction.outcome == "SUCCESS"
        captured = capsys.readouterr()
        assert DRY_RUN_WARNING_MESSAGE in captured.err

    def test_registered_cutover_is_mutating(self):
        runtime = create_runtime()
        try:
            wf = runtime.resolve_workflow("ifg.container.cutover")
            assert wf is not None
            assert wf.mutating is True
        finally:
            runtime.shutdown()


class TestMutatingCliGuard:
    def test_rollback_live_blocked_on_ds723(self, monkeypatch):
        monkeypatch.setattr(
            "ifg_guardian.core.execution_guard.socket.gethostname",
            lambda: "DS723plus",
        )
        with pytest.raises(ExecutionGuardError):
            enforce_mutating_live_orchestration(dry_run=False)

    def test_rollback_dry_run_warns_on_ds723(self, monkeypatch, capsys):
        monkeypatch.setattr(
            "ifg_guardian.core.execution_guard.socket.gethostname",
            lambda: "DS723plus",
        )
        enforce_mutating_live_orchestration(dry_run=True)
        captured = capsys.readouterr()
        assert DRY_RUN_WARNING_MESSAGE in captured.err
