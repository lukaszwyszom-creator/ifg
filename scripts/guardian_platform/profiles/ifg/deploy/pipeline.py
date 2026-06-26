from __future__ import annotations

from guardian_platform.profiles.ifg.config.defaults import COMPOSE_FILE, TARGET_BRANCH


def build_deploy_pipeline(*, remote_host: str, remote_path: str) -> list[tuple[str, str, bool]]:
    """Return (action, command, mutating) steps for deploy run."""
    return [
        ("git validation", f"git fetch origin {TARGET_BRANCH} --quiet && git status --short", True),
        (
            "backup database",
            f"ssh {remote_host} 'cd {remote_path} && sudo docker compose -f {COMPOSE_FILE} exec -T db "
            f"pg_dump -U postgres ifg > backups/guardian_pre_deploy.sql'",
            True,
        ),
        ("alembic upgrade", f"ssh {remote_host} 'cd {remote_path} && alembic upgrade head'", True),
        ("frontend build", "cd frontend-react && npm run build", True),
        (
            "docker build",
            f"ssh {remote_host} 'cd {remote_path} && sudo docker compose -f {COMPOSE_FILE} build api worker'",
            True,
        ),
        (
            "container restart",
            f"ssh {remote_host} 'cd {remote_path} && sudo docker compose -f {COMPOSE_FILE} up -d api worker'",
            True,
        ),
        (
            "health verification",
            f"ssh {remote_host} 'curl -sS -m 10 http://127.0.0.1:8000/health'",
            False,
        ),
        (
            "smoke tests",
            f"ssh {remote_host} 'curl -sS -m 10 http://127.0.0.1:8000/openapi.json | head -c 200'",
            False,
        ),
    ]
