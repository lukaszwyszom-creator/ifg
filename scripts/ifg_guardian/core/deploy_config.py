from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ifg_guardian.config import (
    COMPOSE_FILE,
    DEFAULT_REMOTE_HOST,
    DEFAULT_REMOTE_PATH,
    ROOT,
    TARGET_BRANCH,
)

DS723_ENV_FILE = ROOT / "scripts" / "ds723.env"


@dataclass(frozen=True)
class DS723Config:
    host: str
    user: str
    port: int
    repo: str
    compose_file: str
    env_file: str
    docker_path: str
    remote_rsync_path: str
    branch: str

    @property
    def ssh_target(self) -> str:
        if self.user:
            return f"{self.user}@{self.host}"
        return self.host

    @classmethod
    def from_context(
        cls,
        *,
        remote_host: str | None = None,
        remote_path: str | None = None,
    ) -> DS723Config:
        values = _load_ds723_env()
        host = remote_host or values.get("DS723_HOST", DEFAULT_REMOTE_HOST)
        repo = remote_path or values.get("DS723_REPO", DEFAULT_REMOTE_PATH)
        return cls(
            host=host,
            user=values.get("DS723_USER", ""),
            port=int(values.get("DS723_PORT", "22")),
            repo=repo,
            compose_file=values.get("DS723_COMPOSE_FILE", COMPOSE_FILE),
            env_file=values.get("DS723_ENV_FILE", f"{repo}/.env.production"),
            docker_path=values.get(
                "DS723_DOCKER_PATH",
                "/var/packages/ContainerManager/target/usr/bin",
            ),
            remote_rsync_path=values.get("DS723_REMOTE_RSYNC_PATH", ""),
            branch=values.get("DS723_DEPLOY_BRANCH", TARGET_BRANCH),
        )

    def remote_preamble(self) -> str:
        return (
            f"set -euo pipefail\n"
            f'export PATH="{self.docker_path}:$PATH"\n'
            f'cd "{self.repo}"\n'
        )


def _load_ds723_env() -> dict[str, str]:
    if not DS723_ENV_FILE.is_file():
        return {}
    values: dict[str, str] = {}
    for line in DS723_ENV_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values
