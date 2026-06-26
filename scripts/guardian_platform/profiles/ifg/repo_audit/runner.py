from __future__ import annotations

from pathlib import Path

from guardian_platform.core.runtime.mode import ExecutionMode
from guardian_platform.core.workflow.engine import ExecutionEngine
from guardian_platform.core.workflow.state import WorkflowState
from guardian_platform.profiles.ifg.config.defaults import REPO_ROOT
from guardian_platform.profiles.ifg.repo_audit.report import (
    audit_from_transaction,
    exit_status_for_audit,
    render_json,
    render_markdown,
    render_terminal,
)
from guardian_platform.profiles.ifg.workflows.repo_audit import IFG_REPO_AUDIT_WORKFLOW


def execute_repo_audit(
    *,
    do_fetch: bool = False,
    dry_run: bool = False,
    output_format: str = "terminal",
    report_path: Path | None = None,
    root: Path | None = None,
):
    mode = ExecutionMode.DRY_RUN if dry_run else ExecutionMode.LIVE
    engine = ExecutionEngine(root=root or REPO_ROOT)
    return engine.run(
        IFG_REPO_AUDIT_WORKFLOW,
        mode=mode,
        initial_data={
            "do_fetch": do_fetch,
            "output_format": output_format,
            "report_path": str(report_path) if report_path else None,
        },
    )


def collect_audit(*, do_fetch: bool = False):
    ctx = execute_repo_audit(do_fetch=do_fetch, output_format="none")
    if ctx.state_machine.state != WorkflowState.SUCCESS:
        failed = next((s for s in ctx.transaction.stages if s.status == "fail"), None)
        detail = failed.message if failed else ctx.transaction.outcome
        raise RuntimeError(detail or "repo audit workflow failed")
    return audit_from_transaction(ctx.transaction)


def audit_from_context(ctx):
    if ctx.transaction.profile_data.get("audit"):
        return audit_from_transaction(ctx.transaction)
    from guardian_platform.profiles.ifg.repo_audit.service import get_audit_state

    return get_audit_state(ctx)


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
            if record.status == "fail":
                print(f"  Stage {record.id}: {record.message}")
        return 1

    audit = audit_from_context(ctx)

    if output_format == "json":
        print(render_json(audit, transaction=ctx.transaction))
        return exit_status_for_audit(audit)

    if output_format == "markdown":
        print(render_markdown(audit, transaction=ctx.transaction))
        return exit_status_for_audit(audit)

    if output_format != "none":
        print(render_terminal(audit, transaction=ctx.transaction))
        report_file = ctx.data.get("report_file")
        if report_file:
            try:
                rel = Path(report_file).relative_to(REPO_ROOT)
            except ValueError:
                rel = report_file
            print(f"\nReport: {rel}")

    return exit_status_for_audit(audit)
