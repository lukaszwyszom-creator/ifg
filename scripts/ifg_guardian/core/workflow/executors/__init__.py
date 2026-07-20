from __future__ import annotations

from pathlib import Path

from ifg_guardian.core.progress.mapping import deploy_phase_index, phase_for_shell_command
from ifg_guardian.core.progress.tracker import ProgressTracker
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
        progress_tracker: ProgressTracker | None = None,
    ) -> None:
        self.root = root
        self.deploy_context = deploy_context or DeployExecutorContext()
        self._progress_tracker = progress_tracker
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
        tracker = self._progress_tracker
        phase = phase_for_shell_command(shell_cmd)
        step = deploy_phase_index(phase) or 0
        track_deploy_intent = tracker is not None and kind != DeployCommandKind.LOCAL

        if track_deploy_intent:
            tracker.note_action(shell_cmd)
            tracker.intent_started(
                phase=phase,
                step=step or None,
                message=shell_cmd,
            )

        result = self._dispatch_local_exec(intent, shell_cmd, kind)

        if track_deploy_intent:
            message = result.error or result.output or "ok"
            tracker.intent_finished(
                phase=phase,
                step=step or None,
                ok=result.ok,
                message=message,
            )
        return result

    def _dispatch_local_exec(
        self,
        intent: LocalExecIntent,
        shell_cmd: str,
        kind: DeployCommandKind,
    ) -> IntentResult:
        if kind == DeployCommandKind.LOCAL_GIT:
            self.deploy_context.record(shell_cmd)
            local_result = self._local.execute(intent)
            if not local_result.ok:
                return local_result
            cfg = self.deploy_context.config()
            remote_script = (
                "git fetch origin\n"
                f"git checkout {cfg.branch}\n"
                f"git reset --hard origin/{cfg.branch}\n"
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

        if kind == DeployCommandKind.ARTIFACT_GATE_LOCAL:
            from ifg_guardian.core.frontend_artifacts import verify_local_dist

            self.deploy_context.record(shell_cmd)
            gate = verify_local_dist(self.root)
            if gate.is_go:
                return IntentResult(
                    intent=intent,
                    ok=True,
                    output=gate.message,
                    data={"artifact_gate": gate.status, "js_count": gate.js_count},
                )
            return IntentResult(
                intent=intent,
                ok=False,
                output=gate.message,
                error=f"Artifact Verification Gate {gate.status}",
                data={"artifact_gate": gate.status},
            )

        if kind == DeployCommandKind.ARTIFACT_GATE_REMOTE:
            from ifg_guardian.core.frontend_artifacts import parse_artifact_gate_output, remote_artifact_verify_script

            cfg = self.deploy_context.config()
            self.deploy_context.record(shell_cmd)
            result = self._ssh.run_remote(remote_artifact_verify_script(cfg.repo), label="artifact_gate_remote")
            result.intent = intent
            gate = parse_artifact_gate_output(result.output)
            if result.ok and gate.is_go:
                result.data["artifact_gate"] = gate.status
                result.data["js_count"] = gate.js_count
                return result
            return IntentResult(
                intent=intent,
                ok=False,
                output=result.output or gate.message,
                error=gate.message or result.error or "Artifact Verification Gate NO_GO",
                data={"artifact_gate": "NO_GO"},
            )

        if kind == DeployCommandKind.DOCKER_BUILD:
            return self._docker.execute_build(intent, shell_cmd)

        if kind == DeployCommandKind.IMAGE_VERIFY:
            expected = None
            rebuild_required = False
            meta = getattr(intent, "meta", None) or {}
            if isinstance(meta, dict):
                expected = meta.get("expected_revision")
                rebuild_required = bool(meta.get("rebuild_was_required"))
            return self._docker.execute_image_verify(
                intent,
                expected_revision=expected,
                rebuild_was_required=rebuild_required,
            )

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
