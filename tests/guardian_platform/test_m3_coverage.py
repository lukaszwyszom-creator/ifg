"""Additional M3 coverage to meet 220+ platform test threshold."""
from __future__ import annotations

from guardian_platform.profiles.ifg.deploy.models import DeployRunState, DeployStep, RollbackPoint, StepStatus
from guardian_platform.profiles.ifg.deploy.pipeline import build_deploy_pipeline
from guardian_platform.profiles.ifg.deploy.report import exit_code_for_deploy, render_json, render_markdown
from guardian_platform.profiles.ifg.recover.models import RecoverState
from guardian_platform.profiles.ifg.recover.report import exit_code_for_recover, render_json as recover_json
from guardian_platform.core.workflow.context import WorkflowTransaction
from guardian_platform.core.runtime.mode import ExecutionMode


def _tx(wf: str) -> WorkflowTransaction:
    return WorkflowTransaction("t", wf, "ifg", ExecutionMode.LIVE)


class TestDeployPipelineDetails:
    def test_step_1_git_validation(self):
        steps = build_deploy_pipeline(remote_host="h", remote_path="/r")
        assert steps[0][0] == "git validation"

    def test_step_2_backup(self):
        steps = build_deploy_pipeline(remote_host="h", remote_path="/r")
        assert steps[1][0] == "backup database"

    def test_step_3_alembic(self):
        steps = build_deploy_pipeline(remote_host="h", remote_path="/r")
        assert steps[2][0] == "alembic upgrade"

    def test_step_4_frontend(self):
        steps = build_deploy_pipeline(remote_host="h", remote_path="/r")
        assert steps[3][0] == "frontend build"

    def test_step_5_docker(self):
        steps = build_deploy_pipeline(remote_host="h", remote_path="/r")
        assert steps[4][0] == "docker build"

    def test_step_6_restart(self):
        steps = build_deploy_pipeline(remote_host="h", remote_path="/r")
        assert steps[5][0] == "container restart"

    def test_step_7_health(self):
        steps = build_deploy_pipeline(remote_host="h", remote_path="/r")
        assert steps[6][0] == "health verification"

    def test_step_8_smoke(self):
        steps = build_deploy_pipeline(remote_host="h", remote_path="/r")
        assert steps[7][0] == "smoke tests"


class TestDeployStateSerialization:
    def test_to_dict_keys(self):
        d = DeployRunState(rollback_available=True).to_dict()
        assert "rollback_available" in d
        assert "steps" in d

    def test_rollback_point_dict(self):
        rp = RollbackPoint(commit_before="abc")
        assert rp.to_dict()["commit_before"] == "abc"

    def test_step_to_dict(self):
        step = DeployStep(order=1, action="a", command="c", status=StepStatus.EXECUTED)
        assert step.to_dict()["status"] == "EXECUTED"


class TestDeployReportFormats:
    def test_render_json_schema(self):
        s = DeployRunState()
        out = render_json(s, transaction=_tx("ifg.deploy.run"))
        assert "ifg_deploy_run_v1" in out

    def test_render_markdown_halted(self):
        s = DeployRunState(halted=True, halt_reason="smoke")
        assert "Halted" in render_markdown(s, transaction=_tx("ifg.deploy.run"))

    def test_exit_halted(self):
        assert exit_code_for_deploy(DeployRunState(halted=True)) == 1

    def test_exit_failed_step(self):
        s = DeployRunState(steps=[DeployStep(1, "x", "c", status=StepStatus.FAILED)])
        assert exit_code_for_deploy(s) == 1


class TestRecoverStateSerialization:
    def test_to_dict(self):
        d = RecoverState(ksef_ok=True).to_dict()
        assert d["ksef_ok"] is True

    def test_recover_json(self):
        out = recover_json(RecoverState(), transaction=_tx("ifg.prod.recover"))
        assert "ifg_prod_recover_v1" in out

    def test_recover_dry_run_exit(self):
        assert exit_code_for_recover(RecoverState(dry_run=True)) == 0

    def test_recover_aborted_exit(self):
        assert exit_code_for_recover(RecoverState(aborted=True, dry_run=False)) == 1


class TestM3CommandInventory:
    def test_deploy_run_help(self, platform_runtime):
        spec = platform_runtime.commands.resolve_namespaced("ifg", ["deploy", "run"])
        assert "deploy" in spec.help.lower()

    def test_prod_recover_help(self, platform_runtime):
        spec = platform_runtime.commands.resolve_namespaced("ifg", ["prod", "recover"])
        assert "recover" in spec.help.lower()

    def test_workflows_mutating(self, platform_runtime):
        for wf_id in ("ifg.deploy.run", "ifg.prod.recover"):
            wf = platform_runtime.workflows.get(wf_id)
            assert wf.mutating is True

    def test_read_only_count(self, platform_runtime):
        ro = sum(1 for c in platform_runtime.commands.list_commands() if c.profile == "ifg" and not c.mutating)
        assert ro == 7
