from __future__ import annotations

import re

from ifg_guardian.core.deploy_config import DS723Config
from ifg_guardian.core.frontend_artifacts import remote_artifact_verify_script, remote_frontend_build_script

ENV_FILE = ".env.production"
OLD_PROJECT = "docker"
POSTGRES_DB = "ksef_backend"
LEGACY_CONTAINERS = ("docker-api-1", "docker-worker-1", "docker-db-1")


def compose_base(cfg: DS723Config) -> str:
    return f'docker compose -f "{cfg.compose_file}" --env-file {ENV_FILE}'


def compose_old(cfg: DS723Config) -> str:
    return f'docker compose -p {OLD_PROJECT} -f "{cfg.compose_file}" --env-file {ENV_FILE}'


def backup_script(cfg: DS723Config) -> str:
    old = compose_old(cfg)
    return (
        "mkdir -p backups\n"
        "git rev-parse HEAD | tee backups/pre_cutover_commit.txt\n"
        f'db_running=$(docker inspect -f "{{{{.State.Running}}}}" {LEGACY_CONTAINERS[2]} 2>/dev/null || echo false)\n'
        'if [ "$db_running" != "true" ]; then\n'
        f"  {old} up -d db\n"
        "  for i in $(seq 1 30); do\n"
        f'    {old} exec db pg_isready -U postgres -d {POSTGRES_DB} && break\n'
        "    sleep 2\n"
        "  done\n"
        "fi\n"
        'stamp=$(date +%Y%m%d_%H%M)\n'
        f'backup="backups/pre_ifg_project_${{stamp}}.sql"\n'
        f"{old} exec -T db pg_dump -U postgres {POSTGRES_DB} > \"$backup\"\n"
        'test -s "$backup"\n'
        'echo "backup_file=$backup"\n'
        'if [ "$db_running" != "true" ]; then\n'
        f"  {old} stop db\n"
        "fi\n"
    )


def git_pull_script(cfg: DS723Config) -> str:
    return (
        f"git fetch origin {cfg.branch}\n"
        f"git checkout {cfg.branch}\n"
        f"git pull origin {cfg.branch}\n"
        "git log -1 --oneline\n"
    )


def compose_config_gate_script(cfg: DS723Config) -> str:
    return f"{compose_base(cfg)} config 2>/dev/null\n"


def validate_compose_config(text: str) -> tuple[bool, str]:
    if not re.search(r"^name:\s*ifg\s*$", text, re.MULTILINE):
        return False, "missing name: ifg"
    if "docker_postgres_data" not in text:
        return False, "docker_postgres_data not in config"
    if "ifg_postgres_data" in text:
        return False, "dangerous ifg_postgres_data in config"
    if "docker_ifg_prod" not in text:
        return False, "docker_ifg_prod not in config"
    if text.count("external: true") < 2:
        return False, "expected external: true on volume and network"
    return True, "compose config gate PASS"


def legacy_containers_script() -> str:
    names = " ".join(LEGACY_CONTAINERS)
    return (
        f"docker ps -a --filter name=docker- --format '{{{{.Names}}}}\\t{{{{.Status}}}}'\n"
        f"for c in {names}; do\n"
        '  docker inspect -f "{{.Name}} {{.State.Status}}" "$c" 2>/dev/null || echo "$c missing"\n'
        "done\n"
    )


def parse_legacy_containers(output: str) -> tuple[bool, str]:
    running = []
    for line in output.splitlines():
        if "Running" in line or line.endswith("\tUp"):
            running.append(line.strip())
    if running:
        return False, f"legacy containers still running: {running}"
    return True, "legacy docker-* Exited (rollback asset preserved)"


def cutover_up_script(cfg: DS723Config) -> str:
    return (
        remote_artifact_verify_script(cfg.repo)
        + f"{compose_base(cfg)} up -d\n"
    )


def frontend_build_script(cfg: DS723Config) -> str:
    return remote_frontend_build_script(cfg.repo)


def post_health_script(cfg: DS723Config) -> str:
    base = compose_base(cfg)
    return (
        f"{base} ps\n"
        "curl -fsS http://127.0.0.1:8000/health\n"
        f"{base} exec db pg_isready -U postgres -d {POSTGRES_DB}\n"
        f'{base} exec db psql -U postgres -d {POSTGRES_DB} -t -c "SELECT COUNT(*) FROM invoices;"\n'
        "docker volume inspect docker_postgres_data --format '{{.Name}}'\n"
        f"{base} logs worker --tail=30\n"
        "docker ps --filter name=ifg- --format 'table {{.Names}}\\t{{.Status}}'\n"
    )


def cleanup_script() -> str:
    return "docker rm docker-api-1 docker-worker-1 docker-db-1\n"


def rollback_script(cfg: DS723Config) -> str:
    base = compose_base(cfg)
    old = compose_old(cfg)
    return (
        f"{base} stop || true\n"
        'commit=$(cat backups/pre_cutover_commit.txt 2>/dev/null || git rev-parse HEAD)\n'
        'git checkout "$commit" -- docker/docker-compose.prod.yml || true\n'
        f"{old} up -d\n"
        "curl -fsS http://127.0.0.1:8000/health || true\n"
    )


def rollback_command_text(cfg: DS723Config) -> str:
    return (
        f"ssh {cfg.ssh_target} 'cd {cfg.repo} && "
        f"{compose_base(cfg)} stop && "
        'git checkout $(cat backups/pre_cutover_commit.txt) -- docker/docker-compose.prod.yml && '
        f"{compose_old(cfg)} up -d'"
    )
