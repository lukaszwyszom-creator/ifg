from __future__ import annotations

from ifg_guardian.config import COMPOSE_FILE, DEFAULT_REMOTE_PATH, TARGET_BRANCH
from ifg_guardian.core.frontend_artifacts import (
    ARTIFACT_GATE_LOCAL_CMD,
    ARTIFACT_GATE_REMOTE_CMD,
    build_rsync_dist_command,
)
from ifg_guardian.plugins.ifg.deploy_run.models import DeployStep
from ifg_guardian.plugins.ifg.release_plan.models import DeploymentRisk, ReleasePlanState

# Steps that must pass before compose up is allowed.
_COMPOSE_BLOCKING_ACTIONS = frozenset({
    "frontend build",
    "artifact verify local",
    "dist sync",
    "artifact verify",
})


def _plan_step_map(plan: ReleasePlanState) -> dict[str, object]:
    return {step.action: step for step in plan.execution_plan}


def _decision_required(plan: ReleasePlanState, name: str) -> bool:
    for decision in plan.build_decisions:
        if decision.name == name:
            return decision.required
    return False


def build_deploy_pipeline(
    plan: ReleasePlanState,
    *,
    remote_path: str = DEFAULT_REMOTE_PATH,
    force_docker_rebuild: bool = False,
    docker_rebuild_reason: str | None = None,
    image_verify_required: bool = True,
) -> list[DeployStep]:
    """Build deployment pipeline from release plan execution plan."""
    steps_map = _plan_step_map(plan)
    pipeline: list[DeployStep] = []
    order = 1

    git_step = steps_map.get("git pull")
    pipeline.append(
        DeployStep(
            order=order,
            action="git pull",
            description=git_step.description if git_step else "Synchronize repository",
            reason="Always required before deploy",
            required=True,
            skipped=False,
            command=f"git pull origin {TARGET_BRANCH}",
        )
    )
    order += 1

    fe_step = steps_map.get("frontend build")
    pipeline.append(
        DeployStep(
            order=order,
            action="frontend build",
            description=fe_step.description if fe_step else "Build frontend",
            reason="Mandatory — dist is not in git; API bind-mount requires host artifacts",
            required=True,
            skipped=False,
            command="cd frontend-react && npm ci --prefer-offline --no-audit --no-fund && npm run build",
        )
    )
    order += 1

    pipeline.append(
        DeployStep(
            order=order,
            action="artifact verify local",
            description="Artifact Verification Gate (local dist before sync)",
            reason="index.html and assets/*.js must exist before rsync",
            required=True,
            skipped=False,
            command=ARTIFACT_GATE_LOCAL_CMD,
        )
    )
    order += 1

    pipeline.append(
        DeployStep(
            order=order,
            action="dist sync",
            description="Sync frontend-react/dist to DS723+",
            reason="Static assets must be on DS723+ before compose restart",
            required=True,
            skipped=False,
            command=build_rsync_dist_command(remote_path=remote_path),
        )
    )
    order += 1

    pipeline.append(
        DeployStep(
            order=order,
            action="artifact verify",
            description="Artifact Verification Gate (remote DS723+)",
            reason="index.html and assets/*.js must exist on host before compose up",
            required=True,
            skipped=False,
            command=ARTIFACT_GATE_REMOTE_CMD,
        )
    )
    order += 1

    api_step = steps_map.get("docker build api")
    worker_step = steps_map.get("docker build worker")
    docker_required = (
        force_docker_rebuild
        or (api_step.required if api_step else False)
        or (worker_step.required if worker_step else False)
        or _decision_required(plan, "Backend Build")
        or _decision_required(plan, "Worker Build")
    )
    if force_docker_rebuild and docker_rebuild_reason:
        docker_reason = docker_rebuild_reason
    else:
        docker_reason = (
            api_step.description if api_step and api_step.required
            else worker_step.description if worker_step and worker_step.required
            else "No image rebuild required"
        )
    pipeline.append(
        DeployStep(
            order=order,
            action="docker build",
            description="Build api and worker Docker images",
            reason=docker_reason,
            required=docker_required,
            skipped=not docker_required,
            command=f"docker compose -f {COMPOSE_FILE} build api worker",
        )
    )
    order += 1

    mig_step = steps_map.get("migration")
    mig_required = mig_step.required if mig_step else _decision_required(plan, "Migration Required")
    pipeline.append(
        DeployStep(
            order=order,
            action="alembic upgrade",
            description=mig_step.description if mig_step else "Database migration",
            reason=mig_step.description if mig_step else "from release plan",
            required=mig_required,
            skipped=not mig_required,
            command="alembic upgrade head",
        )
    )
    order += 1

    restart_step = steps_map.get("restart")
    compose_required = restart_step.required if restart_step else _decision_required(plan, "Compose Restart")
    if not compose_required:
        compose_required = True
    pipeline.append(
        DeployStep(
            order=order,
            action="compose up",
            description=restart_step.description if restart_step else "Restart compose stack",
            reason="Start api/worker after artifact gate GO (compose executor re-verifies)",
            required=compose_required,
            skipped=False,
            command=f"docker compose -f {COMPOSE_FILE} up -d",
        )
    )
    order += 1

    health_step = steps_map.get("health")
    pipeline.append(
        DeployStep(
            order=order,
            action="health check",
            description=health_step.description if health_step else "Verify /health endpoint",
            reason="Post-deploy verification",
            required=True,
            skipped=False,
            command="curl -sS http://127.0.0.1:8000/health",
        )
    )
    order += 1

    pipeline.append(
        DeployStep(
            order=order,
            action="image verify",
            description="Verify deployed ifg-api image Id + ifg.git.commit label",
            reason="Hard gate: image label must match remote HEAD after deploy",
            required=image_verify_required,
            skipped=not image_verify_required,
            command="ifg_guardian_image_verify",
        )
    )
    order += 1

    log_step = steps_map.get("log verification")
    pipeline.append(
        DeployStep(
            order=order,
            action="log verification",
            description=log_step.description if log_step else "Review service logs",
            reason="Detect startup errors after deploy",
            required=True,
            skipped=False,
            command=f"docker compose -f {COMPOSE_FILE} logs --tail=50 api worker",
        )
    )

    return pipeline


def detect_blockers(plan: ReleasePlanState) -> list[str]:
    blockers: list[str] = []
    if plan.doctor_overall_status == "BLOCKED":
        blockers.append(f"Doctor status is BLOCKED (workflow {plan.doctor_workflow_id})")
    elif plan.doctor_overall_status not in ("READY", "READY_WITH_WARNINGS"):
        blockers.append(f"Doctor status not deployable: {plan.doctor_overall_status}")
    if plan.deployment_risk == DeploymentRisk.CRITICAL:
        blockers.append(f"Deployment risk is CRITICAL: {'; '.join(plan.risk_rationale[:2])}")
    for item in plan.risk_rationale:
        if item.startswith("CRITICAL:"):
            blockers.append(item)
    return blockers


def compose_blocked_by_step_failure(action: str) -> bool:
    return action in _COMPOSE_BLOCKING_ACTIONS
