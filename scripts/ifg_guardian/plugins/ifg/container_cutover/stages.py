from __future__ import annotations

from pathlib import Path

from ifg_guardian.core.preflight.engine import PreflightEngine
from ifg_guardian.core.preflight.gate import SafetyGate
from ifg_guardian.core.preflight.report import render_precheck_markdown
from ifg_guardian.core.workflow.context import WorkflowContext
from ifg_guardian.core.workflow.executors.context import DeployExecutorContext
from ifg_guardian.core.workflow.executors.ssh_executor import SSHExecutor
from ifg_guardian.core.workflow.intents import NoOpIntent
from ifg_guardian.core.workflow.mode import ExecutionMode
from ifg_guardian.core.workflow.results import StageExecutionResults
from ifg_guardian.core.workflow.stage import SkipReason, Stage, StagePlan, StageResult, StageStatus
from ifg_guardian.core.workflow.transaction import ArtifactRecord
from ifg_guardian.plugins.ifg.container_cutover.remote import (
    backup_script,
    cleanup_script,
    compose_config_gate_script,
    cutover_up_script,
    frontend_build_script,
    git_pull_script,
    legacy_containers_script,
    parse_legacy_containers,
    post_health_script,
    rollback_command_text,
    validate_compose_config,
)
from ifg_guardian.core.frontend_artifacts import parse_artifact_gate_output, remote_artifact_verify_script
from ifg_guardian.plugins.ifg.container_cutover.service import get_cutover_state
from ifg_guardian.reporting import default_report_path, write_report


def _ssh(ctx: WorkflowContext) -> SSHExecutor:
    deploy_ctx = ctx.data.get("deploy_executor_context")
    if not isinstance(deploy_ctx, DeployExecutorContext):
        deploy_ctx = DeployExecutorContext(
            remote_host=ctx.data.get("remote_host"),
            remote_path=ctx.data.get("remote_path"),
        )
        ctx.data["deploy_executor_context"] = deploy_ctx
    return SSHExecutor(root=ctx.root, deploy_context=deploy_ctx)


def _dry_run(ctx: WorkflowContext) -> bool:
    return ctx.mode in (ExecutionMode.DRY_RUN, ExecutionMode.PLAN)


class _CutoverStage(Stage):
    mutating = False

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        on_fail = "halt"
        return StagePlan(intents=[NoOpIntent(reason=self.id)], on_fail=on_fail)


class InitStage(_CutoverStage):
    id = "init"
    label = "Initialize container cutover"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        dry_run = _dry_run(ctx)
        assume_yes = bool(ctx.data.get("assume_yes"))
        if not dry_run and not assume_yes:
            return StageResult(status=StageStatus.FAIL, message="LIVE cutover requires --yes")

        state = get_cutover_state(ctx)
        state.dry_run = dry_run
        state.functional_confirmed = bool(ctx.data.get("confirm_functional"))
        cfg = _ssh(ctx).deploy_context.config()
        state.rollback_command = rollback_command_text(cfg)
        ctx.transaction.rollback_possible = True
        ctx.data.setdefault("output_format", "terminal")
        return StageResult(
            status=StageStatus.PASS,
            message="cutover dry-run initialized" if dry_run else "cutover LIVE initialized",
        )


class BackupStage(Stage):
    id = "backup"
    label = "SQL backup (mandatory)"
    mutating = True

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        return StagePlan(intents=[NoOpIntent(reason=self.id)], on_fail="halt")

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_cutover_state(ctx)
        ssh = _ssh(ctx)
        cfg = ssh.deploy_context.config()

        if _dry_run(ctx):
            state.backup_file = "backups/pre_ifg_project_DRYRUN.sql"
            return StageResult(status=StageStatus.PASS, message="[dry-run] SQL backup simulated")

        result = ssh.run_remote(backup_script(cfg), label="cutover_backup")
        if not result.ok:
            return StageResult(status=StageStatus.FAIL, message=f"backup failed: {result.error or result.output}")

        for line in result.output.splitlines():
            if line.startswith("backup_file="):
                state.backup_file = line.split("=", 1)[1].strip()
        if not state.backup_file:
            return StageResult(status=StageStatus.FAIL, message="backup file path not returned")

        ctx.transaction.recommended_actions.append(f"Backup: {state.backup_file}")
        return StageResult(status=StageStatus.PASS, message=f"backup OK: {state.backup_file}")


