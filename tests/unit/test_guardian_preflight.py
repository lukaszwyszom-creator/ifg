"""Unit tests for Guardian Preflight Engine and Safety Gate."""
from __future__ import annotations

import sys
import subprocess
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian.core.preflight.engine import PreflightEngine  # noqa: E402
from ifg_guardian.core.preflight.gate import SafetyGate  # noqa: E402
from ifg_guardian.core.preflight.models import (  # noqa: E402
    DeploymentDecision,
    DeploymentDecisionStatus,
    PreflightCheckResult,
    PreflightContext,
    PreflightReport,
    PreflightStatus,
)
from ifg_guardian.core.preflight.report import render_precheck_markdown  # noqa: E402
from ifg_guardian.core.workflow.mode import ExecutionMode  # noqa: E402


class TestSafetyGate:
    def test_go_when_all_pass(self):
        report = PreflightReport()
        report.add(PreflightCheckResult("a", "A", PreflightStatus.PASS, "ok"))
        decision = SafetyGate().evaluate(report)
        assert decision.status == DeploymentDecisionStatus.GO
        assert not decision.blocking_items

    def test_no_go_on_fail(self):
        report = PreflightReport()
        report.add(PreflightCheckResult("a", "A", PreflightStatus.FAIL, "bad"))
        decision = SafetyGate().evaluate(report)
        assert decision.status == DeploymentDecisionStatus.NO_GO
        assert len(decision.blocking_items) == 1

    def test_go_with_warnings(self):
        report = PreflightReport()
        report.add(PreflightCheckResult("a", "A", PreflightStatus.PASS, "ok"))
        report.add(PreflightCheckResult("b", "B", PreflightStatus.WARNING, "warn"))
        decision = SafetyGate().evaluate(report)
        assert decision.status == DeploymentDecisionStatus.GO
        assert len(decision.warnings) == 1


class TestPreflightEngine:
    def test_local_checks_on_repo(self, tmp_path: Path):
        compose_dir = tmp_path / "docker"
        compose_dir.mkdir()
        (compose_dir / "docker-compose.prod.yml").write_text("services:\n  api:\n    image: test\n", encoding="utf-8")
        (tmp_path / ".env.production").write_text("POSTGRES_DB=test\n", encoding="utf-8")

        ctx = PreflightContext(
            root=tmp_path,
            mode=ExecutionMode.DRY_RUN,
            compose_file="docker/docker-compose.prod.yml",
            env_file=".env.production",
            skip_remote=True,
        )
        report = PreflightEngine().run(ctx)
        assert report.passed >= 3
        assert report.failures == 0

    def test_compose_missing_fails(self, tmp_path: Path):
        ctx = PreflightContext(root=tmp_path, mode=ExecutionMode.DRY_RUN, skip_remote=True)
        report = PreflightEngine().run(ctx)
        decision = SafetyGate().evaluate(report)
        assert decision.status == DeploymentDecisionStatus.NO_GO
        assert any("Compose file" in b for b in decision.blocking_items)


class TestPrecheckReport:
    def test_renders_markdown_table(self):
        report = PreflightReport(mode="DRY_RUN")
        report.add(PreflightCheckResult("x", "Test", PreflightStatus.PASS, "ok", duration_ms=5))
        decision = DeploymentDecision(status=DeploymentDecisionStatus.GO)
        md = render_precheck_markdown(report, decision=decision, workflow_id="wf-1")
        assert "PRECHECK_REPORT" in md
        assert "| PASS |" in md
        assert "**GO**" in md


class TestGitCleanDirtyTree:
    def test_dirty_tree_fails_on_live_without_override(self, tmp_path: Path):
        from ifg_guardian.core.preflight.checks import check_git_clean, DIRTY_TREE_BLOCK_MESSAGE

        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@test"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, check=True, capture_output=True)
        (tmp_path / "dirty.txt").write_text("x", encoding="utf-8")
        subprocess.run(["git", "add", "dirty.txt"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)
        (tmp_path / "dirty.txt").write_text("changed", encoding="utf-8")

        ctx = PreflightContext(root=tmp_path, mode=ExecutionMode.LIVE, skip_remote=True)
        result = check_git_clean(ctx)
        assert result.status == PreflightStatus.FAIL
        assert DIRTY_TREE_BLOCK_MESSAGE in result.description

        decision = SafetyGate().evaluate(PreflightReport(checks=[result]))
        assert decision.status == DeploymentDecisionStatus.NO_GO

    def test_dirty_tree_warns_on_live_with_override(self, tmp_path: Path):
        from ifg_guardian.core.preflight.checks import check_git_clean, DIRTY_TREE_OVERRIDE_WARNING

        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@test"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, check=True, capture_output=True)
        (tmp_path / "dirty.txt").write_text("x", encoding="utf-8")
        subprocess.run(["git", "add", "dirty.txt"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)
        (tmp_path / "dirty.txt").write_text("changed", encoding="utf-8")

        ctx = PreflightContext(
            root=tmp_path,
            mode=ExecutionMode.LIVE,
            skip_remote=True,
            allow_dirty_build=True,
        )
        result = check_git_clean(ctx)
        assert result.status == PreflightStatus.WARNING
        assert DIRTY_TREE_OVERRIDE_WARNING in result.description
