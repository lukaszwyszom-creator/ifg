from __future__ import annotations

from pathlib import Path

from ifg_guardian.config import TARGET_BRANCH
from ifg_guardian.core.repo_audit.actions import build_recommended_actions
from ifg_guardian.core.repo_audit.classifier import (
    classify_line_endings,
    classify_modified_path,
    classify_untracked,
)
from ifg_guardian.core.repo_audit.models import RepoAuditState
from ifg_guardian.core.repo_audit.report import render_json, render_markdown
from ifg_guardian.core.repo_audit.service import (
    aggregate_risk,
    collect_git_status,
    get_audit_state,
    get_extensions,
    parse_changed_paths,
)
from ifg_guardian.core.risk import FileCategory
from ifg_guardian.core.workflow.context import WorkflowContext
from ifg_guardian.core.workflow.intents import (
    FsExistsIntent,
    GitFetchIntent,
    GitRevParseIntent,
    GitStatusIntent,
    NoOpIntent,
)
from ifg_guardian.core.workflow.results import StageExecutionResults
from ifg_guardian.core.workflow.stage import BuildReason, Stage, StagePlan, StageResult, StageStatus
from ifg_guardian.core.workflow.transaction import ArtifactRecord
from ifg_guardian.reporting import default_report_path, write_report


class InitStage(Stage):
    id = "init"
    label = "Initialize repo audit"
    mutating = False

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        return StagePlan(intents=[NoOpIntent(reason="init repo audit")])

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        audit = RepoAuditState(do_fetch=bool(ctx.data.get("do_fetch", False)))
        ctx.data["audit"] = audit

        extensions = []
        if ctx.plugin_registry is not None:
            for plugin in ctx.plugin_registry.list():
                extensions.extend(plugin.repo_audit_extensions())
        ctx.data["repo_extensions"] = extensions

        ctx.data.setdefault("output_format", "terminal")
        return StageResult(status=StageStatus.PASS, message="audit initialized")


class CollectGitStatusStage(Stage):
    id = "collect_git_status"
    label = "Collect git status"
    mutating = False

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        audit = get_audit_state(ctx)
        intents = []
        if audit.do_fetch:
            intents.append(GitFetchIntent(remote="origin", branch=TARGET_BRANCH))
        intents.extend([
            GitRevParseIntent(ref="HEAD"),
            GitStatusIntent(porcelain=True),
        ])
        return StagePlan(intents=intents)

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        audit = get_audit_state(ctx)
        try:
            fetch_simulated = any(r.simulated for r in results.intent_results if r.intent.intent_type == "git_fetch")
            if audit.do_fetch and not fetch_simulated:
                for r in results.intent_results:
                    if r.intent.intent_type == "git_fetch" and not r.ok:
                        return StageResult(status=StageStatus.FAIL, message=r.error or "git fetch failed")
            collect_git_status(audit)
        except RuntimeError as exc:
            return StageResult(status=StageStatus.FAIL, message=str(exc))

        ctx.transaction.branch = audit.branch
        ctx.transaction.commit_before = audit.head
        ctx.transaction.commit_after = audit.head
        return StageResult(status=StageStatus.PASS, message="git status collected")


class CollectRepositoryMetadataStage(Stage):
    id = "collect_repository_metadata"
    label = "Collect repository metadata"
    mutating = False

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        return StagePlan(
            intents=[
                FsExistsIntent(path=".gitignore"),
                FsExistsIntent(path=".gitattributes"),
            ]
        )

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        audit = get_audit_state(ctx)
        for result in results.intent_results:
            if not result.ok:
                continue
            path = getattr(result.intent, "path", "")
            if path == ".gitignore":
                audit.gitignore_exists = bool(result.data.get("exists"))
            if path == ".gitattributes":
                audit.gitattributes_exists = bool(result.data.get("exists"))
        return StageResult(status=StageStatus.PASS, message="metadata collected")


