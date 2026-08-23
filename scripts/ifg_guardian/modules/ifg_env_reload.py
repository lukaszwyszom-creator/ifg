from __future__ import annotations

import json
from pathlib import Path

from ifg_guardian.config import DEFAULT_REMOTE_PATH, ROOT
from ifg_guardian.core.plugins.bootstrap import create_runtime
from ifg_guardian.core.workflow.engine import ExecutionEngine
from ifg_guardian.core.workflow.mode import ExecutionMode
from ifg_guardian.core.workflow.state import WorkflowState
from ifg_guardian.plugins.ifg.env_reload.aggregation import exit_code_for_env_reload
from ifg_guardian.plugins.ifg.env_reload.models import EnvReloadState
from ifg_guardian.plugins.ifg.env_reload.report import render_env_reload_markdown

IFG_ENV_RELOAD_ID = "ifg.env.reload"
LIVE_REQUIRES_YES = "LIVE env reload requires --yes."


def _state_from_transaction(transaction) -> EnvReloadState:
    payload = transaction.env_reload or {}
    return EnvReloadState.from_dict(payload)


def execute_ifg_env_reload(
    *,
    dry_run: bool = False,
    assume_yes: bool = False,
    output_format: str = "terminal",
    report_path: Path | None = None,
    remote_host: str | None = None,
    remote_path: str = DEFAULT_REMOTE_PATH,
    progress_enabled: bool | None = None,
    root: Path | None = None,
):
    if not dry_run and not assume_yes:
        raise RuntimeError(LIVE_REQUIRES_YES)

    runtime = create_runtime(root=root)
    try:
        workflow = runtime.resolve_workflow(IFG_ENV_RELOAD_ID)
        if workflow is None:
            raise RuntimeError(f"workflow not registered: {IFG_ENV_RELOAD_ID}")

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
                "progress_enabled": progress_enabled,
            },
            plugin_registry=runtime.plugin_registry,
        )
    finally:
        runtime.shutdown()


def run_ifg_env_reload(
    *,
    dry_run: bool = False,
    assume_yes: bool = False,
    output_format: str = "terminal",
    report_path: Path | None = None,
    remote_host: str | None = None,
    remote_path: str = DEFAULT_REMOTE_PATH,
    progress_enabled: bool | None = None,
) -> int:
    if not dry_run and not assume_yes:
        print(LIVE_REQUIRES_YES)
        return 2

    try:
        ctx = execute_ifg_env_reload(
            dry_run=dry_run,
            assume_yes=assume_yes,
            output_format=output_format,
            report_path=report_path,
            remote_host=remote_host,
            remote_path=remote_path,
            progress_enabled=progress_enabled,
        )
    except RuntimeError as exc:
        print(f"\n❌ Env reload workflow failed: {exc}")
        return 1

    state = _state_from_transaction(ctx.transaction)
    if not state.summary and ctx.state_machine.state != WorkflowState.SUCCESS:
        print(f"\n❌ Env reload workflow failed: {ctx.transaction.outcome}")
        for record in ctx.transaction.stages:
            if record.status == "fail":
                print(f"  Stage {record.id}: {record.message}")
        return 1

    if output_format == "json":
        payload = {
            "schema": "ifg_env_reload_report_v1",
            "workflow": ctx.transaction.to_dict(),
            "env_reload": state.to_dict(),
        }
        print(json.dumps(payload, indent=2))
    else:
        print(render_env_reload_markdown(state, transaction=ctx.transaction))
        report_file = ctx.data.get("report_file")
        if report_file:
            try:
                rel = Path(report_file).relative_to(ROOT)
            except ValueError:
                rel = report_file
            print(f"\nReport: {rel}")

    return exit_code_for_env_reload(state)
