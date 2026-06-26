from __future__ import annotations

from pathlib import Path

from ifg_guardian.core.workflow.executors.context import DeployExecutorContext
from ifg_guardian.core.workflow.executors.ssh_executor import SSHExecutor
from ifg_guardian.core.workflow.intents import LocalExecIntent
from ifg_guardian.core.workflow.results import IntentResult


class ComposeExecutor:
    """Manage docker compose on the remote host via SSH."""

    def __init__(self, *, root: Path, deploy_context: DeployExecutorContext | None = None) -> None:
        self._ssh = SSHExecutor(root=root, deploy_context=deploy_context)

    def execute_up(self, intent: LocalExecIntent, shell_cmd: str) -> IntentResult:
        cfg = self._ssh.deploy_context.config()
        script = (
            f'docker compose -f "{cfg.compose_file}" --env-file "{cfg.env_file}" '
            f"up -d --remove-orphans api worker\n"
        )
        result = self._ssh.run_remote(script, label="compose_up")
        if result.ok:
            ps = self._ssh.run_remote(
                f'docker compose -f "{cfg.compose_file}" --env-file "{cfg.env_file}" ps\n',
                label="compose_ps",
            )
            result.data["containers"] = ps.output if ps.ok else ""
            result.data["executor"] = "compose"
        result.intent = intent
        return result

    def execute_logs(self, intent: LocalExecIntent, shell_cmd: str) -> IntentResult:
        cfg = self._ssh.deploy_context.config()
        script = (
            f'docker compose -f "{cfg.compose_file}" --env-file "{cfg.env_file}" '
            f"logs --tail=50 api worker\n"
        )
        result = self._ssh.run_remote(script, label="compose_logs")
        if result.ok:
            result.data["executor"] = "compose"
            result.data["services"] = ["api", "worker"]
        result.intent = intent
        return result
