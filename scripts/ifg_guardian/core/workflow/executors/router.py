from __future__ import annotations

import re
from enum import Enum


class DeployCommandKind(str, Enum):
    LOCAL = "local"
    LOCAL_GIT = "local_git"
    LOCAL_NPM = "local_npm"
    RSYNC = "rsync"
    ARTIFACT_GATE_LOCAL = "artifact_gate_local"
    ARTIFACT_GATE_REMOTE = "artifact_gate_remote"
    DOCKER_BUILD = "docker_build"
    IMAGE_VERIFY = "image_verify"
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
    if "npm run build" in normalized or "npm ci" in normalized:
        return DeployCommandKind.LOCAL_NPM
    if normalized.startswith("rsync"):
        return DeployCommandKind.RSYNC
    if (
        "ifg_guardian_frontend_artifact_gate local" in normalized
        or "ifg_guardian_frontend_artifact_gate.py local" in normalized
    ):
        return DeployCommandKind.ARTIFACT_GATE_LOCAL
    if (
        "ifg_guardian_frontend_artifact_gate remote" in normalized
        or "ifg_guardian_frontend_artifact_gate.py remote" in normalized
    ):
        return DeployCommandKind.ARTIFACT_GATE_REMOTE
    if re.search(r"docker compose .* build", normalized):
        return DeployCommandKind.DOCKER_BUILD
    if (
        "ifg_guardian_image_verify" in normalized
        or normalized.startswith("image verify")
        or "docker image inspect ifg-api" in normalized
    ):
        return DeployCommandKind.IMAGE_VERIFY
    if re.search(r"docker compose .* up", normalized):
        return DeployCommandKind.COMPOSE_UP
    if re.search(r"docker compose .* logs", normalized):
        return DeployCommandKind.COMPOSE_LOGS
    if "alembic upgrade" in normalized:
        return DeployCommandKind.ALEMBIC
    if normalized.startswith("curl"):
        return DeployCommandKind.HTTP_CHECK
    return DeployCommandKind.LOCAL