class GitPullStage(Stage):
    id = "git_pull"
    label = "git pull on DS723+"
    mutating = True

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        return StagePlan(intents=[NoOpIntent(reason=self.id)], on_fail="halt")

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_cutover_state(ctx)
        ssh = _ssh(ctx)
        cfg = ssh.deploy_context.config()

        if _dry_run(ctx):
            return StageResult(status=StageStatus.PASS, message="[dry-run] git pull simulated")

        result = ssh.run_remote(git_pull_script(cfg), label="cutover_git_pull")
        if not result.ok:
            return StageResult(status=StageStatus.FAIL, message=f"git pull failed: {result.error or result.output}")

        state.rollback_commit = result.output.splitlines()[-1] if result.output else ""
        return StageResult(status=StageStatus.PASS, message=f"git pull OK ({state.rollback_commit[:60]})")


class ComposeConfigGateStage(_CutoverStage):
    id = "compose_config_gate"
    label = "Compose config gate (mandatory)"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_cutover_state(ctx)
        ssh = _ssh(ctx)
        cfg = ssh.deploy_context.config()

        if _dry_run(ctx):
            state.compose_config_ok = True
            return StageResult(status=StageStatus.PASS, message="[dry-run] compose config gate simulated")

        result = ssh.run_remote(compose_config_gate_script(cfg), label="compose_config_gate")
        if not result.ok:
            return StageResult(status=StageStatus.FAIL, message=f"compose config failed: {result.error}")

        ok, msg = validate_compose_config(result.output)
        state.compose_config_ok = ok
        if not ok:
            return StageResult(status=StageStatus.FAIL, message=msg)
        return StageResult(status=StageStatus.PASS, message=msg)


class PreflightStage(_CutoverStage):
    id = "preflight"
    label = "Preflight engine and safety gate"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_cutover_state(ctx)
        engine = PreflightEngine()
        preflight_ctx = PreflightEngine.context_from_workflow(
            root=ctx.root,
            mode=ctx.mode,
            remote_host=ctx.data.get("remote_host"),
            remote_path=ctx.data.get("remote_path"),
            skip_remote=_dry_run(ctx),
        )
        report = engine.run(preflight_ctx)
        report.workflow_id = ctx.transaction.workflow_id
        decision = SafetyGate().evaluate(report)
        ctx.data["preflight_report"] = report
        ctx.data["deployment_decision"] = decision
        state.safety_gate = decision.status.value

        markdown = render_precheck_markdown(report, decision=decision, workflow_id=ctx.transaction.workflow_id)
        out = Path(ctx.data.get("precheck_report_path") or default_report_path("CUTOVER_PRECHECK"))
        write_report(out, markdown)
        ctx.data["precheck_report_file"] = str(out)
        ctx.transaction.artifacts.append(ArtifactRecord(type="precheck_report", path=str(out)))

        if not decision.is_go:
            return StageResult(
                status=StageStatus.FAIL,
                message=f"Safety Gate NO_GO ({len(decision.blocking_items)} blocking)",
            )
        warn = f", {len(decision.warnings)} warning(s)" if decision.warnings else ""
        return StageResult(status=StageStatus.PASS, message=f"Safety Gate GO{warn}")


class LegacyContainersStage(_CutoverStage):
    id = "legacy_containers"
    label = "Verify legacy docker-* preserved (rollback asset)"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        if _dry_run(ctx):
            return StageResult(status=StageStatus.PASS, message="[dry-run] legacy containers check simulated")

        ssh = _ssh(ctx)
        result = ssh.run_remote(legacy_containers_script(), label="legacy_containers")
        if not result.ok:
            return StageResult(status=StageStatus.FAIL, message=result.error or "legacy check failed")

        ok, msg = parse_legacy_containers(result.output)
        if not ok:
            return StageResult(status=StageStatus.FAIL, message=msg)
        return StageResult(status=StageStatus.PASS, message=msg)