class ClassifyFilesStage(Stage):
    id = "classify_files"
    label = "Classify changed files"
    mutating = False

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        return StagePlan(intents=[NoOpIntent(reason="classify files")])

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        audit = get_audit_state(ctx)
        extensions = get_extensions(ctx)
        audit.files = []

        for status, path in parse_changed_paths(audit.porcelain):
            if status == "??":
                audit.files.append(classify_untracked(path, extensions=extensions))
            elif "M" in status or "A" in status or "D" in status:
                audit.files.append(classify_modified_path(path, extensions=extensions))

        return StageResult(
            status=StageStatus.PASS,
            message=f"classified {len(audit.files)} file(s)",
        )


class LineEndingAnalysisStage(Stage):
    id = "line_ending_analysis"
    label = "Analyze line endings"
    mutating = False

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        return StagePlan(intents=[NoOpIntent(reason="line ending analysis")])

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        audit = get_audit_state(ctx)
        reasons: list[BuildReason] = []
        updated = 0

        for index, classified in enumerate(audit.files):
            if classified.status != "M":
                continue
            if classified.category in (FileCategory.IGNORE, FileCategory.DEPLOY_BLOCKER):
                continue

            eol_file, eol_reasons = classify_line_endings(classified.path)
            if eol_file is None:
                continue

            audit.files[index] = eol_file
            reasons.extend(eol_reasons)
            updated += 1

        return StageResult(
            status=StageStatus.PASS,
            message=f"line ending analysis on {updated} file(s)",
            reasons=reasons,
        )


class RiskAnalysisStage(Stage):
    id = "risk_analysis"
    label = "Aggregate risk"
    mutating = False

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        return StagePlan(intents=[NoOpIntent(reason="risk analysis")])

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        audit = get_audit_state(ctx)
        aggregate_risk(audit, extensions=get_extensions(ctx))
        return StageResult(
            status=StageStatus.PASS,
            message=f"overall risk: {audit.overall_risk.value}",
            reasons=[
                BuildReason(
                    decision="overall_risk",
                    because=[audit.overall_risk.value],
                    source_stage=self.id,
                )
            ],
        )


class RecommendedActionsStage(Stage):
    id = "recommended_actions"
    label = "Build recommended actions"
    mutating = False

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        return StagePlan(intents=[NoOpIntent(reason="recommended actions")])

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        audit = get_audit_state(ctx)
        audit.recommended_actions = build_recommended_actions(audit)
        ctx.transaction.recommended_actions = list(audit.recommended_actions)
        return StageResult(
            status=StageStatus.PASS,
            message=f"{len(audit.recommended_actions)} action(s)",
        )


class ReportStage(Stage):
    id = "report"
    label = "Generate report"
    mutating = False

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        return StagePlan(intents=[NoOpIntent(reason="report")])

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        audit = get_audit_state(ctx)
        ctx.transaction.audit = audit.to_dict()

        output_format = ctx.data.get("output_format", "terminal")
        report_path = ctx.data.get("report_path")

        markdown = render_markdown(audit, transaction=ctx.transaction)
        json_report = render_json(audit, transaction=ctx.transaction)

        ctx.data["report_markdown"] = markdown
        ctx.data["report_json"] = json_report

        if output_format in ("markdown", "terminal") or report_path:
            if output_format != "json" or report_path:
                out = Path(report_path) if report_path else default_report_path("REPO_AUDIT")
                write_report(out, markdown)
                ctx.data["report_file"] = str(out)
                ctx.transaction.artifacts.append(
                    ArtifactRecord(type="repo_audit_report", path=str(out))
                )

        return StageResult(status=StageStatus.PASS, message=f"report format: {output_format}")


class SummaryStage(Stage):
    id = "summary"
    label = "Summarize repo audit"
    mutating = False

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        return StagePlan(intents=[NoOpIntent(reason="summary")])

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        audit = get_audit_state(ctx)
        ctx.data["summary"] = {
            "files": len(audit.files),
            "overall_risk": audit.overall_risk.value,
            "dirty": audit.dirty,
        }
        return StageResult(status=StageStatus.PASS, message="summary complete")
