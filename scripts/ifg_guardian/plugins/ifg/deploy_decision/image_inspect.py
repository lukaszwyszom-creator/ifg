"""Odczyt labeli wdrożonego obrazu ifg-api na DS723+."""
from __future__ import annotations

import json
import shlex
from dataclasses import dataclass

from ifg_guardian.config import ROOT
from ifg_guardian.core.workflow.executors.context import DeployExecutorContext
from ifg_guardian.core.workflow.executors.ssh_executor import SSHExecutor


IMAGE_NAME = "ifg-api:latest"
LABEL_GIT_COMMIT = "ifg.git.commit"
LABEL_OCI_REVISION = "org.opencontainers.image.revision"


@dataclass(frozen=True)
class DeployedImageInfo:
    inspect_ok: bool
    image_id: str | None
    git_commit: str | None
    raw_error: str | None = None


def parse_image_inspect_payload(payload: str) -> DeployedImageInfo:
    text = (payload or "").strip()
    if not text or text == "{}":
        return DeployedImageInfo(
            inspect_ok=False,
            image_id=None,
            git_commit=None,
            raw_error="image missing or empty inspect",
        )
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return DeployedImageInfo(
            inspect_ok=False,
            image_id=None,
            git_commit=None,
            raw_error=f"invalid json: {exc}",
        )
    if isinstance(data, list):
        if not data:
            return DeployedImageInfo(
                inspect_ok=False,
                image_id=None,
                git_commit=None,
                raw_error="image not found",
            )
        data = data[0]
    if not isinstance(data, dict):
        return DeployedImageInfo(
            inspect_ok=False,
            image_id=None,
            git_commit=None,
            raw_error="unexpected inspect shape",
        )
    image_id = data.get("Id") or data.get("id")
    labels = data.get("Config", {}).get("Labels") if isinstance(data.get("Config"), dict) else None
    if labels is None:
        labels = data.get("Labels") or {}
    if not isinstance(labels, dict):
        labels = {}
    git_commit = (
        labels.get(LABEL_GIT_COMMIT)
        or labels.get(LABEL_OCI_REVISION)
        or labels.get("IFG_GIT_COMMIT")
    )
    return DeployedImageInfo(
        inspect_ok=True,
        image_id=str(image_id) if image_id else None,
        git_commit=str(git_commit).strip() if git_commit else None,
    )


def inspect_deployed_api_image(
    *,
    remote_host: str | None = None,
    remote_path: str | None = None,
    image: str = IMAGE_NAME,
) -> DeployedImageInfo:
    """SSH: docker image inspect ifg-api:latest → Id + git labels."""
    ctx = DeployExecutorContext(remote_host=remote_host, remote_path=remote_path)
    ssh = SSHExecutor(root=ROOT, deploy_context=ctx)
    script = (
        f"docker image inspect {shlex.quote(image)} "
        f"--format '{{{{json .}}}}' 2>/dev/null || echo '{{}}'"
    )
    result = ssh.run_remote(script, label="image_inspect")
    if not result.ok:
        return DeployedImageInfo(
            inspect_ok=False,
            image_id=None,
            git_commit=None,
            raw_error=str(result.data.get("stderr") or result.error or result.output or "ssh inspect failed"),
        )
    return parse_image_inspect_payload(str(result.data.get("stdout") or result.output or ""))
