from __future__ import annotations

import io
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

from ifg_guardian.config import DEFAULT_REMOTE_PATH, ROOT
from ifg_guardian.core.workflow.context import WorkflowContext
from ifg_guardian.core.workflow.intents import NoOpIntent
from ifg_guardian.core.workflow.results import StageExecutionResults
from ifg_guardian.core.workflow.stage import Stage, StagePlan, StageResult, StageStatus
from ifg_guardian.core.workflow.transaction import ArtifactRecord
from ifg_guardian.modules.deploy import run_deploy_check
from ifg_guardian.plugins.ifg.release_evaluate.models import ReleaseEvaluateState
from ifg_guardian.plugins.ifg.release_evaluate.report import render_json, render_markdown
from ifg_guardian.plugins.ifg.release_evaluate.classification import finalize_classification, is_local_environment_error
from ifg_guardian.plugins.ifg.release_evaluate.policy_engine import apply_policy_engine, load_policy_config
from ifg_guardian.plugins.ifg.release_evaluate.service import (
    aggregate_release_score,
    detect_impacts,
    get_release_evaluate_state,
    score_from_doctor,
)
from ifg_guardian.plugins.ifg.release_plan.service import get_doctor_dependency
from ifg_guardian.reporting import default_report_path, write_report


class _EvaluateStage(Stage):
    mutating = False

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        return StagePlan(intents=[NoOpIntent(reason=self.id)], on_fail="continue")


class InitStage(_EvaluateStage):
    id = "init"
    label = "Initialize release engine evaluation"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        ctx.data["release_evaluate"] = ReleaseEvaluateState()
        ctx.data.setdefault("output_format", "terminal")
        ctx.data.setdefault("remote_path", DEFAULT_REMOTE_PATH)
        return StageResult(status=StageStatus.PASS, message="release engine initialized")


class DoctorDependencyStage(_EvaluateStage):
    id = "doctor_dependency"
    label = "Consume doctor dependency"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_release_evaluate_state(ctx)
        doctor = get_doctor_dependency(ctx)
        state.doctor_overall_status = doctor.overall_status.value
        positives = [
            f"[{c.group}] {c.name}: {c.message}"
            for c in doctor.checks
            if c.status.value == "PASS"
        ]
        state.positives.extend(positives[:12])
        return StageResult(
            status=StageStatus.PASS,
            message=f"doctor consumed: {doctor.overall_status.value}",
        )


class GitChangesStage(_EvaluateStage):
    id = "git_changes"
    label = "Collect changed files and impact"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_release_evaluate_state(ctx)
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        changed_files: list[str] = []
        entries: list[dict[str, str]] = []
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                if not line.strip():
                    continue
                code = line[:2]
                path = line[3:].strip()
                if path:
                    changed_files.append(path)
                    entries.append({"code": code, "path": path})
        state.changed_files = changed_files
        state.git_status_entries = entries
        state.impact = detect_impacts(changed_files)
        return StageResult(
            status=StageStatus.PASS,
            message=f"changed files: {len(changed_files)}",
        )


class DeployCheckStage(_EvaluateStage):
    id = "deploy_check"
    label = "Run deploy check (read-only)"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_release_evaluate_state(ctx)
        remote_host = ctx.data.get("remote_host")
        remote_path = ctx.data.get("remote_path", DEFAULT_REMOTE_PATH)
        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = run_deploy_check(remote_host=remote_host, remote_path=remote_path)
        state.deploy_check_exit_code = exit_code
        if exit_code == 0:
            state.positives.append("Deploy check: production alignment confirmed.")
            return StageResult(status=StageStatus.PASS, message="deploy check passed")
        return StageResult(status=StageStatus.WARN, message="deploy check reported warnings")


class TestDiscoveryStage(_EvaluateStage):
    id = "test_discovery"
    label = "Run test discovery"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_release_evaluate_state(ctx)
        cmd = [sys.executable, "-m", "pytest", "--collect-only", "tests/unit", "-q"]
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
        state.test_discovery_ok = proc.returncode == 0
        output = (proc.stderr or proc.stdout or "").strip()
        state.test_discovery_error = output.splitlines()[-1] if output else ""
        if state.test_discovery_ok:
            state.positives.append("Test discovery passed (tests/unit).")
            return StageResult(status=StageStatus.PASS, message="test discovery passed")
        if is_local_environment_error(output):
            state.test_discovery_local_env = True
            return StageResult(
                status=StageStatus.WARN,
                message="test discovery skipped: local environment limitation",
            )
        return StageResult(status=StageStatus.WARN, message="test discovery warning")


class DecisionStage(_EvaluateStage):
    id = "decision"
    label = "Compute release score and policy decision"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_release_evaluate_state(ctx)
        state.allow_dirty_build = bool(ctx.data.get("allow_dirty_build"))
        doctor = get_doctor_dependency(ctx)
        policy = load_policy_config()
        parts = score_from_doctor(
            doctor,
            test_discovery_ok=state.test_discovery_ok or state.test_discovery_local_env,
            policy=policy,
        )
        state.release_score_parts = parts
        state.release_score = aggregate_release_score(parts)
        state.rationale = (
            f"Policy decision based on doctor status `{state.doctor_overall_status}`, "
            f"facts from checks and advisory release score `{state.release_score}`."
        )
        apply_policy_engine(state, doctor=doctor, policy=policy)
        finalize_classification(state, doctor=doctor, policy=policy)
        if state.summary is not None:
            state.summary.deployment_recommendation = state.deployment_recommendation
        ctx.transaction.release_evaluate = state.to_dict()
        return StageResult(
            status=StageStatus.PASS,
            message=f"policy decision: {state.status.value} ({state.release_score}/100)",
        )


class SummaryStage(_EvaluateStage):
    id = "summary"
    label = "Render release manager report"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_release_evaluate_state(ctx)
        ctx.transaction.duration_ms = ctx.transaction.elapsed_ms()
        output_format = ctx.data.get("output_format", "terminal")
        report_path = ctx.data.get("report_path")
        markdown = render_markdown(state, transaction=ctx.transaction)
        json_report = render_json(state, transaction=ctx.transaction)
        ctx.data["report_markdown"] = markdown
        ctx.data["report_json"] = json_report

        if output_format in ("markdown", "terminal") or report_path:
            if output_format != "json" or report_path:
                out = Path(report_path) if report_path else default_report_path("IFG_RELEASE_EVALUATE")
                write_report(out, markdown)
                ctx.data["report_file"] = str(out)
                ctx.transaction.artifacts.append(
                    ArtifactRecord(type="ifg_release_evaluate_report", path=str(out))
                )
        return StageResult(status=StageStatus.PASS, message="release evaluation summary complete")
