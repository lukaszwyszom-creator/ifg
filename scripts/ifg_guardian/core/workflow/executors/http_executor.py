from __future__ import annotations

import subprocess
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from ifg_guardian.core.workflow.executors.context import DeployExecutorContext
from ifg_guardian.core.workflow.executors.ssh_executor import SSHExecutor
from ifg_guardian.core.workflow.intents import LocalExecIntent
from ifg_guardian.core.workflow.results import IntentResult


class HTTPExecutor:
    """Verify HTTP health endpoints (local curl or remote via SSH)."""

    def __init__(self, *, root: Path, deploy_context: DeployExecutorContext | None = None) -> None:
        self.root = root
        self._ssh = SSHExecutor(root=root, deploy_context=deploy_context)

    def execute_check(self, intent: LocalExecIntent, shell_cmd: str) -> IntentResult:
        url = "http://127.0.0.1:8000/health"
        if "http" in shell_cmd:
            parts = shell_cmd.split()
            for part in parts:
                if part.startswith("http"):
                    url = part
                    break

        cfg = self._ssh.deploy_context.config()
        remote_cmd = f'curl -fsS "{url}"'
        self._ssh.deploy_context.record(remote_cmd)
        ssh_result = self._ssh.run_remote(f'{remote_cmd}\n', label="http_health")
        if ssh_result.ok:
            ssh_result.intent = intent
            ssh_result.data["url"] = url
            ssh_result.data["executor"] = "http"
            return ssh_result

        try:
            with urlopen(url, timeout=10) as response:
                body = response.read().decode("utf-8", errors="replace").strip()
        except (URLError, OSError) as exc:
            return IntentResult(intent=intent, ok=False, error=str(exc), data={"url": url})

        return IntentResult(
            intent=intent,
            ok=True,
            output=body,
            data={"url": url, "executor": "http", "host": cfg.host},
        )

    def execute_local_curl(self, intent: LocalExecIntent, shell_cmd: str) -> IntentResult:
        self._ssh.deploy_context.record(shell_cmd)
        try:
            result = subprocess.run(
                ["/bin/sh", "-c", shell_cmd],
                cwd=self.root,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            return IntentResult(intent=intent, ok=False, error=str(exc))

        output = (result.stdout or result.stderr or "").strip()
        if result.returncode != 0:
            return IntentResult(intent=intent, ok=False, output=output, error=f"curl exit {result.returncode}")
        return IntentResult(intent=intent, ok=True, output=output, data={"executor": "http"})