class FrontendBuildStage(Stage):
    id = "frontend_build"
    label = "Build frontend on DS723+ (npm run build)"
    mutating = True

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        return StagePlan(intents=[NoOpIntent(reason=self.id)], on_fail="halt")

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_cutover_state(ctx)
        if _dry_run(ctx):
            return StageResult(status=StageStatus.PASS, message="[dry-run] frontend build simulated")

        ssh = _ssh(ctx)
        cfg = ssh.deploy_context.config()
        result = ssh.run_remote(frontend_build_script(cfg), label="cutover_frontend_build")
        if not result.ok:
            return StageResult(
                status=StageStatus.FAIL,
                message=f"frontend build failed: {result.error or result.output}",
            )
        return StageResult(status=StageStatus.PASS, message="frontend build OK on DS723+")


class FrontendArtifactGateStage(_CutoverStage):
    id = "frontend_artifact_gate"
    label = "Artifact Verification Gate (index.html + assets)"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_cutover_state(ctx)
        if _dry_run(ctx):
            state.frontend_artifacts_ok = True
            state.artifact_gate_status = "GO"
            return StageResult(status=StageStatus.PASS, message="[dry-run] artifact gate simulated GO")

        ssh = _ssh(ctx)
        cfg = ssh.deploy_context.config()
        result = ssh.run_remote(remote_artifact_verify_script(cfg.repo), label="frontend_artifact_gate")
        gate = parse_artifact_gate_output(result.output)
        state.artifact_gate_status = gate.status
        state.frontend_artifacts_ok = gate.is_go

        if not result.ok or not gate.is_go:
            return StageResult(
                status=StageStatus.FAIL,
                message=f"Artifact Verification Gate NO_GO — {gate.message}",
            )
        return StageResult(
            status=StageStatus.PASS,
            message=f"Artifact Verification Gate GO ({gate.js_count} JS bundle(s))",
        )


class CutoverUpStage(Stage):
    id = "cutover_up"
    label = "Start project ifg (compose up -d)"
    mutating = True

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        return StagePlan(intents=[NoOpIntent(reason=self.id)], on_fail="halt")

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_cutover_state(ctx)
        if state.safety_gate and state.safety_gate != "GO":
            return StageResult(status=StageStatus.FAIL, message="cutover blocked — Safety Gate not GO")
        if not _dry_run(ctx) and not state.frontend_artifacts_ok:
            return StageResult(
                status=StageStatus.FAIL,
                message="cutover blocked — Artifact Verification Gate not GO",
            )

        ssh = _ssh(ctx)
        cfg = ssh.deploy_context.config()

        if _dry_run(ctx):
            state.cutover_executed = False
            return StageResult(status=StageStatus.PASS, message="[dry-run] compose up -d simulated")

        result = ssh.run_remote(cutover_up_script(cfg), label="cutover_up")
        if not result.ok:
            return StageResult(status=StageStatus.FAIL, message=f"cutover up failed: {result.error or result.output}")

        state.cutover_executed = True
        return StageResult(status=StageStatus.PASS, message="project ifg started")


class PostHealthStage(_CutoverStage):
    id = "post_health"
    label = "Health, sanity SQL, worker logs"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_cutover_state(ctx)
        if _dry_run(ctx):
            state.health_ok = True
            return StageResult(status=StageStatus.PASS, message="[dry-run] post-health simulated")

        ssh = _ssh(ctx)
        cfg = ssh.deploy_context.config()
        result = ssh.run_remote(post_health_script(cfg), label="post_health")
        if not result.ok:
            return StageResult(status=StageStatus.FAIL, message=f"post-health failed: {result.error or result.output}")

        output = result.output
        if "accepting connections" not in output and "accepting connection" not in output:
            state.warnings.append("pg_isready not confirmed in output")
        if "docker_postgres_data" not in output:
            return StageResult(status=StageStatus.FAIL, message="volume docker_postgres_data not verified")
        if '"status":"ok"' not in output and '"status": "ok"' not in output:
            state.warnings.append("health JSON not confirmed — verify manually")

        state.health_ok = True
        return StageResult(status=StageStatus.PASS, message="post-health checks completed")


