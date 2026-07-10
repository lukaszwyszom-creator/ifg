"""Guardian remote pre-pull unblock for DS723+ (operational, uses SSHExecutor)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ifg_guardian.config import ROOT
from ifg_guardian.core.deploy_config import DS723Config
from ifg_guardian.core.preflight.probes import run_remote_readonly
from ifg_guardian.core.workflow.executors.context import DeployExecutorContext
from ifg_guardian.core.workflow.executors.ssh_executor import SSHExecutor

BLOCKER_PATH = "frontend-react/dist/index.html"
EXPECTED_HEAD = "0cbaeba6e2c7ddb4d1b18b25be93958372201d0d"


@dataclass
class PullUnblockResult:
    ok: bool
    head_before: str
    head_after: str
    status_before: str
    status_after: str
    backup_path: str
    pull_output: str
    error: str = ""


def _ssh_executor(cfg: DS723Config) -> SSHExecutor:
    deploy_ctx = DeployExecutorContext(remote_host=cfg.host, remote_path=cfg.repo)
    return SSHExecutor(root=ROOT, deploy_context=deploy_ctx)


def _parse_marker(output: str, marker: str) -> str:
    pattern = rf"=== {marker} ===\n(.*?)(?:\n=== |\Z)"
    match = re.search(pattern, output, re.DOTALL)
    return match.group(1).strip() if match else ""


def inspect_remote(*, remote_path: str | None = None, remote_host: str | None = None) -> tuple[bool, str]:
    cfg = DS723Config.from_context(remote_host=remote_host, remote_path=remote_path)
    script = (
        'echo "=== BRANCH ==="\n'
        "git branch --show-current\n"
        'echo "=== HEAD ==="\n'
        "git rev-parse HEAD\n"
        'echo "=== STATUS ==="\n'
        "git status --short\n"
    )
    probe = run_remote_readonly(cfg, script, label="inspect")
    if not probe.ok:
        return False, probe.error or probe.output
    return True, probe.output


def run_ds723_pull_unblock(
    *,
    remote_path: str | None = None,
    remote_host: str | None = None,
) -> PullUnblockResult:
    cfg = DS723Config.from_context(remote_host=remote_host, remote_path=remote_path)
    ssh = _ssh_executor(cfg)

    inspect = run_remote_readonly(
        cfg,
        'echo "=== STATUS ==="\n'
        "git status --short\n"
        'echo "=== HEAD ==="\n'
        "git rev-parse HEAD\n",
        label="pre_unblock_inspect",
    )
    if not inspect.ok:
        return PullUnblockResult(
            ok=False,
            head_before="",
            head_after="",
            status_before="",
            status_after="",
            backup_path="",
            pull_output="",
            error=inspect.error or inspect.output,
        )

    status_before = _parse_marker(inspect.output, "STATUS")
    head_before = _parse_marker(inspect.output, "HEAD").splitlines()[-1] if inspect.output else ""

    unblock_script = f"""
BLOCKER="{BLOCKER_PATH}"
stamp=$(date +%Y%m%d_%H%M%S)
backup_dir="backups/pull_unblock_${{stamp}}"
guardian_backup=".guardian/pull_unblock/index.html.${{stamp}}.bak"
mkdir -p backups .guardian/pull_unblock "$backup_dir"

echo "=== STATUS ==="
git status --short

if [ ! -f "$BLOCKER" ]; then
  echo "BLOCKER_MISSING=1"
  exit 2
fi

modified=$(git status --porcelain | grep -E '^.[MADRCU]' || true)
other=$(echo "$modified" | grep -v "$BLOCKER" | grep -v '^$' || true)
if [ -n "$other" ]; then
  echo "OTHER_MODIFIED=$other"
  exit 3
fi

if ! echo "$modified" | grep -q "$BLOCKER"; then
  echo "BLOCKER_NOT_MODIFIED=1"
  git status --short
  exit 4
fi

cp -a "$BLOCKER" "$backup_dir/index.html.bak"
cp -a "$BLOCKER" "$guardian_backup"
echo "BACKUP_PATH=$backup_dir/index.html.bak"
echo "GUARDIAN_BACKUP=$guardian_backup"

git checkout HEAD -- "$BLOCKER"
echo "=== STATUS_AFTER_RESTORE ==="
git status --short

git fetch origin {cfg.branch}
git pull origin {cfg.branch}

echo "=== HEAD_AFTER ==="
git rev-parse HEAD
git log -1 --oneline
echo "=== STATUS_AFTER_PULL ==="
git status --short
"""

    result = ssh.run_remote(unblock_script, label="pull_unblock")
    if not result.ok:
        return PullUnblockResult(
            ok=False,
            head_before=head_before,
            head_after="",
            status_before=status_before,
            status_after="",
            backup_path="",
            pull_output=result.output,
            error=result.error or result.output,
        )

    output = result.output or ""
    head_after = _parse_marker(output, "HEAD_AFTER").splitlines()[0] if "HEAD_AFTER" in output else ""
    if not head_after:
        for line in output.splitlines():
            if re.fullmatch(r"[0-9a-f]{40}", line.strip()):
                head_after = line.strip()
                break

    status_after = _parse_marker(output, "STATUS_AFTER_PULL")
    backup_match = re.search(r"BACKUP_PATH=(\S+)", output)
    backup_path = backup_match.group(1) if backup_match else ""

    ok = head_after.startswith(EXPECTED_HEAD[:7]) or head_after == EXPECTED_HEAD
    return PullUnblockResult(
        ok=ok,
        head_before=head_before,
        head_after=head_after,
        status_before=status_before,
        status_after=status_after,
        backup_path=backup_path,
        pull_output=output,
    )


def main() -> int:
    import sys

    remote_path = sys.argv[1] if len(sys.argv) > 1 else None
    result = run_ds723_pull_unblock(remote_path=remote_path)
    if result.error:
        print(f"ERROR: {result.error}")
    print(f"HEAD before: {result.head_before}")
    print(f"HEAD after:  {result.head_after}")
    print(f"Backup:      {result.backup_path}")
    print(f"Status before:\n{result.status_before}")
    print(f"Status after:\n{result.status_after}")
    if result.pull_output:
        print(f"\n--- remote log ---\n{result.pull_output}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
