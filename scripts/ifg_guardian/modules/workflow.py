from __future__ import annotations

from ifg_guardian.core.plugins.bootstrap import create_runtime
from ifg_guardian.core.workflow.engine import ExecutionEngine
from ifg_guardian.core.workflow.mode import ExecutionMode
from ifg_guardian.core.workflow.state import WorkflowState


def run_workflow(workflow_id: str, *, dry_run: bool = False, plan: bool = False) -> int:
    runtime = create_runtime()
    try:
        workflow = runtime.resolve_workflow(workflow_id)
        if workflow is None:
            print(f"Unknown workflow: {workflow_id}")
            return 2

        if plan:
            mode = ExecutionMode.PLAN
        elif dry_run:
            mode = ExecutionMode.DRY_RUN
        else:
            mode = ExecutionMode.LIVE

        print(f"Guardian Workflow — {workflow_id}")
        print("=" * 40)
        print(f"Mode: {mode.value}")

        engine = ExecutionEngine(root=runtime.config.root)
        ctx = engine.run(workflow, mode=mode)

        print(f"\nWorkflow ID: {ctx.workflow_id}")
        print(f"Outcome: {ctx.transaction.outcome}")
        print(f"State: {ctx.state_machine.state.value}")
        print(f"Duration: {ctx.transaction.duration_ms} ms")

        for record in ctx.transaction.stages:
            print(f"  [{record.status}] {record.id} ({record.duration_ms} ms) — {record.message}")

        if ctx.transaction.warnings:
            print("\nWarnings:")
            for warning in ctx.transaction.warnings:
                print(f"  • {warning}")

        if ctx.transaction.artifacts:
            print("\nArtifacts:")
            for artifact in ctx.transaction.artifacts:
                print(f"  • {artifact.type}: {artifact.path}")

        print("\n" + "=" * 40)
        if ctx.state_machine.state == WorkflowState.SUCCESS:
            print("Status: SUCCESS")
            return 0
        if ctx.state_machine.state == WorkflowState.ABORTED:
            print("Status: ABORTED")
            return 2
        print("Status: FAILED")
        return 1
    finally:
        runtime.shutdown()
