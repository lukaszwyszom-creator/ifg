"""Porównanie revision Alembic: lokalny HEAD vs produkcja (DS723+)."""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field

from ifg_guardian.config import ROOT
from ifg_guardian.core.deploy_config import DS723Config
from ifg_guardian.core.workflow.executors.ssh_executor import SSHExecutor
from ifg_guardian.core.workflow.executors.context import DeployExecutorContext


@dataclass
class AlembicDeploySnapshot:
    local_head: str = ""
    local_current: str = ""
    local_current_available: bool = False
    remote_revision: str = ""
    remote_available: bool = False
    remote_error: str = ""
    pending_revisions: list[str] = field(default_factory=list)

    @property
    def migration_required(self) -> bool:
        if not self.local_head:
            return False
        if not self.remote_available:
            return False
        if not self.remote_revision:
            return True
        return self.remote_revision != self.local_head


def extract_revision(text: str) -> str:
    if not text:
        return ""
    match = re.search(r"\b([0-9a-z]{8,})\b", text, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    first = text.strip().split()
    return first[0] if first else ""


def _run_local(command: list[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return 1, str(exc)
    output = (result.stdout or result.stderr or "").strip()
    return result.returncode, output


def read_local_alembic_head() -> tuple[str, str]:
    code, output = _run_local(["alembic", "heads"])
    if code != 0:
        return "", output
    head = extract_revision(output.splitlines()[0] if output else "")
    return head, output


def read_local_alembic_current() -> tuple[str, str, bool]:
    code, output = _run_local(["alembic", "current"])
    if code != 0:
        return "", output, False
    return extract_revision(output), output, True


def read_remote_alembic_revision(
    *,
    remote_host: str | None,
    remote_path: str,
    dry_run: bool,
) -> tuple[str, str, bool]:
    if dry_run:
        return "", "skipped in dry-run", False
    cfg = DS723Config.from_context(remote_host=remote_host, remote_path=remote_path)
    executor = SSHExecutor(
        root=ROOT,
        deploy_context=DeployExecutorContext(remote_host=cfg.host, remote_path=cfg.repo),
    )
    script = (
        f'docker compose -f "{cfg.compose_file}" exec -T api '
        f'alembic current 2>/dev/null | head -1\n'
    )
    result = executor.run_remote(script, label="alembic_remote_current")
    if not result.ok:
        return "", result.error or result.output or "remote alembic unavailable", False
    revision = extract_revision(result.output or "")
    return revision, result.output or "", True


def pending_revisions_between(base: str, head: str) -> list[str]:
    if not base or not head or base == head:
        return []
    ini = ROOT / "alembic.ini"
    if not ini.is_file():
        return [head] if head != base else []
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        script = ScriptDirectory.from_config(Config(str(ini)))
        revisions = [
            rev.revision
            for rev in script.iterate_revisions(head, base)
            if rev.revision and rev.revision != base
        ]
        return list(reversed(revisions))
    except Exception:
        return [head] if head != base else []


def build_alembic_deploy_snapshot(
    *,
    remote_host: str | None = None,
    remote_path: str,
    dry_run: bool = False,
) -> AlembicDeploySnapshot:
    snapshot = AlembicDeploySnapshot()
    snapshot.local_head, _ = read_local_alembic_head()
    snapshot.local_current, _, snapshot.local_current_available = read_local_alembic_current()
    snapshot.remote_revision, snapshot.remote_error, snapshot.remote_available = read_remote_alembic_revision(
        remote_host=remote_host,
        remote_path=remote_path,
        dry_run=dry_run,
    )
    if snapshot.migration_required and snapshot.remote_available:
        base = snapshot.remote_revision or ""
        snapshot.pending_revisions = pending_revisions_between(base, snapshot.local_head)
    return snapshot
