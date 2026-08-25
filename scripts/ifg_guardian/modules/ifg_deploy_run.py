from __future__ import annotations

from pathlib import Path

from ifg_guardian.config import DEFAULT_REMOTE_PATH, ROOT
from ifg_guardian.core.plugins.bootstrap import create_runtime
from ifg_guardian.core.workflow.engine import ExecutionEngine
from ifg_guardian.core.workflow.mode import ExecutionMode
from ifg_guardian.core.workflow.state import WorkflowState
from ifg_guardian.plugins.ifg.deploy_run.models import DeployRunState
from ifg_guardian.plugins.ifg.deploy_run.report import (
    deploy_from_transaction,
    exit_code_for_deploy,
    render_json,
    render_markdown,
    render_terminal,
)
from ifg_guardian.plugins.ifg.deploy_run.service import get_deploy_state

IFG_DEPLOY_RUN_ID = "ifg.deploy.run"
LIVE_REQUIRES_YES = "LIVE deploy requires --yes."


def execute_ifg_deploy_run(
    *,
    dry_run: bool = False,
    assume_yes: bool = False,
    allow_dirty_build: bool = False,
    skip_preflight: bool = False,
    output_format: str = "terminal",
    report_path: Path | None = None,
    remote_host: str | None = None,
    remote_path: str = DEFAULT_REMOTE_PATH,
    progress_enabled: bool | None = None,
    root: Path | None = None,
    build_commit: str | None = None,
    keep_build_snapshot: bool = False,
    skip_build_snapshot: bool = False,
):
    if not dry_run and not assume_yes:
        raise RuntimeError(LIVE_REQUIRES_YES)

    runtime = create_runtime(root=root)
    try:
        workflow = runtime.resolve_workflow(IFG_DEPLOY_RUN_ID)
        if workflow is None:
            raise RuntimeError(f"workflow not registered: {IFG_DEPLOY_RUN_ID}")

        engine = ExecutionEngine(root=runtime.config.root)
        mode = ExecutionMode.DRY_RUN if dry_run else ExecutionMode.LIVE
        return engine.run(
            workflow,
            mode=mode,
            initial_data={
                "output_format": output_format,
                "report_path": str(report_path) if report_path else None,
                "remote_host": remote_host,
                "remote_path": remote_path,
                "assume_yes": assume_yes,
                "allow_dirty_build": allow_dirty_build,
                "skip_preflight": skip_preflight,
                "progress_enabled": progress_enabled,
                "build_commit": build_commit,
                "keep_build_snapshot": keep_build_snapshot,
                "skip_build_snapshot": skip_build_snapshot,
            },
            plugin_registry=runtime.plugin_registry,
        )
    finally:
        runtime.shutdown()


def deploy_from_context(ctx) -> DeployRunState:
    if ctx.transaction.deploy_run:
        return deploy_from_transaction(ctx.transaction)
    return get_deploy_state(ctx)


def run_ifg_deploy_run(
    *,
    dry_run: bool = False,
    assume_yes: bool = False,
    allow_dirty_build: bool = False,
    skip_preflight: bool = False,
    output_format: str = "terminal",
    report_path: Path | None = None,
    remote_host: str | None = None,
    remote_path: str = DEFAULT_REMOTE_PATH,
    progress_enabled: bool | None = None,
) -> int:
    if not dry_run and not assume_yes:
        print(LIVE_REQUIRES_YES)
        return 2

    from ifg_guardian.core.runtime_audit import RuntimeAuditSession

    audit = RuntimeAuditSession(
        workflow="ifg.deploy.run",
        event_type="deploy",
        reason="allow_dirty_build" if allow_dirty_build else None,
        target=remote_path,
    )
    if dry_run:
        audit.started(extra={"dry_run": True})
    else:
        audit.started()

    try:
        ctx = execute_ifg_deploy_run(
            dry_run=dry_run,
            assume_yes=assume_yes,
            allow_dirty_build=allow_dirty_build,
            skip_preflight=skip_preflight,
            output_format=output_format,
            report_path=report_path,
            remote_host=remote_host,
            remote_path=remote_path,
            progress_enabled=progress_enabled,
        )
    except RuntimeError as exc:
        if not dry_run:
            audit.failed(str(exc))
        print(f"\n❌ Deploy run failed: {exc}")
        return 1

    if ctx.state_machine.state != WorkflowState.SUCCESS:
        if not dry_run:
            audit.failed(ctx.transaction.outcome or "workflow failed")
        print(f"\n❌ Deploy workflow failed: {ctx.transaction.outcome}")
        for record in ctx.transaction.stages:
            if record.status in ("fail", "FAIL"):
                print(f"  Stage {record.id}: {record.message}")
        return 1

    state = deploy_from_context(ctx)

    if output_format == "json":
        print(render_json(state, transaction=ctx.transaction))
        code = exit_code_for_deploy(state)
    elif output_format == "markdown":
        print(render_markdown(state, transaction=ctx.transaction))
        code = exit_code_for_deploy(state)
    else:
        print(render_terminal(state, transaction=ctx.transaction))
        report_file = ctx.data.get("report_file")
        if report_file:
            try:
                rel = Path(report_file).relative_to(ROOT)
            except ValueError:
                rel = report_file
            print(f"\nReport: {rel}")
        code = exit_code_for_deploy(state)

    if not dry_run:
        if code == 0:
            audit.completed(result="ok", extra={"release_decision": state.release_decision})
        else:
            audit.failed(f"deploy exit {code}")
    else:
        audit.completed(result="dry_run")
    return code
