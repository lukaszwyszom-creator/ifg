from __future__ import annotations

from pathlib import Path

from ifg_guardian.config import DEFAULT_REMOTE_PATH, ROOT
from ifg_guardian.core.plugins.bootstrap import create_runtime
from ifg_guardian.core.workflow.engine import ExecutionEngine
from ifg_guardian.core.workflow.mode import ExecutionMode
from ifg_guardian.core.workflow.state import WorkflowState
from ifg_guardian.plugins.ifg.release_evaluate.models import (
    ReleaseDecisionStatus,
    ReleaseEvaluateState,
)
from ifg_guardian.plugins.ifg.release_evaluate.report import (
    evaluate_from_transaction,
    render_json,
    render_markdown,
    render_terminal,
)
from ifg_guardian.plugins.ifg.release_evaluate.policy_engine import load_policy_config
from ifg_guardian.plugins.ifg.release_evaluate.service import get_release_evaluate_state

IFG_RELEASE_EVALUATE_ID = "ifg.release.evaluate"


def execute_ifg_release_evaluate(
    *,
    do_fetch: bool = False,
    allow_dirty_build: bool = False,
    output_format: str = "terminal",
    report_path: Path | None = None,
    remote_host: str | None = None,
    remote_path: str = DEFAULT_REMOTE_PATH,
    progress_enabled: bool | None = None,
    root: Path | None = None,
):
    runtime = create_runtime(root=root)
    try:
        workflow = runtime.resolve_workflow(IFG_RELEASE_EVALUATE_ID)
        if workflow is None:
            raise RuntimeError(f"workflow not registered: {IFG_RELEASE_EVALUATE_ID}")

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
                "progress_enabled": progress_enabled,
                "allow_dirty_build": allow_dirty_build,
            },
            plugin_registry=runtime.plugin_registry,
        )
    finally:
        runtime.shutdown()


def evaluate_from_context(ctx) -> ReleaseEvaluateState:
    if ctx.transaction.release_evaluate:
        return evaluate_from_transaction(ctx.transaction)
    return get_release_evaluate_state(ctx)


def _exit_code_for_decision(status: ReleaseDecisionStatus) -> int:
    if status == ReleaseDecisionStatus.READY_FOR_DEPLOY:
        return 0
    if status in (ReleaseDecisionStatus.READY_WITH_WARNINGS, ReleaseDecisionStatus.READY_WITH_OVERRIDE):
        return 1
    if status == ReleaseDecisionStatus.STAGING_ONLY:
        return 2
    return 3


def run_ifg_release_evaluate(
    *,
    do_fetch: bool = False,
    allow_dirty_build: bool = False,
    output_format: str = "terminal",
    report_path: Path | None = None,
    remote_host: str | None = None,
    remote_path: str = DEFAULT_REMOTE_PATH,
    progress_enabled: bool | None = None,
) -> int:
    try:
        ctx = execute_ifg_release_evaluate(
            do_fetch=do_fetch,
            allow_dirty_build=allow_dirty_build,
            output_format=output_format,
            report_path=report_path,
            remote_host=remote_host,
            remote_path=remote_path,
            progress_enabled=progress_enabled,
        )
    except RuntimeError as exc:
        print(f"\n❌ Release evaluate failed: {exc}")
        return 1

    if ctx.state_machine.state != WorkflowState.SUCCESS:
        print(f"\n❌ Release evaluate workflow failed: {ctx.transaction.outcome}")
        for record in ctx.transaction.stages:
            if record.status == "fail":
                print(f"  Stage {record.id}: {record.message}")
        return 1

    state = evaluate_from_context(ctx)

    if output_format == "json":
        print(render_json(state, transaction=ctx.transaction))
        return _exit_code_for_decision(state.status)

    if output_format == "markdown":
        print(render_markdown(state, transaction=ctx.transaction))
        return _exit_code_for_decision(state.status)

    print(render_terminal(state, transaction=ctx.transaction))
    report_file = ctx.data.get("report_file")
    if report_file:
        try:
            rel = Path(report_file).relative_to(ROOT)
        except ValueError:
            rel = report_file
        print(f"\nReport: {rel}")
    return _exit_code_for_decision(state.status)


def run_ifg_release_explain(*, output_format: str = "terminal") -> int:
    policy = load_policy_config()
    if output_format == "json":
        import json

        print(json.dumps(policy, indent=2))
        return 0

    print("IFG Guardian — Release Policy Explain")
    print("=" * 44)
    print("Policy Engine podejmuje decyzję końcową dla release evaluate.")
    print("Plik policy:")
    print("  scripts/ifg_guardian/policies/ifg_production.yaml")
    print("")
    print("Critical migration tables:")
    for name in policy.get("critical_migration_tables", []):
        print(f"  • {name}")
    print("")
    print("Suspicious untracked patterns:")
    for pat in policy.get("non_report_untracked_block_patterns", []):
        print(f"  • {pat}")
    print("")
    print("Report paths ignored for untracked policy:")
    for prefix in policy.get("report_paths", []):
        print(f"  • {prefix}")
    return 0
