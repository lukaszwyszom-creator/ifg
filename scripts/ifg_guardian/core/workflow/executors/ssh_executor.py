from __future__ import annotations

import subprocess
from pathlib import Path

from ifg_guardian.core.workflow.executors.context import DeployExecutorContext
from ifg_guardian.core.workflow.intents import LocalExecIntent
from ifg_guardian.core.workflow.results import IntentResult


class SSHExecutor:
    """Run commands on DS723+ via SSH."""

    def __init__(self, *, root: Path, deploy_context: DeployExecutorContext | None = None) -> None:
        self.root = root
        self.deploy_context = deploy_context or DeployExecutorContext()

    def run_remote(self, script_body: str, *, label: str = "ssh") -> IntentResult:
        cfg = self.deploy_context.config()
        full_script = cfg.remote_preamble() + script_body
        command = ["ssh", "-p", str(cfg.port), cfg.ssh_target, "bash", "-s"]
        self.deploy_context.record(f"{label}: ssh {cfg.ssh_target}")

        try:
            result = subprocess.run(
                command,
                input=full_script,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            return IntentResult(
                intent=LocalExecIntent(command=command, mutating=True),
                ok=False,
                error=str(exc),
                data={"exit_code": None, "stdout": "", "stderr": str(exc), "host": cfg.ssh_target},
            )

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        output = (stdout or stderr or "").strip()
        if result.returncode != 0:
            return IntentResult(
                intent=LocalExecIntent(command=command, mutating=True),
                ok=False,
                output=output,
                error=f"ssh exit {result.returncode}",
                data={
                    "exit_code": result.returncode,
                    "stdout": stdout,
                    "stderr": stderr,
                    "host": cfg.ssh_target,
                    "label": label,
                },
            )
        return IntentResult(
            intent=LocalExecIntent(command=command, mutating=True),
            ok=True,
            output=output,
            data={
                "host": cfg.ssh_target,
                "label": label,
                "exit_code": result.returncode,
                "stdout": stdout,
                "stderr": stderr,
            },
        )

    def execute_rsync(self, intent: LocalExecIntent, shell_cmd: str) -> IntentResult:
        self.deploy_context.record(shell_cmd)
        try:
            result = subprocess.run(
                ["/bin/sh", "-c", shell_cmd],
                cwd=self.root,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            return IntentResult(
                intent=intent,
                ok=False,
                error=str(exc),
                data={"exit_code": None, "stdout": "", "stderr": str(exc)},
            )

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        output = (stdout or stderr or "").strip()
        if result.returncode != 0:
            return IntentResult(
                intent=intent,
                ok=False,
                output=output,
                error=f"rsync exit {result.returncode}",
                data={"exit_code": result.returncode, "stdout": stdout, "stderr": stderr},
            )
        return IntentResult(
            intent=intent,
            ok=True,
            output=output or "rsync ok",
            data={"synced": True, "exit_code": result.returncode, "stdout": stdout, "stderr": stderr},
        )

    def capture_rollback_snapshot(self) -> dict[str, str]:
        cfg = self.deploy_context.config()
        commit = self.run_remote(
            f'git rev-parse --short HEAD\n',
            label="rollback_commit",
        )
        alembic = self.run_remote(
            f'docker compose -f "{cfg.compose_file}" --env-file "{cfg.env_file}" '
            f'exec -T api alembic current 2>/dev/null | head -1\n',
            label="rollback_alembic",
        )
        images = self.run_remote(
            "docker images --format '{{.Repository}}:{{.Tag}}' | grep -E 'ifg|api|worker' | head -5\n",
            label="rollback_images",
        )
        return {
            "commit_before": commit.output if commit.ok else "",
            "alembic_before": alembic.output if alembic.ok else "",
            "images_before": images.output if images.ok else "",
        }

    def run_backup_before_migration(self) -> IntentResult:
        cfg = self.deploy_context.config()
        script = (
            'mkdir -p backups\n'
            'stamp="$(date +%Y%m%d_%H%M%S)"\n'
            f'docker compose -f "{cfg.compose_file}" --env-file "{cfg.env_file}" '
            'exec -T db pg_dump -U postgres ifg '
            '> "backups/pre_migrate_${stamp}.sql"\n'
            'echo "backup=backups/pre_migrate_${stamp}.sql"\n'
        )
        return self.run_remote(script, label="db_backup")