class GuardianVerifyStage(_CutoverStage):
    id = "guardian_verify"
    label = "Guardian deploy check (read-only)"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_cutover_state(ctx)
        if _dry_run(ctx):
            state.guardian_verify_ok = True
            return StageResult(status=StageStatus.PASS, message="[dry-run] guardian verify simulated")

        from ifg_guardian.modules.deploy import run_deploy_check

        code = run_deploy_check(
            remote_host=ctx.data.get("remote_host"),
            remote_path=str(ctx.data.get("remote_path", "")),
        )
        state.guardian_verify_ok = code == 0
        if code != 0:
            return StageResult(status=StageStatus.FAIL, message="Guardian deploy check failed")
        return StageResult(status=StageStatus.PASS, message="Guardian deploy check OK")


class FunctionalGateStage(_CutoverStage):
    id = "functional_gate"
    label = "Functional test attestation"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_cutover_state(ctx)
        if not state.functional_confirmed:
            state.warnings.append(
                "Functional tests not attested — run UI/KSeF checks, then re-run with --confirm-functional --cleanup"
            )
            ctx.transaction.recommended_actions.append(
                "Operator: complete functional checklist (login, invoices, KSeF), then "
                "guardian ifg cutover run --yes --confirm-functional --cleanup"
            )
            return StageResult(
                status=StageStatus.WARN,
                message="functional attestation missing (--confirm-functional)",
            )
        return StageResult(status=StageStatus.PASS, message="functional tests attested by operator")


class CleanupStage(Stage):
    id = "cleanup"
    label = "Remove legacy docker-* containers"
    mutating = True

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        return StagePlan(intents=[NoOpIntent(reason=self.id)], on_fail="halt")

    def should_skip(self, ctx: WorkflowContext) -> SkipReason | None:
        if not ctx.data.get("cleanup"):
            return SkipReason(message="cleanup not requested (--cleanup)")
        state = get_cutover_state(ctx)
        if not state.functional_confirmed:
            return SkipReason(message="cleanup requires --confirm-functional")
        if not state.health_ok:
            return SkipReason(message="cleanup blocked — health not OK")
        return None

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_cutover_state(ctx)
        if _dry_run(ctx):
            return StageResult(status=StageStatus.PASS, message="[dry-run] docker rm simulated")

        ssh = _ssh(ctx)
        result = ssh.run_remote(cleanup_script(), label="cutover_cleanup")
        if not result.ok:
            return StageResult(status=StageStatus.FAIL, message=f"cleanup failed: {result.error or result.output}")

        state.cleanup_executed = True
        return StageResult(status=StageStatus.PASS, message="legacy docker-* removed")


class SummaryStage(_CutoverStage):
    id = "summary"
    label = "Cutover summary report"

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        return StagePlan(intents=[NoOpIntent(reason=self.id)], on_fail="continue")

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        from ifg_guardian.plugins.ifg.container_cutover.report import render_markdown

        state = get_cutover_state(ctx)
        state.summary = {
            "mode": "DRY-RUN" if state.dry_run else "LIVE",
            "backup_file": state.backup_file,
            "compose_config_ok": state.compose_config_ok,
            "safety_gate": state.safety_gate,
            "artifact_gate": state.artifact_gate_status,
            "frontend_artifacts_ok": state.frontend_artifacts_ok,
            "cutover_executed": state.cutover_executed,
            "health_ok": state.health_ok,
            "guardian_verify_ok": state.guardian_verify_ok,
            "functional_confirmed": state.functional_confirmed,
            "cleanup_executed": state.cleanup_executed,
        }
        ctx.transaction.cutover_run = state.to_dict()
        ctx.transaction.warnings.extend(state.warnings)

        markdown = render_markdown(state, transaction=ctx.transaction)
        report_path = ctx.data.get("report_path")
        out = Path(report_path) if report_path else default_report_path("IFG_CONTAINER_CUTOVER")
        write_report(out, markdown)
        ctx.data["report_file"] = str(out)
        ctx.transaction.artifacts.append(ArtifactRecord(type="cutover_report", path=str(out)))
        ctx.transaction.recommended_actions.append(f"Rollback: {state.rollback_command}")
        return StageResult(status=StageStatus.PASS, message="summary complete")
