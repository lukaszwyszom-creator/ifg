from __future__ import annotations

import re
from enum import Enum


class DeployCommandKind(str, Enum):
    LOCAL = "local"
    LOCAL_GIT = "local_git"
    LOCAL_NPM = "local_npm"
    RSYNC = "rsync"
    DOCKER_BUILD = "docker_build"
    COMPOSE_UP = "compose_up"
    COMPOSE_LOGS = "compose_logs"
    ALEMBIC = "alembic"
    HTTP_CHECK = "http_check"


def shell_command_from_intent(command: list[str]) -> str:
    if len(command) >= 3 and command[0] == "/bin/sh" and command[1] == "-c":
        return command[2]
    return " ".join(command)


def classify_deploy_command(shell_cmd: str) -> DeployCommandKind:
    normalized = shell_cmd.strip()
    if normalized.startswith("git pull"):
        return DeployCommandKind.LOCAL_GIT
    if "npm run build" in normalized:
        return DeployCommandKind.LOCAL_NPM
    if normalized.startswith("rsync"):
        return DeployCommandKind.RSYNC
    if re.search(r"docker compose .* build", normalized):
        return DeployCommandKind.DOCKER_BUILD
    if re.search(r"docker compose .* up", normalized):
        return DeployCommandKind.COMPOSE_UP
    if re.search(r"docker compose .* logs", normalized):
        return DeployCommandKind.COMPOSE_LOGS
    if "alembic upgrade" in normalized:
        return DeployCommandKind.ALEMBIC
    if normalized.startswith("curl"):
        return DeployCommandKind.HTTP_CHECK
    return DeployCommandKind.LOCAL
