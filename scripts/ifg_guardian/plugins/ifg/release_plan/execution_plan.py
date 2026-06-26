from __future__ import annotations

from ifg_guardian.plugins.ifg.release_plan.models import BuildDecision, ExecutionStep


def _decision_map(decisions: list[BuildDecision]) -> dict[str, BuildDecision]:
    return {d.name: d for d in decisions}


def build_execution_plan(decisions: list[BuildDecision]) -> list[ExecutionStep]:
    by_name = _decision_map(decisions)
    frontend = by_name.get("Frontend Build")
    backend = by_name.get("Backend Build")
    worker = by_name.get("Worker Build")
    migration = by_name.get("Migration Required")
    compose = by_name.get("Compose Restart")

    steps = [
        ExecutionStep(
            1,
            "git pull",
            "Synchronize DS723+ repository with origin/production",
            required=True,
        ),
    ]

    if frontend and frontend.required:
        steps.append(
            ExecutionStep(
                2,
                "frontend build",
                f"cd frontend-react && npm run build — {frontend.reason}",
                required=True,
            )
        )
    else:
        steps.append(
            ExecutionStep(
                2,
                "frontend build",
                "Skipped — dist aktualny",
                required=False,
            )
        )

    if backend and backend.required:
        steps.append(
            ExecutionStep(
                3,
                "docker build api",
                f"Rebuild API image — {backend.reason}",
                required=True,
            )
        )
    else:
        steps.append(
            ExecutionStep(
                3,
                "docker build api",
                "Skipped — brak zmian backend",
                required=False,
            )
        )

    if worker and worker.required:
        steps.append(
            ExecutionStep(
                4,
                "docker build worker",
                f"Rebuild worker image — {worker.reason}",
                required=True,
            )
        )
    else:
        steps.append(
            ExecutionStep(
                4,
                "docker build worker",
                "Skipped — brak zmian worker",
                required=False,
            )
        )

    if migration and migration.required:
        steps.append(
            ExecutionStep(
                5,
                "migration",
                f"alembic upgrade head — {migration.reason}",
                required=True,
            )
        )
    else:
        steps.append(
            ExecutionStep(
                5,
                "migration",
                "Skipped — schema at head",
                required=False,
            )
        )

    if compose and compose.required:
        steps.append(
            ExecutionStep(
                6,
                "restart",
                f"docker compose up -d — {compose.reason}",
                required=True,
            )
        )
    else:
        steps.append(
            ExecutionStep(
                6,
                "restart",
                "Rolling restart only if health check fails",
                required=False,
            )
        )

    steps.extend([
        ExecutionStep(
            7,
            "health",
            "Verify /health and container states on DS723+",
            required=True,
        ),
        ExecutionStep(
            8,
            "log verification",
            "Review api/worker logs for startup errors",
            required=True,
        ),
    ])

    return steps
