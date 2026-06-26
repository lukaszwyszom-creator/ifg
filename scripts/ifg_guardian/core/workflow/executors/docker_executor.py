from __future__ import annotations

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
        script = (
            f'docker compose -f "{cfg.compose_file}" --env-file "{cfg.env_file}" '
            f"build {services}\n"
        )
        result = self._ssh.run_remote(script, label="docker_build")
        if result.ok:
            result.data["services"] = services.split()
            result.data["executor"] = "docker"
        result.intent = intent
        return result
