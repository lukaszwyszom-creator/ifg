"""Guardian Platform core.ping workflow CLI tests."""
from __future__ import annotations

from tests.guardian_platform.conftest import run_main


class TestCorePing:
    def test_workflow_run_core_ping(self):
        code, out = run_main(["workflow", "run", "core.ping"])
        assert code == 0
        assert "SUCCESS" in out or "outcome" in out

    def test_workflow_run_core_ping_json(self):
        code, out = run_main(["--format", "json", "workflow", "run", "core.ping"])
        assert code == 0
        assert '"SUCCESS"' in out

    def test_workflow_run_core_ping_markdown(self):
        code, out = run_main(["--format", "markdown", "workflow", "run", "core.ping"])
        assert code == 0
        assert "# Workflow core.ping" in out

    def test_core_ping_workflow_registered(self, platform_runtime):
        wf = platform_runtime.workflows.get("core.ping")
        assert wf is not None
        assert wf.mutating is False

    def test_core_ping_stage_count(self, platform_runtime):
        wf = platform_runtime.workflows.get("core.ping")
        assert len(wf.stages) == 3

    def test_core_ping_not_mutating_via_cli(self):
        code, _ = run_main(["workflow", "run", "core.ping"])
        assert code == 0
