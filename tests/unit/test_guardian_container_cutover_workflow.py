"""Unit tests for IFG container cutover workflow."""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian.core.plugins.bootstrap import create_runtime  # noqa: E402
from ifg_guardian.core.workflow.mode import ExecutionMode  # noqa: E402
from ifg_guardian.modules.ifg_container_cutover import execute_ifg_container_cutover  # noqa: E402
from ifg_guardian.plugins.ifg.container_cutover.remote import validate_compose_config  # noqa: E402


class TestCutoverWorkflowRegistry:
    def test_registered(self):
        runtime = create_runtime()
        try:
            wf = runtime.resolve_workflow("ifg.container.cutover")
            assert wf is not None
            assert wf.mutating is True
            assert wf.requires_yes is True
            assert len(wf.stages) == 12
        finally:
            runtime.shutdown()


class TestComposeConfigGate:
    def test_valid_config(self):
        text = """
name: ifg
networks:
  ifg_prod:
    name: docker_ifg_prod
    external: true
volumes:
  postgres_data:
    name: docker_postgres_data
    external: true
"""
        ok, msg = validate_compose_config(text)
        assert ok
        assert "PASS" in msg

    def test_rejects_ifg_postgres_data(self):
        text = "name: ifg\nifg_postgres_data\n"
        ok, _ = validate_compose_config(text)
        assert not ok


class TestCutoverDryRun:
    def test_dry_run_completes(self):
        ctx = execute_ifg_container_cutover(dry_run=True)
        assert ctx.transaction.outcome == "SUCCESS"
