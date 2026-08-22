from __future__ import annotations

from pathlib import Path

from guardian_platform.core.repository.report import ReportExistsError, write_markdown_report
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
    root: Path | None = None,
):
    if root is None:
        root = REPO_ROOT
    repo = root.resolve()
    mode = ExecutionMode.DRY_RUN if dry_run else ExecutionMode.LIVE
    engine = ExecutionEngine(root=repo)
    return engine.run(
        IFG_REPO_AUDIT_WORKFLOW,
        mode=mode,
        initial_data={
            "do_fetch": do_fetch,
            "output_format": output_format,
        },
    )


def collect_audit(*, do_fetch: bool = False, root: Path | None = None):
    repo = (root or REPO_ROOT).resolve()
    ctx = execute_repo_audit(do_fetch=do_fetch, output_format="none", root=repo)
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
    root: Path,
    do_fetch: bool = False,
    dry_run: bool = False,
    output_format: str = "terminal",
    output_path: Path | None = None,
    force: bool = False,
) -> int:
    repo = root.resolve()
    if not repo.is_dir():
        print(f"Invalid repository root: {repo}")
        return 2
    if not (repo / ".git").exists():
        print(f"Not a git repository: {repo}")
        return 2

    try:
        ctx = execute_repo_audit(
            do_fetch=do_fetch,
            dry_run=dry_run,
            output_format=output_format,
            root=repo,
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
    markdown = ctx.data.get("report_markdown") or render_markdown(audit, transaction=ctx.transaction)
    json_text = ctx.data.get("report_json") or render_json(audit, transaction=ctx.transaction)

    written_path: Path | None = None
    if output_path is not None:
        content = json_text if output_format == "json" else markdown
        try:
            written_path = write_markdown_report(repo, content, output_path, force=force)
        except ReportExistsError as exc:
            print(str(exc))
            return 2

    if output_format == "json":
        print(json_text)
    elif output_format == "markdown":
        print(markdown)
    elif output_format != "none":
        print(render_terminal(audit, transaction=ctx.transaction))

    if written_path is not None:
        try:
            rel = written_path.relative_to(repo)
        except ValueError:
            rel = written_path
        print(f"Audit report: {rel}")

    return exit_status_for_audit(audit)
