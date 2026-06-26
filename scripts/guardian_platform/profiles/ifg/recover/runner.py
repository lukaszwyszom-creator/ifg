from __future__ import annotations

from pathlib import Path

from guardian_platform.core.runtime.mode import ExecutionMode
from guardian_platform.core.workflow.engine import ExecutionEngine
from guardian_platform.core.workflow.state import WorkflowState
from guardian_platform.profiles.ifg.config.defaults import DEFAULT_REMOTE_PATH, REPO_ROOT
from guardian_platform.profiles.ifg.recover.report import (
    exit_code_for_recover,
    render_json,
    render_markdown,
    render_terminal,
)
from guardian_platform.profiles.ifg.recover.service import get_recover_state
from guardian_platform.profiles.ifg.workflows.prod_recover import IFG_PROD_RECOVER_WORKFLOW

LIVE_REQUIRES_YES = "LIVE recover requires --yes."


def execute_prod_recover(
    *,
    dry_run: bool = False,
    assume_yes: bool = False,
    output_format: str = "terminal",
    report_path: Path | None = None,
    remote_host: str | None = None,
    remote_path: str = DEFAULT_REMOTE_PATH,
):
    if not dry_run and not assume_yes:
        raise RuntimeError(LIVE_REQUIRES_YES)

    mode = ExecutionMode.DRY_RUN if dry_run else ExecutionMode.LIVE
    engine = ExecutionEngine(root=REPO_ROOT)
    return engine.run(
        IFG_PROD_RECOVER_WORKFLOW,
        mode=mode,
        initial_data={
            "output_format": output_format,
            "report_path": str(report_path) if report_path else None,
            "remote_host": remote_host,
            "remote_path": remote_path,
            "assume_yes": assume_yes,
        },
    )


def run_prod_recover(
    *,
    dry_run: bool = False,
    assume_yes: bool = False,
    output_format: str = "terminal",
    report_path: Path | None = None,
    remote_host: str | None = None,
    remote_path: str = DEFAULT_REMOTE_PATH,
) -> int:
    if not dry_run and not assume_yes:
        print(LIVE_REQUIRES_YES)
        return 2

    try:
        ctx = execute_prod_recover(
            dry_run=dry_run,
            assume_yes=assume_yes,
            output_format=output_format,
            report_path=report_path,
            remote_host=remote_host,
            remote_path=remote_path,
        )
    except RuntimeError as exc:
        print(f"\n❌ Prod recover failed: {exc}")
        return 1

    state = get_recover_state(ctx)

    if output_format == "json":
        print(render_json(state, transaction=ctx.transaction))
    elif output_format == "markdown":
        print(render_markdown(state, transaction=ctx.transaction))
    else:
        print(render_terminal(state, transaction=ctx.transaction))
        report_file = ctx.data.get("report_file")
        if report_file:
            try:
                rel = Path(report_file).relative_to(REPO_ROOT)
            except ValueError:
                rel = report_file
            print(f"\nReport: {rel}")

    if ctx.state_machine.state != WorkflowState.SUCCESS:
        return 1
    return exit_code_for_recover(state)
