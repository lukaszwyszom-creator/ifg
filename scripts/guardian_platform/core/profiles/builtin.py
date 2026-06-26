from __future__ import annotations

from guardian_platform.core.environment.detect import detect_environment
from guardian_platform.core.git.client import (
    GitError,
    current_branch,
    git_available,
    is_dirty,
    short_sha,
    status_porcelain,
)
from guardian_platform.core.profiles.base import GuardianProfile
from guardian_platform.core.registry.commands import CommandSpec
from guardian_platform.core.registry.profiles import ProfileRegistrationContext
from guardian_platform.core.registry.workflows import WorkflowDefinition
from guardian_platform.core.reporting.writers import render_report
from guardian_platform.core.runtime.context import CommandContext
from guardian_platform.core.runtime.guards import MutatingCommandBlocked
from guardian_platform.core.runtime.mode import ExecutionMode
from guardian_platform.core.workflow.engine import ExecutionEngine
from guardian_platform.core.repository.commands import (
    run_repo_dead_code,
    run_repo_dependencies,
    run_repo_explain,
    run_repo_graph,
    run_repo_impact,
    run_repo_orphan,
)
from guardian_platform.core.workflow.workflows.ping import build_core_ping_workflow


def _cmd_plugin_list(ctx: CommandContext) -> int:
    profiles = ctx.extra.get("profile_list", [])
    lines = ["Guardian Platform — Profiles", "=" * 40]
    for info in profiles:
        lines.append(f"{info.profile_id}")
        lines.append(f"  version: {info.version}")
        if info.description:
            lines.append(f"  description: {info.description}")
    print("\n".join(lines))
    return 0


def _cmd_platform_doctor(ctx: CommandContext) -> int:
    env = detect_environment(ctx.root)
    checks: list[str] = []
    status = "OK"

    checks.append(f"python: {env.python_version}")
    checks.append(f"hostname: {env.hostname}")
    checks.append(f"cwd: {env.cwd}")

    if git_available(ctx.root):
        checks.append(f"git: available (branch={current_branch(ctx.root)})")
        if is_dirty(ctx.root):
            checks.append("git: working tree dirty (warn)")
            status = "DEGRADED"
    else:
        checks.append("git: not available or not a repository")
        status = "DEGRADED"

    active = ctx.config.active_profiles
    checks.append(f"active profiles: {', '.join(active)}")

    payload = {
        "title": "Guardian Platform Doctor",
        "sections": {"status": status, "checks": checks},
    }
    print(render_report(payload, ctx.output_format))
    return 0 if status == "OK" else 1


def _cmd_repo_status(ctx: CommandContext) -> int:
    if not git_available(ctx.root):
        print("Not a git repository.")
        return 1
    branch = current_branch(ctx.root)
    sha = short_sha(ctx.root)
    dirty = is_dirty(ctx.root)
    payload = {
        "title": "Repository Status",
        "sections": {
            "branch": branch,
            "commit": sha,
            "dirty": dirty,
        },
    }
    print(render_report(payload, ctx.output_format))
    return 0


def _cmd_repo_audit(ctx: CommandContext) -> int:
    if not git_available(ctx.root):
        print("Not a git repository.")
        return 1
    porcelain = status_porcelain(ctx.root)
    lines = [line for line in porcelain.splitlines() if line.strip()]
    payload = {
        "title": "Repository Audit (generic)",
        "sections": {
            "modified_files": len(lines),
            "sample": lines[:10],
            "note": "Domain-specific audit rules belong to project profiles (not yet loaded).",
        },
    }
    print(render_report(payload, ctx.output_format))
    return 0


def _cmd_workflow_list(ctx: CommandContext) -> int:
    ids = ctx.extra.get("workflow_ids", [])
    payload = {
        "title": "Registered Workflows",
        "sections": {"workflows": ids or ["(none)"]},
    }
    print(render_report(payload, ctx.output_format))
    return 0


def _cmd_workflow_run(ctx: CommandContext) -> int:
    workflow_id = str(ctx.extra.get("workflow_id", ""))
    registry = ctx.extra.get("workflow_registry")
    if registry is None:
        print("Workflow registry unavailable.")
        return 1
    workflow = registry.get(workflow_id)
    if workflow is None:
        print(f"Unknown workflow: {workflow_id}")
        return 1

    if workflow.mutating or workflow.requires_yes:
        spec = CommandSpec(profile="core", path=("workflow", "run"), handler=_cmd_workflow_run, mutating=True)
        try:
            from guardian_platform.core.runtime.guards import ensure_mutating_allowed

            ensure_mutating_allowed(spec=spec, assume_yes=ctx.assume_yes, dry_run=ctx.dry_run)
        except MutatingCommandBlocked as exc:
            print(str(exc))
            return 2

    engine = ExecutionEngine(root=ctx.root)
    result_ctx = engine.run(workflow, mode=ctx.execution_mode)
    payload = {
        "title": f"Workflow {workflow_id}",
        "sections": {
            "outcome": result_ctx.transaction.outcome,
            "duration_ms": result_ctx.transaction.duration_ms,
            "warnings": result_ctx.transaction.warnings,
        },
    }
    print(render_report(payload, ctx.output_format))
    return 0 if result_ctx.transaction.outcome == "SUCCESS" else 1


def _cmd_platform_mutate_test(ctx: CommandContext) -> int:
    if ctx.dry_run:
        print("[dry-run] would perform mutating platform self-test")
        return 0
    print("mutating platform self-test executed")
    return 0


class CoreProfile(GuardianProfile):
    @property
    def id(self) -> str:
        return "core"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def description(self) -> str:
        return "Neutral Guardian Platform core"

    def register(self, ctx: ProfileRegistrationContext) -> None:
        ctx.workflows.register(build_core_ping_workflow())

        commands = [
            CommandSpec("core", ("plugin", "list"), _cmd_plugin_list, help="List loaded profiles"),
            CommandSpec("core", ("platform", "doctor"), _cmd_platform_doctor, help="Platform health checks"),
            CommandSpec("core", ("platform", "mutate-test"), _cmd_platform_mutate_test, help="Mutating self-test", mutating=True, supports_dry_run=True),
            CommandSpec("core", ("repo", "status"), _cmd_repo_status, help="Git repository status"),
            CommandSpec("core", ("repo", "audit"), _cmd_repo_audit, help="Generic repository audit"),
            CommandSpec("core", ("repo", "graph"), run_repo_graph, help="Build repository dependency graphs"),
            CommandSpec("core", ("repo", "dependencies"), run_repo_dependencies, help="List module import dependencies"),
            CommandSpec("core", ("repo", "orphan"), run_repo_orphan, help="List orphaned modules and scripts"),
            CommandSpec("core", ("repo", "dead-code"), run_repo_dead_code, help="List safe dead-code candidates"),
            CommandSpec("core", ("repo", "impact"), run_repo_impact, help="Show impact for a path"),
            CommandSpec("core", ("repo", "explain"), run_repo_explain, help="Explain dependency metrics for a path"),
            CommandSpec("core", ("workflow", "list"), _cmd_workflow_list, help="List registered workflows"),
            CommandSpec("core", ("workflow", "run"), _cmd_workflow_run, help="Run a workflow by id"),
        ]
        for spec in commands:
            ctx.commands.register(spec)
