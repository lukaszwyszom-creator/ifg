from __future__ import annotations

import shlex
from pathlib import Path

from ifg_guardian.core.workflow.executors.context import DeployExecutorContext
from ifg_guardian.core.workflow.executors.ssh_executor import SSHExecutor
from ifg_guardian.core.workflow.intents import LocalExecIntent
from ifg_guardian.core.workflow.results import IntentResult


class DockerExecutor:
    """Build Docker images on the remote host via SSH."""

    def __init__(self, *, root: Path, deploy_context: DeployExecutorContext | None = None) -> None:
        self._ssh = SSHExecutor(root=root, deploy_context=deploy_context)

    def execute_build(self, intent: LocalExecIntent, shell_cmd: str) -> IntentResult:
        cfg = self._ssh.deploy_context.config()
        services = "api worker"
        if " build " in shell_cmd:
            tail = shell_cmd.split(" build ", 1)[-1].strip()
            if tail:
                services = tail
        # Label ifg.git.commit z HEAD na hoście zdalnym (po git pull w pipeline).
        script = (
            "IFG_GIT_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo unknown)\n"
            f'docker compose -f "{cfg.compose_file}" --env-file "{cfg.env_file}" '
            f'build --build-arg IFG_GIT_COMMIT="$IFG_GIT_COMMIT" {services}\n'
        )
        result = self._ssh.run_remote(script, label="docker_build")
        if result.ok:
            result.data["services"] = services.split()
            result.data["executor"] = "docker"
        result.intent = intent
        return result

    def execute_image_verify(
        self,
        intent: LocalExecIntent,
        *,
        expected_revision: str | None = None,
        rebuild_was_required: bool = False,
        image: str = "ifg-api:latest",
    ) -> IntentResult:
        """Po deployu: Id obrazu + label ifg.git.commit muszą zgadzać się z HEAD na DS723+."""
        from ifg_guardian.plugins.ifg.deploy_decision.image_inspect import parse_image_inspect_payload
        from ifg_guardian.plugins.ifg.deploy_decision.image_rebuild_gate import (
            verify_deployed_image_matches_expected,
        )

        script = (
            "EXPECTED=$(git rev-parse HEAD 2>/dev/null || echo '')\n"
            "echo \"EXPECTED_REVISION=$EXPECTED\"\n"
            f"docker image inspect {shlex.quote(image)} "
            f"--format '{{{{json .}}}}' 2>/dev/null || echo '{{}}'\n"
        )
        result = self._ssh.run_remote(script, label="image_verify")
        result.intent = intent
        if not result.ok:
            result.error = result.error or "image verify ssh failed"
            return result

        stdout = str(result.data.get("stdout") or result.output or "")
        remote_expected = ""
        json_payload = stdout
        if "EXPECTED_REVISION=" in stdout:
            lines = stdout.splitlines()
            for i, line in enumerate(lines):
                if line.startswith("EXPECTED_REVISION="):
                    remote_expected = line.split("=", 1)[1].strip()
                    json_payload = "\n".join(lines[i + 1 :])
                    break

        expected = (expected_revision or remote_expected or "").strip()
        info = parse_image_inspect_payload(json_payload)
        ok, message = verify_deployed_image_matches_expected(
            expected_revision=expected,
            deployed_revision=info.git_commit if info.inspect_ok else None,
            rebuild_was_required=rebuild_was_required,
            image_id=info.image_id if info.inspect_ok else None,
        )
        result.data["image_id"] = info.image_id
        result.data["git_commit"] = info.git_commit
        result.data["expected_revision"] = expected
        result.data["image_verify_ok"] = ok
        result.output = message
        if not ok:
            result.ok = False
            result.error = message
        return result
