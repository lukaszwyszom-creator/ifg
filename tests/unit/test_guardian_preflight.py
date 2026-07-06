"""Unit tests for Guardian Preflight Engine and Safety Gate."""
from __future__ import annotations

import sys
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
