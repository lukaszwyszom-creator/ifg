from __future__ import annotations

from pathlib import Path

from ifg_guardian.core.workflow.executors.compose_executor import ComposeExecutor
from ifg_guardian.core.workflow.executors.context import DeployExecutorContext
from ifg_guardian.core.workflow.executors.docker_executor import DockerExecutor
from ifg_guardian.core.workflow.executors.http_executor import HTTPExecutor
from ifg_guardian.core.workflow.executors.local_executor import LocalExecutor
from ifg_guardian.core.workflow.executors.router import (
    DeployCommandKind,
    classify_deploy_command,
    shell_command_from_intent,
)
from ifg_guardian.core.workflow.executors.ssh_executor import SSHExecutor
from ifg_guardian.core.workflow.intents import (
    ActionIntent,
    FsExistsIntent,
    GitFetchIntent,
    GitRevParseIntent,
    GitStatusIntent,
    LocalExecIntent,
    NoOpIntent,
)
from ifg_guardian.core.workflow.mode import ExecutionMode
from ifg_guardian.core.workflow.results import IntentResult
from ifg_guardian.core.workflow.executors import filesystem_executor as fs_mod
from ifg_guardian.core.workflow.executors import git_executor as git_mod


class IntentExecutor:
    """Dispatch intent execution to specialized executors."""

    def __init__(
        self,
        *,
        root: Path,
        deploy_context: DeployExecutorContext | None = None,
    ) -> None:
        self.root = root
        self.deploy_context = deploy_context or DeployExecutorContext()
        self._git = git_mod.GitExecutor(root=root)
        self._fs = fs_mod.FilesystemExecutor(root=root)
        self._local = LocalExecutor(root=root)
        self._ssh = SSHExecutor(root=root, deploy_context=self.deploy_context)
        self._docker = DockerExecutor(root=root, deploy_context=self.deploy_context)
        self._compose = ComposeExecutor(root=root, deploy_context=self.deploy_context)
        self._http = HTTPExecutor(root=root, deploy_context=self.deploy_context)

    def execute(self, intent: ActionIntent, mode: ExecutionMode) -> IntentResult:
        if mode.simulates_mutations and intent.mutating:
            return IntentResult(
                intent=intent,
                ok=True,
                simulated=True,
                output=f"[dry-run] would: {intent.describe()}",
            )

        if isinstance(intent, NoOpIntent):
            return IntentResult(intent=intent, ok=True, output=intent.reason or "ok")

        if isinstance(intent, LocalExecIntent):
            return self._execute_local_exec(intent)

        if isinstance(intent, FsExistsIntent):
            return self._fs.execute_exists(intent)

        if isinstance(intent, GitRevParseIntent):
            return self._git.execute_rev_parse(intent)

        if isinstance(intent, GitFetchIntent):
            return self._git.execute_fetch(intent)

        if isinstance(intent, GitStatusIntent):
            return self._git.execute_status(intent)

        return IntentResult(intent=intent, ok=False, error=f"unknown intent: {intent.intent_type}")

    def _execute_local_exec(self, intent: LocalExecIntent) -> IntentResult:
        shell_cmd = shell_command_from_intent(intent.command)
        kind = classify_deploy_command(shell_cmd)

        if kind == DeployCommandKind.LOCAL_GIT:
            self.deploy_context.record(shell_cmd)
            local_result = self._local.execute(intent)
            if not local_result.ok:
                return local_result
            cfg = self.deploy_context.config()
            remote_script = (
                "git fetch origin\n"
                f"git checkout {cfg.branch}\n"
                f"git pull origin {cfg.branch}\n"
            )
            remote = self._ssh.run_remote(remote_script, label="git_pull_remote")
            remote.intent = intent
            if remote.ok:
                remote.data["local_sha"] = local_result.output
                remote.data["executor"] = "ssh"
            return remote

        if kind == DeployCommandKind.LOCAL_NPM:
            npm_intent = LocalExecIntent(
                command=["npm", "run", "build"],
                cwd="frontend-react",
                mutating=True,
            )
            self.deploy_context.record("cd frontend-react && npm run build")
            return self._local.execute(npm_intent)

        if kind == DeployCommandKind.RSYNC:
            return self._ssh.execute_rsync(intent, shell_cmd)

        if kind == DeployCommandKind.DOCKER_BUILD:
            return self._docker.execute_build(intent, shell_cmd)

        if kind == DeployCommandKind.COMPOSE_UP:
            return self._compose.execute_up(intent, shell_cmd)

        if kind == DeployCommandKind.COMPOSE_LOGS:
            return self._compose.execute_logs(intent, shell_cmd)

        if kind == DeployCommandKind.ALEMBIC:
            backup = self._ssh.run_backup_before_migration()
            if not backup.ok:
                backup.intent = intent
                return backup
            cfg = self.deploy_context.config()
            script = (
                f'docker compose -f "{cfg.compose_file}" --env-file "{cfg.env_file}" '
                f"exec -T api alembic upgrade head\n"
            )
            result = self._ssh.run_remote(script, label="alembic_upgrade")
            result.intent = intent
            if result.ok:
                result.data["backup"] = backup.output
                result.data["executor"] = "ssh"
            return result

        if kind == DeployCommandKind.HTTP_CHECK:
            return self._http.execute_check(intent, shell_cmd)

        self.deploy_context.record(shell_cmd)
        return self._local.execute(intent)


__all__ = [
    "IntentExecutor",
    "LocalExecutor",
    "DeployExecutorContext",
    "SSHExecutor",
    "DockerExecutor",
    "ComposeExecutor",
    "HTTPExecutor",
]
