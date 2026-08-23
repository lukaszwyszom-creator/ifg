"""Skrypty zdalne dla workflow SMTP na DS723+."""
from __future__ import annotations

from ifg_guardian.core.deploy_config import DS723Config


def ssh_probe_script() -> str:
    return "echo connected\n"


def env_file_read_script(cfg: DS723Config) -> str:
    return (
        f'if test -f "{cfg.env_file}"; then\n'
        f'  cat "{cfg.env_file}"\n'
        "else\n"
        f'  echo "GUARDIAN_ENV_MISSING:{cfg.env_file}" >&2\n'
        "  exit 2\n"
        "fi\n"
    )
