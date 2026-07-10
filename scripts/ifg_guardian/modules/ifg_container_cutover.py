from __future__ import annotations

from pathlib import Path

from ifg_guardian.config import DEFAULT_REMOTE_PATH, ROOT
from ifg_guardian.core.execution_guard import enforce_mutating_live_orchestration
from ifg_guardian.core.plugins.bootstrap import create_runtime
from ifg_guardian.core.workflow.engine import ExecutionEngine
from ifg_guardian.core.workflow.executors.context import DeployExecutorContext
from ifg_guardian.core.workflow.executors.ssh_executor import SSHExecutor
from ifg_guardian.core.workflow.mode import ExecutionMode
from ifg_guardian.core.workflow.state import WorkflowState
from ifg_guardian.plugins.ifg.container_cutover.remote import rollback_script
from ifg_guardian.plugins.ifg.container_cutover.service import get_cutover_state

IFG_CONTAINER_CUTOVER_ID = "ifg.container.cutover"
LIVE_REQUIRES_YES = "LIVE cutover requires --yes."


def execute_ifg_container_cutover(
    *,
    dry_run: bool = False,
    assume_yes: bool = False,
    confirm_functional: bool = False,
    cleanup: bool = False,
    output_format: str = "terminal",
    report_path: Path | None = None,
    precheck_report_path: Path | None = None,
    remote_host: str | None = None,
    remote_path: str = DEFAULT_REMOTE_PATH,
    progress_enabled: bool | None = None,
    root: Path | None = None,
):
    if not dry_run and not assume_yes:
        raise RuntimeError(LIVE_REQUIRES_YES)

    runtime = create_runtime(root=root)
    try:
        workflow = runtime.resolve_workflow(IFG_CONTAINER_CUTOVER_ID)
        if workflow is None:
            raise RuntimeError(f"workflow not registered: {IFG_CONTAINER_CUTOVER_ID}")

        engine = ExecutionEngine(root=runtime.config.root)
        mode = ExecutionMode.DRY_RUN if dry_run else ExecutionMode.LIVE
        return engine.run(
            workflow,
            mode=mode,
            initial_data={
                "output_format": output_format,
                "report_path": str(report_path) if report_path else None,
                "precheck_report_path": str(precheck_report_path) if precheck_report_path else None,
                "remote_host": remote_host,
                "remote_path": remote_path,
                "assume_yes": assume_yes,
                "confirm_functional": confirm_functional,
                "cleanup": cleanup,
                "progress_enabled": progress_enabled,
            },
            plugin_registry=runtime.plugin_registry,
        )
    finally:
        runtime.shutdown()


def run_ifg_container_cutover(
    *,
    dry_run: bool = False,
    assume_yes: bool = False,
    confirm_functional: bool = False,
    cleanup: bool = False,
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
        ctx = execute_ifg_container_cutover(
            dry_run=dry_run,
            assume_yes=assume_yes,
            confirm_functional=confirm_functional,
            cleanup=cleanup,
            output_format=output_format,
            report_path=report_path,
            remote_host=remote_host,
            remote_path=remote_path,
            progress_enabled=progress_enabled,
        )
    except RuntimeError as exc:
        print(f"\n❌ Container cutover failed: {exc}")
        return 1

    state = get_cutover_state(ctx)
    report_file = ctx.data.get("report_file")

    if ctx.state_machine.state != WorkflowState.SUCCESS:
        print(f"\n❌ Cutover workflow failed: {ctx.transaction.outcome}")
        for record in ctx.transaction.stages:
            if record.status in ("fail", "FAIL"):
                print(f"  Stage {record.id}: {record.message}")
        if state.rollback_command:
            print(f"\nRollback:\n  {state.rollback_command}")
        return 1

    if output_format == "markdown" and report_file:
        print(Path(report_file).read_text(encoding="utf-8"))
    else:
        print(f"\n✅ Cutover workflow {ctx.transaction.outcome}")
        print(f"  Safety Gate: {state.safety_gate}")
        print(f"  Backup: {state.backup_file or 'n/a'}")
        print(f"  Cutover executed: {state.cutover_executed}")
        print(f"  Health OK: {state.health_ok}")
        print(f"  Guardian verify: {state.guardian_verify_ok}")
        if not state.functional_confirmed:
            print("\n⚠️  Functional tests not attested — complete checklist, then:")
            print("  python3 scripts/guardian.py ifg cutover run --yes --confirm-functional --cleanup")
        elif not state.cleanup_executed:
            print("\nℹ️  Cleanup skipped — to remove legacy docker-*:")
            print("  python3 scripts/guardian.py ifg cutover run --yes --confirm-functional --cleanup")

    if report_file:
        try:
            rel = Path(report_file).relative_to(ROOT)
        except ValueError:
            rel = report_file
        print(f"\nReport: {rel}")

    return 0


def run_ifg_container_cutover_rollback(
    *,
    dry_run: bool = False,
    assume_yes: bool = False,
    remote_host: str | None = None,
    remote_path: str = DEFAULT_REMOTE_PATH,
) -> int:
    if not dry_run and not assume_yes:
        print("LIVE rollback requires --yes.")
        return 2

    try:
        enforce_mutating_live_orchestration(
            dry_run=dry_run,
            root=ROOT,
            remote_path=remote_path,
        )
    except RuntimeError as exc:
        print(f"\n❌ Container cutover rollback blocked: {exc}")
        return 1

    deploy_ctx = DeployExecutorContext(remote_host=remote_host, remote_path=remote_path)
    ssh = SSHExecutor(root=ROOT, deploy_context=deploy_ctx)
    cfg = deploy_ctx.config()
    script = rollback_script(cfg)

    if dry_run:
        print("[dry-run] would execute rollback on DS723+:")
        print(script)
        return 0

    result = ssh.run_remote(script, label="cutover_rollback")
    if not result.ok:
        print(f"❌ Rollback failed: {result.error or result.output}")
        return 1

    print("✅ Rollback completed")
    print(result.output)
    return 0
