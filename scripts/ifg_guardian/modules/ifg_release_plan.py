from __future__ import annotations

from pathlib import Path

from ifg_guardian.config import DEFAULT_REMOTE_PATH, ROOT
from ifg_guardian.core.plugins.bootstrap import create_runtime
from ifg_guardian.core.workflow.engine import ExecutionEngine
from ifg_guardian.core.workflow.mode import ExecutionMode
from ifg_guardian.core.workflow.state import WorkflowState
from ifg_guardian.plugins.ifg.release_plan.models import ReleasePlanState
from ifg_guardian.plugins.ifg.release_plan.report import (
    plan_from_transaction,
    render_json,
    render_markdown,
    render_terminal,
)
from ifg_guardian.plugins.ifg.release_plan.risk import exit_code_for_risk
from ifg_guardian.plugins.ifg.release_plan.service import get_plan_state

IFG_RELEASE_PLAN_ID = "ifg.release.plan"


def execute_ifg_release_plan(
    *,
    do_fetch: bool = False,
    output_format: str = "terminal",
    report_path: Path | None = None,
    remote_host: str | None = None,
    remote_path: str = DEFAULT_REMOTE_PATH,
    root: Path | None = None,
):
    runtime = create_runtime(root=root)
    try:
        workflow = runtime.resolve_workflow(IFG_RELEASE_PLAN_ID)
        if workflow is None:
            raise RuntimeError(f"workflow not registered: {IFG_RELEASE_PLAN_ID}")

        engine = ExecutionEngine(root=runtime.config.root)
        return engine.run(
            workflow,
            mode=ExecutionMode.LIVE,
            initial_data={
                "do_fetch": do_fetch,
                "output_format": output_format,
                "report_path": str(report_path) if report_path else None,
                "remote_host": remote_host,
                "remote_path": remote_path,
            },
            plugin_registry=runtime.plugin_registry,
        )
    finally:
        runtime.shutdown()


def plan_from_context(ctx) -> ReleasePlanState:
    if ctx.transaction.release_plan:
        return plan_from_transaction(ctx.transaction)
    return get_plan_state(ctx)


def run_ifg_release_plan(
    *,
    do_fetch: bool = False,
    output_format: str = "terminal",
    report_path: Path | None = None,
    remote_host: str | None = None,
    remote_path: str = DEFAULT_REMOTE_PATH,
) -> int:
    try:
        ctx = execute_ifg_release_plan(
            do_fetch=do_fetch,
            output_format=output_format,
            report_path=report_path,
            remote_host=remote_host,
            remote_path=remote_path,
        )
    except RuntimeError as exc:
        print(f"\n❌ Release plan failed: {exc}")
        return 1

    if ctx.state_machine.state != WorkflowState.SUCCESS:
        print(f"\n❌ Release plan workflow failed: {ctx.transaction.outcome}")
        for record in ctx.transaction.stages:
            if record.status == "fail":
                print(f"  Stage {record.id}: {record.message}")
        return 1

    state = plan_from_context(ctx)

    if output_format == "json":
        print(render_json(state, transaction=ctx.transaction))
        return exit_code_for_risk(state.deployment_risk)

    if output_format == "markdown":
        print(render_markdown(state, transaction=ctx.transaction))
        return exit_code_for_risk(state.deployment_risk)

    print(render_terminal(state, transaction=ctx.transaction))
    report_file = ctx.data.get("report_file")
    if report_file:
        try:
            rel = Path(report_file).relative_to(ROOT)
        except ValueError:
            rel = report_file
        print(f"\nReport: {rel}")

    return exit_code_for_risk(state.deployment_risk)
