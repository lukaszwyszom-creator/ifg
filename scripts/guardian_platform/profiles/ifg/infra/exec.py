from __future__ import annotations

import subprocess
from dataclasses import dataclass

from guardian_platform.profiles.ifg.config.defaults import REPO_ROOT


@dataclass
class ExecResult:
    ok: bool
    simulated: bool
    output: str = ""
    error: str = ""
    returncode: int = 0


def run_local(
    cmd: list[str] | str,
    *,
    cwd: Path | None = None,
    dry_run: bool = False,
    mutating: bool = True,
) -> ExecResult:
    if isinstance(cmd, str):
        shell_cmd = cmd
    else:
        shell_cmd = " ".join(cmd)

    if dry_run:
        return ExecResult(ok=True, simulated=True, output=f"[dry-run] would: {shell_cmd}")

    if isinstance(cmd, list):
        result = subprocess.run(
            cmd,
            cwd=cwd or REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    else:
        result = subprocess.run(
            shell_cmd,
            cwd=cwd or REPO_ROOT,
            shell=True,
            capture_output=True,
            text=True,
            check=False,
        )

    output = (result.stdout or result.stderr or "").strip()
    return ExecResult(
        ok=result.returncode == 0,
        simulated=False,
        output=output,
        error="" if result.returncode == 0 else output,
        returncode=result.returncode,
    )


def run_remote(
    host: str,
    remote_cmd: str,
    *,
    remote_path: str,
    dry_run: bool = False,
    mutating: bool = True,
) -> ExecResult:
    full = f"cd {remote_path} && {remote_cmd}"
    wrapped = f"ssh {host} {full!r}"

    if dry_run:
        return ExecResult(ok=True, simulated=True, output=f"[dry-run] would: {wrapped}")

    result = subprocess.run(
        ["ssh", host, full],
        capture_output=True,
        text=True,
        check=False,
    )
    output = (result.stdout or result.stderr or "").strip()
    return ExecResult(
        ok=result.returncode == 0,
        simulated=False,
        output=output,
        error="" if result.returncode == 0 else output,
        returncode=result.returncode,
    )
