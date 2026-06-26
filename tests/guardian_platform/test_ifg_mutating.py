"""IFG mutating command guards and infra tests (M3)."""
from __future__ import annotations

from guardian_platform.core.registry.commands import CommandSpec
from guardian_platform.core.runtime.guards import MutatingCommandBlocked, ensure_mutating_allowed
from guardian_platform.profiles.ifg.deploy.models import DeployRunState, DeployStep, StepStatus
from guardian_platform.profiles.ifg.deploy.report import render_terminal
from guardian_platform.profiles.ifg.infra.exec import run_local, run_remote
from guardian_platform.profiles.ifg.recover.models import RecoverState
from guardian_platform.profiles.ifg.recover.report import render_terminal as recover_terminal
from guardian_platform.core.workflow.context import WorkflowTransaction
from guardian_platform.core.runtime.mode import ExecutionMode
import pytest


def _noop(ctx):
    return 0


class TestMutatingGuards:
    def test_deploy_run_is_mutating(self, platform_runtime):
        spec = platform_runtime.commands.resolve_namespaced("ifg", ["deploy", "run"])
        assert spec.mutating is True

    def test_deploy_check_not_mutating(self, platform_runtime):
        spec = platform_runtime.commands.resolve_namespaced("ifg", ["deploy", "check"])
        assert spec.mutating is False

    def test_prod_recover_mutating(self, platform_runtime):
        spec = platform_runtime.commands.resolve_namespaced("ifg", ["prod", "recover"])
        assert spec.mutating is True

    def test_prod_health_not_mutating(self, platform_runtime):
        spec = platform_runtime.commands.resolve_namespaced("ifg", ["prod", "health"])
        assert spec.mutating is False

    def test_deploy_run_supports_dry_run(self, platform_runtime):
        spec = platform_runtime.commands.resolve_namespaced("ifg", ["deploy", "run"])
        assert spec.supports_dry_run is True

    def test_guard_blocks_live(self):
        spec = CommandSpec("ifg", ("deploy", "run"), _noop, mutating=True)
        with pytest.raises(MutatingCommandBlocked):
            ensure_mutating_allowed(spec=spec, assume_yes=False, dry_run=False)

    def test_guard_allows_dry_run(self):
        spec = CommandSpec("ifg", ("deploy", "run"), _noop, mutating=True)
        ensure_mutating_allowed(spec=spec, assume_yes=False, dry_run=True)

    def test_guard_allows_yes(self):
        spec = CommandSpec("ifg", ("deploy", "run"), _noop, mutating=True)
        ensure_mutating_allowed(spec=spec, assume_yes=True, dry_run=False)


class TestDeployReports:
    def test_terminal_blocked_status(self):
        s = DeployRunState(blockers=["dirty"])
        tx = WorkflowTransaction("w", "ifg.deploy.run", "ifg", ExecutionMode.DRY_RUN)
        assert "BLOCKED" in render_terminal(s, transaction=tx)

    def test_terminal_dry_run_complete(self):
        s = DeployRunState(dry_run=True)
        tx = WorkflowTransaction("w", "ifg.deploy.run", "ifg", ExecutionMode.DRY_RUN)
        assert "DRY-RUN COMPLETE" in render_terminal(s, transaction=tx)

    def test_rollback_available_flag(self):
        s = DeployRunState(rollback_available=True)
        assert s.rollback_available is True

    def test_step_status_simulated(self):
        step = DeployStep(order=1, action="x", command="y", status=StepStatus.SIMULATED)
        assert step.status == StepStatus.SIMULATED


class TestRecoverReports:
    def test_recover_terminal_dry_run(self):
        s = RecoverState(dry_run=True)
        tx = WorkflowTransaction("w", "ifg.prod.recover", "ifg", ExecutionMode.DRY_RUN)
        assert "DRY-RUN COMPLETE" in recover_terminal(s, transaction=tx)

    def test_recover_terminal_failed(self):
        s = RecoverState(aborted=True, health_ok=False)
        tx = WorkflowTransaction("w", "ifg.prod.recover", "ifg", ExecutionMode.LIVE)
        assert "FAILED" in recover_terminal(s, transaction=tx)


class TestRemoteExec:
    def test_run_remote_dry_run(self):
        r = run_remote("host", "echo hi", remote_path="/p", dry_run=True)
        assert r.simulated is True

    def test_run_local_non_mutating_dry_run(self):
        r = run_local("echo test", dry_run=True, mutating=False)
        assert r.simulated is True


class TestWorkflowRegistration:
    def test_both_mutating_workflows(self, platform_runtime):
        ids = platform_runtime.workflows.list_ids()
        assert "ifg.deploy.run" in ids
        assert "ifg.prod.recover" in ids

    def test_ten_ifg_commands(self, platform_runtime):
        ifg = [c for c in platform_runtime.commands.list_commands() if c.profile == "ifg"]
        assert len(ifg) == 10

    def test_two_mutating_commands(self, platform_runtime):
        mutating = [
            c for c in platform_runtime.commands.list_commands()
            if c.profile == "ifg" and c.mutating
        ]
        assert len(mutating) == 3

    def test_ifg_version_m3(self, platform_runtime):
        info = next(p for p in platform_runtime.profiles.list_profiles() if p.profile_id == "ifg")
        assert info.version.startswith("0.5")
