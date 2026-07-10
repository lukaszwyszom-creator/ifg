from __future__ import annotations

# Canonical deploy/recovery phases (GWO).
DEPLOY_PHASES: tuple[str, ...] = (
    "repo_status",
    "tests",
    "commit",
    "push",
    "remote_pull",
    "remote_build",
    "restart_services",
    "health_check",
    "post_deploy_verification",
    "report_write",
)

LONG_WORKFLOW_IDS: frozenset[str] = frozenset(
    {
        "ifg.deploy.run",
        "ifg.container.cutover",
        "ifg.release.evaluate",
        "ifg.release.plan",
        "ifg.doctor",
    }
)

_STAGE_PHASE_MAP: dict[str, str] = {
    "init": "repo_status",
    "dependency": "repo_status",
    "release_plan": "repo_status",
    "release_evaluate": "tests",
    "doctor_dependency": "repo_status",
    "blocker": "repo_status",
    "build_pipeline": "repo_status",
    "preflight": "repo_status",
    "summary": "report_write",
    "simulate_execution": "remote_build",
}

_CUTOVER_STAGE_PHASE_MAP: dict[str, str] = {
    "init": "repo_status",
    "preflight": "repo_status",
    "backup": "push",
    "compose_down_legacy": "restart_services",
    "compose_up_ifg": "restart_services",
    "health_check": "health_check",
    "functional_gate": "post_deploy_verification",
    "cleanup": "post_deploy_verification",
    "summary": "report_write",
}

_DEPLOY_ACTION_PHASE_MAP: dict[str, str] = {
    "git pull": "remote_pull",
    "frontend build": "remote_build",
    "artifact verify local": "remote_build",
    "dist sync": "push",
    "artifact verify": "remote_build",
    "docker build": "remote_build",
    "alembic upgrade": "remote_build",
    "compose up": "restart_services",
    "health check": "health_check",
    "log verification": "post_deploy_verification",
}

_COMMAND_KIND_PHASE_MAP: dict[str, str] = {
    "local_git": "remote_pull",
    "local_npm": "remote_build",
    "rsync": "push",
    "artifact_gate_local": "remote_build",
    "artifact_gate_remote": "remote_build",
    "docker_build": "remote_build",
    "alembic": "remote_build",
    "compose_up": "restart_services",
    "compose_logs": "post_deploy_verification",
    "http_check": "health_check",
}


def default_progress_enabled(workflow_type: str, *, explicit: bool | None) -> bool:
    if explicit is not None:
        return explicit
    return workflow_type in LONG_WORKFLOW_IDS


def phase_for_workflow_stage(workflow_type: str, stage_id: str) -> str:
    if workflow_type == "ifg.container.cutover":
        return _CUTOVER_STAGE_PHASE_MAP.get(stage_id, stage_id)
    return _STAGE_PHASE_MAP.get(stage_id, stage_id)


def phase_for_deploy_action(action: str) -> str:
    return _DEPLOY_ACTION_PHASE_MAP.get(action, "remote_build")


def phase_for_shell_command(shell_cmd: str) -> str:
    normalized = shell_cmd.strip()
    if "pytest" in normalized:
        return "tests"
    if normalized.startswith("git commit") or " git commit " in normalized:
        return "commit"
    if normalized.startswith("git push") or " git push " in normalized:
        return "push"
    if (
        normalized.startswith("git status")
        or "git rev-parse" in normalized
        or normalized.startswith("git fetch")
    ):
        return "repo_status"
    from ifg_guardian.core.workflow.executors.router import classify_deploy_command

    kind = classify_deploy_command(shell_cmd)
    return _COMMAND_KIND_PHASE_MAP.get(kind.value, "remote_build")


def deploy_phase_index(phase: str) -> int:
    try:
        return DEPLOY_PHASES.index(phase) + 1
    except ValueError:
        return 0
