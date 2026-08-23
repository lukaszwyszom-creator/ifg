from __future__ import annotations

import json
from pathlib import Path

from ifg_guardian.config import DEFAULT_REMOTE_PATH, ROOT
from ifg_guardian.core.plugins.bootstrap import create_runtime
from ifg_guardian.core.workflow.engine import ExecutionEngine
from ifg_guardian.core.workflow.mode import ExecutionMode
from ifg_guardian.core.workflow.state import WorkflowState
from ifg_guardian.plugins.ifg.smtp.aggregation import exit_code_for_smtp
from ifg_guardian.plugins.ifg.smtp.models import SmtpState
from ifg_guardian.plugins.ifg.smtp.report import render_smtp_markdown

IFG_SMTP_CHECK_ID = "ifg.smtp.check"
IFG_SMTP_TEST_ID = "ifg.smtp.test"


def _smtp_from_transaction(transaction) -> SmtpState:
    payload = transaction.smtp or {}
    return SmtpState.from_dict(payload)


def execute_ifg_smtp(
    *,
    mode: str,
    dry_run: bool = False,
    assume_yes: bool = False,
    use_local: bool = False,
    output_format: str = "terminal",
    report_path: Path | None = None,
    env_file: Path | None = None,
    remote_host: str | None = None,
    remote_path: str = DEFAULT_REMOTE_PATH,
    progress_enabled: bool | None = None,
    root: Path | None = None,
):
    workflow_id = IFG_SMTP_TEST_ID if mode == "test" else IFG_SMTP_CHECK_ID
    runtime = create_runtime(root=root)
    try:
        workflow = runtime.resolve_workflow(workflow_id)
        if workflow is None:
            raise RuntimeError(f"workflow not registered: {workflow_id}")

        exec_mode = ExecutionMode.DRY_RUN if dry_run else ExecutionMode.LIVE
        if mode == "test" and not dry_run and not assume_yes:
            raise RuntimeError("SMTP test requires --yes (or --dry-run)")

        engine = ExecutionEngine(root=runtime.config.root)
        return engine.run(
            workflow,
            mode=exec_mode,
            initial_data={
                "smtp_mode": mode,
                "use_local": use_local,
                "output_format": output_format,
                "report_path": str(report_path) if report_path else None,
                "env_file": str(env_file) if env_file else None,
                "remote_host": remote_host,
                "remote_path": remote_path,
                "assume_yes": assume_yes,
                "progress_enabled": progress_enabled,
            },
            plugin_registry=runtime.plugin_registry,
        )
    finally:
        runtime.shutdown()


def run_ifg_smtp_check(
    *,
    use_local: bool = False,
    output_format: str = "terminal",
    report_path: Path | None = None,
    env_file: Path | None = None,
    remote_host: str | None = None,
    remote_path: str = DEFAULT_REMOTE_PATH,
    progress_enabled: bool | None = None,
) -> int:
    return _run_ifg_smtp(
        mode="check",
        use_local=use_local,
        output_format=output_format,
        report_path=report_path,
        env_file=env_file,
        remote_host=remote_host,
        remote_path=remote_path,
        progress_enabled=progress_enabled,
    )


def run_ifg_smtp_test(
    *,
    assume_yes: bool = False,
    dry_run: bool = False,
    use_local: bool = False,
    output_format: str = "terminal",
    report_path: Path | None = None,
    env_file: Path | None = None,
    remote_host: str | None = None,
    remote_path: str = DEFAULT_REMOTE_PATH,
    progress_enabled: bool | None = None,
) -> int:
    return _run_ifg_smtp(
        mode="test",
        assume_yes=assume_yes,
        dry_run=dry_run,
        use_local=use_local,
        output_format=output_format,
        report_path=report_path,
        env_file=env_file,
        remote_host=remote_host,
        remote_path=remote_path,
        progress_enabled=progress_enabled,
    )


def run_ifg_smtp_report(
    *,
    use_local: bool = False,
    report_path: Path | None = None,
    env_file: Path | None = None,
    remote_host: str | None = None,
    remote_path: str = DEFAULT_REMOTE_PATH,
) -> int:
    return run_ifg_smtp_check(
        use_local=use_local,
        output_format="markdown",
        report_path=report_path,
        env_file=env_file,
        remote_host=remote_host,
        remote_path=remote_path,
    )


def _run_ifg_smtp(
    *,
    mode: str,
    assume_yes: bool = False,
    dry_run: bool = False,
    use_local: bool = False,
    output_format: str = "terminal",
    report_path: Path | None = None,
    env_file: Path | None = None,
    remote_host: str | None = None,
    remote_path: str = DEFAULT_REMOTE_PATH,
    progress_enabled: bool | None = None,
) -> int:
    try:
        ctx = execute_ifg_smtp(
            mode=mode,
            dry_run=dry_run,
            assume_yes=assume_yes,
            use_local=use_local,
            output_format=output_format,
            report_path=report_path,
            env_file=env_file,
            remote_host=remote_host,
            remote_path=remote_path,
            progress_enabled=progress_enabled,
        )
    except RuntimeError as exc:
        print(f"\n❌ SMTP workflow failed: {exc}")
        return 1

    if ctx.state_machine.state != WorkflowState.SUCCESS:
        print(f"\n❌ SMTP workflow failed: {ctx.transaction.outcome}")
        for record in ctx.transaction.stages:
            if record.status == "fail":
                print(f"  Stage {record.id}: {record.message}")
        return 1

    state = _smtp_from_transaction(ctx.transaction)
    if output_format == "json":
        payload = {
            "schema": "ifg_smtp_report_v1",
            "workflow": ctx.transaction.to_dict(),
            "smtp": state.to_dict(),
        }
        print(json.dumps(payload, indent=2))
    elif output_format == "markdown":
        print(render_smtp_markdown(state, transaction=ctx.transaction))
    else:
        print(render_smtp_markdown(state, transaction=ctx.transaction))
        report_file = ctx.data.get("report_file")
        if report_file:
            try:
                rel = Path(report_file).relative_to(ROOT)
            except ValueError:
                rel = report_file
            print(f"\nReport: {rel}")

    return exit_code_for_smtp(state)
