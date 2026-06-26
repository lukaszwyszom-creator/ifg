from __future__ import annotations

from pathlib import Path

from ifg_guardian.config import ROOT
from ifg_guardian.core.plugins.bootstrap import create_runtime
from ifg_guardian.core.repo_audit.models import RepoAuditState
from ifg_guardian.core.repo_audit.report import (
    audit_from_transaction,
    exit_status_for_audit,
    render_json,
    render_markdown,
    render_terminal,
)
from ifg_guardian.core.repo_audit.service import get_audit_state
from ifg_guardian.core.workflow.engine import ExecutionEngine
from ifg_guardian.core.workflow.mode import ExecutionMode
from ifg_guardian.core.workflow.state import WorkflowState

CORE_REPO_AUDIT_ID = "core.repo.audit"


def execute_repo_audit(
    *,
    do_fetch: bool = False,
    dry_run: bool = False,
    output_format: str = "terminal",
    report_path: Path | None = None,
    root: Path | None = None,
):
    runtime = create_runtime(root=root)
    try:
        workflow = runtime.resolve_workflow(CORE_REPO_AUDIT_ID)
        if workflow is None:
            raise RuntimeError(f"workflow not registered: {CORE_REPO_AUDIT_ID}")

        mode = ExecutionMode.DRY_RUN if dry_run else ExecutionMode.LIVE
        engine = ExecutionEngine(root=runtime.config.root)
        return engine.run(
            workflow,
            mode=mode,
            initial_data={
                "do_fetch": do_fetch,
                "output_format": output_format,
                "report_path": str(report_path) if report_path else None,
            },
            plugin_registry=runtime.plugin_registry,
        )
    finally:
        runtime.shutdown()


def audit_from_context(ctx) -> RepoAuditState:
    if ctx.transaction.audit:
        return audit_from_transaction(ctx.transaction)
    return get_audit_state(ctx)


def collect_audit(*, do_fetch: bool = False) -> RepoAuditState:
    ctx = execute_repo_audit(do_fetch=do_fetch, output_format="none")
    if ctx.state_machine.state != WorkflowState.SUCCESS:
        failed = next((s for s in ctx.transaction.stages if s.status == "FAIL"), None)
        detail = failed.message if failed else ctx.transaction.outcome
        raise RuntimeError(detail or "repo audit workflow failed")
    return audit_from_context(ctx)


def run_repo_audit(
    *,
    do_fetch: bool = False,
    dry_run: bool = False,
    output_format: str = "terminal",
    report_path: Path | None = None,
) -> int:
    try:
        ctx = execute_repo_audit(
            do_fetch=do_fetch,
            dry_run=dry_run,
            output_format=output_format,
            report_path=report_path,
        )
    except RuntimeError as exc:
        print(f"\n❌ Audit failed: {exc}")
        return 1

    if ctx.state_machine.state != WorkflowState.SUCCESS:
        print(f"\n❌ Audit workflow failed: {ctx.transaction.outcome}")
        for record in ctx.transaction.stages:
            if record.status == "FAIL":
                print(f"  Stage {record.id}: {record.message}")
        return 1

    audit = audit_from_context(ctx)

    if output_format == "json":
        print(render_json(audit, transaction=ctx.transaction))
        return exit_status_for_audit(audit)

    if output_format == "markdown":
        print(render_markdown(audit, transaction=ctx.transaction))
        return exit_status_for_audit(audit)

    print(render_terminal(audit, transaction=ctx.transaction))
    report_file = ctx.data.get("report_file")
    if report_file:
        try:
            rel = Path(report_file).relative_to(ROOT)
        except ValueError:
            rel = report_file
        print(f"\nReport: {rel}")

    return exit_status_for_audit(audit)
