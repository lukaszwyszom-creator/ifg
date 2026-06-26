"""Guardian Platform CLI integration tests."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from tests.guardian_platform.conftest import run_main


class TestCLI:
    def test_help_returns_zero(self):
        code, out = run_main([])
        assert code == 0
        assert "Guardian Platform" in out

    def test_version_flag(self):
        code, out = run_main(["--version"])
        assert code == 0
        assert "Guardian Platform" in out

    def test_plugin_list(self):
        code, out = run_main(["plugin", "list"])
        assert code == 0
        assert "ifg" in out
        assert "psag" in out

    def test_workflow_list_terminal(self):
        code, out = run_main(["workflow", "list"])
        assert code == 0
        assert "core.ping" in out

    def test_workflow_list_json(self):
        code, out = run_main(["--format", "json", "workflow", "list"])
        assert code == 0
        assert '"core.ping"' in out

    def test_repo_status(self, repo_root):
        code, out = run_main(["repo", "status"])
        assert code == 0
        assert "branch" in out.lower() or "Repository Status" in out

    def test_repo_audit_generic(self, repo_root):
        code, out = run_main(["repo", "audit"])
        assert code == 0
        assert "Repository Audit" in out or "modified_files" in out

    def test_psag_ping(self):
        code, out = run_main(["psag", "ping"])
        assert code == 0
        assert "psag scaffold active" in out

    def test_ifg_ping(self):
        code, out = run_main(["ifg", "ping"])
        assert code == 0
        assert "ifg profile active (M3 mutating)" in out

    def test_unknown_command(self):
        code, out = run_main(["does", "not", "exist"])
        assert code == 2
        assert "Unknown command" in out

    def test_mutating_blocked_without_yes(self):
        code, out = run_main(["platform", "mutate-test"])
        assert code == 2
        assert "requires --yes" in out

    def test_mutating_allowed_with_yes(self):
        code, out = run_main(["--yes", "platform", "mutate-test"])
        assert code == 0
        assert "mutating platform self-test executed" in out

    def test_mutating_dry_run(self):
        code, out = run_main(["--dry-run", "platform", "mutate-test"])
        assert code == 0
        assert "dry-run" in out

    def test_platform_doctor(self):
        code, out = run_main(["platform", "doctor"])
        assert "python:" in out

    def test_workflow_run_missing_id(self):
        code, out = run_main(["workflow", "run"])
        assert code == 2
        assert "Usage" in out

    def test_workflow_run_unknown(self):
        code, out = run_main(["workflow", "run", "unknown.workflow"])
        assert code == 1
        assert "Unknown workflow" in out

    @patch("guardian_platform.profiles.ifg.commands.doctor.run_ifg_doctor", return_value=0)
    def test_ifg_doctor_cli(self, mock_doctor):
        code, _ = run_main(["ifg", "doctor"])
        assert code == 0
        mock_doctor.assert_called_once()

    def test_repo_status_markdown(self):
        code, out = run_main(["--format", "markdown", "repo", "status"])
        assert code == 0
        assert "#" in out

    def test_resolve_ifg_deploy_check_registered(self, platform_runtime):
        spec = platform_runtime.commands.resolve_namespaced("ifg", ["deploy", "check"])
        assert spec is not None
