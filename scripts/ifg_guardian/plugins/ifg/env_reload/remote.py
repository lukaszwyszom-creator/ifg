"""Skrypty zdalne dla przeładowania środowiska IFG na DS723+."""
from __future__ import annotations

from ifg_guardian.core.deploy_config import DS723Config


def ssh_probe_script() -> str:
    return "echo connected\n"


def env_file_check_script(cfg: DS723Config) -> str:
    return (
        f'if test -f "{cfg.env_file}"; then\n'
        f'  echo "exists:{cfg.env_file}"\n'
        "else\n"
        f'  echo "missing:{cfg.env_file}"\n'
        "  exit 1\n"
        "fi\n"
    )


def compose_config_script(cfg: DS723Config) -> str:
    return (
        f'if test -f "{cfg.compose_file}"; then\n'
        f'  echo "compose:{cfg.compose_file}"\n'
        "else\n"
        f'  echo "missing:{cfg.compose_file}"\n'
        "  exit 1\n"
        "fi\n"
    )


def compose_reload_script(cfg: DS723Config) -> str:
    return (
        f'docker compose -f "{cfg.compose_file}" --env-file "{cfg.env_file}" '
        "up -d api worker\n"
    )


def compose_ps_script(cfg: DS723Config) -> str:
    return (
        f'docker compose -f "{cfg.compose_file}" --env-file "{cfg.env_file}" '
        "ps --format '{{.Service}}\t{{.State}}'\n"
    )


def health_probe_script(*, timeout_seconds: int = 10) -> str:
    return f"curl -sS -m {timeout_seconds} http://127.0.0.1:8000/health\n"


def startup_logs_script(cfg: DS723Config, *, tail: int = 30) -> str:
    return (
        f'docker compose -f "{cfg.compose_file}" --env-file "{cfg.env_file}" '
        f"logs --tail={tail} api worker\n"
    )
