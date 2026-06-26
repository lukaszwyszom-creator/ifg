"""Unit tests for Guardian repo audit workflow (Sprint 3)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian.core.line_endings import Confidence  # noqa: E402
from ifg_guardian.core.plugins.bootstrap import create_runtime  # noqa: E402
from ifg_guardian.core.repo_audit.classifier import classify_line_endings  # noqa: E402
from ifg_guardian.core.repo_audit.models import ClassifiedFile, RepoAuditState  # noqa: E402
from ifg_guardian.core.repo_audit.report import (  # noqa: E402
    audit_from_transaction,
    render_json,
    render_markdown,
    render_terminal,
)
from ifg_guardian.core.repo_audit.service import aggregate_risk  # noqa: E402
from ifg_guardian.core.risk import FileCategory, RiskLevel  # noqa: E402
from ifg_guardian.core.workflow.mode import ExecutionMode  # noqa: E402
from ifg_guardian.core.workflow.state import WorkflowState  # noqa: E402
from ifg_guardian.core.workflow.transaction import WorkflowTransaction  # noqa: E402
from ifg_guardian.modules.repo_audit import audit_from_context, execute_repo_audit  # noqa: E402


def _run_git(args: list[str], *, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    _run_git(["init"], cwd=tmp_path)
    _run_git(["config", "user.email", "audit@test"], cwd=tmp_path)
    _run_git(["config", "user.name", "Audit Test"], cwd=tmp_path)
    (tmp_path / ".gitignore").write_text("*.pyc\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# test\n", encoding="utf-8")
    _run_git(["add", "."], cwd=tmp_path)
    _run_git(["commit", "-m", "init"], cwd=tmp_path)
    return tmp_path


def _patch_root(monkeypatch: pytest.MonkeyPatch, git_repo: Path) -> None:
    import ifg_guardian.config as config_mod
    import ifg_guardian.core.git as git_mod
    import ifg_guardian.core.line_endings as le_mod
    import ifg_guardian.modules.frontend as frontend_mod

    monkeypatch.setattr(config_mod, "ROOT", git_repo)
    monkeypatch.setattr(git_mod, "ROOT", git_repo)
    monkeypatch.setattr(le_mod, "ROOT", git_repo)
    monkeypatch.setattr(frontend_mod, "ROOT", git_repo)


class TestWorkflowRegistry:
    def test_core_repo_audit_registered(self):
        runtime = create_runtime()
        try:
            wf = runtime.resolve_workflow("core.repo.audit")
            assert wf is not None
            assert wf.plugin == "core"
            assert [s.id for s in wf.stages] == [
                "init",
                "collect_git_status",
                "collect_repository_metadata",
                "classify_files",
                "line_ending_analysis",
                "risk_analysis",
                "recommended_actions",
                "report",
                "summary",
            ]
        finally:
            runtime.shutdown()


class TestRepoAuditWorkflow:
    def test_workflow_success_clean_repo(self, git_repo: Path, monkeypatch: pytest.MonkeyPatch):
        _patch_root(monkeypatch, git_repo)
        ctx = execute_repo_audit(output_format="none", root=git_repo)
        assert ctx.state_machine.state == WorkflowState.SUCCESS
        assert ctx.transaction.audit
        assert ctx.transaction.recommended_actions
        assert ctx.transaction.duration_ms >= 0

    def test_dry_run_skips_fetch(self, git_repo: Path, monkeypatch: pytest.MonkeyPatch):
        _patch_root(monkeypatch, git_repo)
        ctx = execute_repo_audit(do_fetch=True, dry_run=True, output_format="none", root=git_repo)
        assert ctx.state_machine.state == WorkflowState.SUCCESS
        fetch_stage = next(r for r in ctx.transaction.stages if r.id == "collect_git_status")
        assert fetch_stage.status == "pass"


class TestRiskAggregation:
    def test_branch_mismatch_raises_overall_risk(self):
        audit = RepoAuditState(branch="feature", files=[])
        aggregate_risk(audit)
        assert audit.overall_risk == RiskLevel.HIGH

    def test_substantive_backend_high_risk(self):
        audit = RepoAuditState(
            branch="production",
            files=[
                ClassifiedFile(
                    path="app/api/deps.py",
                    status="M",
                    category=FileCategory.SUBSTANTIVE,
                    risk=RiskLevel.HIGH,
                )
            ],
        )
        with patch(
            "ifg_guardian.core.repo_audit.service.check_frontend_worktree_requires_build",
            return_value=(True, ""),
        ):
            aggregate_risk(audit)
        assert audit.overall_risk == RiskLevel.HIGH


class TestCRLFClassification:
    def test_deps_py_regression_not_crlf_only(self):
        crlf = b"import os\r\n\r\n"
        with (
            patch("ifg_guardian.core.line_endings._read_head", return_value=crlf),
            patch("ifg_guardian.core.line_endings._read_index", return_value=crlf),
            patch("ifg_guardian.core.line_endings._read_worktree", return_value=crlf),
            patch("ifg_guardian.core.line_endings._run_git") as mock_git,
        ):
            mock_git.return_value = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            classified, reasons = classify_line_endings("app/api/deps.py")

        assert classified is not None
        assert classified.category == FileCategory.UNKNOWN_LINE_ENDINGS
        assert classified.category != FileCategory.CRLF_ONLY
        assert classified.confidence == Confidence.LOW
        assert reasons
        assert reasons[0].decision == "unknown_line_endings"
        assert "app/api/deps.py" in reasons[0].because

    def test_crlf_only_has_high_confidence_reason(self):
        with (
            patch("ifg_guardian.core.line_endings._read_head", return_value=b"line\n"),
            patch("ifg_guardian.core.line_endings._read_index", return_value=b"line\n"),
            patch("ifg_guardian.core.line_endings._read_worktree", return_value=b"line\r\n"),
            patch("ifg_guardian.core.line_endings._run_git") as mock_git,
        ):
            mock_git.return_value = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            classified, reasons = classify_line_endings("sample.py")

        assert classified is not None
        assert classified.category == FileCategory.CRLF_ONLY
        assert reasons[0].confidence == Confidence.HIGH.value


class TestWorkflowTransactionAudit:
    def test_audit_persisted_in_transaction(self, git_repo: Path, monkeypatch: pytest.MonkeyPatch):
        _patch_root(monkeypatch, git_repo)
        ctx = execute_repo_audit(output_format="none", root=git_repo)
        payload = ctx.transaction.to_dict()

        assert payload["audit"]
        assert "overall_risk" in payload["audit"]
        assert "recommended_actions" in payload["audit"]
        assert payload["lifecycle"]["duration_ms"] >= 0

        restored = audit_from_transaction(ctx.transaction)
        assert restored.branch == audit_from_context(ctx).branch


class TestReportsFromTransaction:
    def _sample_audit(self) -> tuple[RepoAuditState, WorkflowTransaction]:
        audit = RepoAuditState(
            branch="production",
            head="abc123def456",
            dirty=True,
            files=[
                ClassifiedFile(
                    path="app/api/deps.py",
                    status="M",
                    category=FileCategory.UNKNOWN_LINE_ENDINGS,
                    risk=RiskLevel.MEDIUM,
                    confidence=Confidence.LOW,
                    verification=["git diff --ignore-cr-at-eol: clean"],
                )
            ],
            overall_risk=RiskLevel.MEDIUM,
            recommended_actions=["Review unknown line endings"],
        )
        tx = WorkflowTransaction(
            workflow_id="2026-05-22T120000Z_core_repo_audit",
            workflow_type="core.repo.audit",
            plugin="core",
            execution_mode=ExecutionMode.LIVE,
        )
        tx.mark_started()
        tx.mark_ended(state=WorkflowState.SUCCESS)
        tx.audit = audit.to_dict()
        tx.recommended_actions = list(audit.recommended_actions)
        return audit, tx

    def test_markdown_report(self):
        audit, tx = self._sample_audit()
        md = render_markdown(audit, transaction=tx)
        assert "# IFG Guardian — Repo Audit" in md
        assert "app/api/deps.py" in md
        assert "unknown_line_endings" in md
        assert "Workflow ID" in md
        assert "RECOMMENDED ACTION" in md

    def test_json_report(self):
        audit, tx = self._sample_audit()
        data = json.loads(render_json(audit, transaction=tx))
        assert data["schema"] == "repo_audit_report_v1"
        assert data["workflow"]["workflow_type"] == "core.repo.audit"
        assert data["audit"]["files"][0]["category"] == "unknown_line_endings"

    def test_terminal_report(self):
        audit, tx = self._sample_audit()
        text = render_terminal(audit, transaction=tx)
        assert "IFG Guardian — Repo Audit" in text
        assert "Overall risk: MEDIUM" in text
        assert "RECOMMENDED ACTION" in text
        assert "Status: WARNING" in text


class TestLineEndingStageIntegration:
    def test_modified_file_gets_eol_classification_in_workflow(self, git_repo: Path, monkeypatch: pytest.MonkeyPatch):
        deps = git_repo / "app" / "api"
        deps.mkdir(parents=True)
        (deps / "deps.py").write_bytes(b"import os\r\n")
        _run_git(["add", "app/api/deps.py"], cwd=git_repo)
        _run_git(["commit", "-m", "add deps"], cwd=git_repo)
        (deps / "deps.py").write_bytes(b"import os\r\n\r\n")

        _patch_root(monkeypatch, git_repo)
        ctx = execute_repo_audit(output_format="none", root=git_repo)
        audit = audit_from_context(ctx)
        deps_files = [f for f in audit.files if f.path == "app/api/deps.py"]
        assert deps_files
        assert deps_files[0].category != FileCategory.CRLF_ONLY
