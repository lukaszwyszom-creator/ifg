from __future__ import annotations

import subprocess
from dataclasses import dataclass

from ifg_guardian.core.deploy_config import DS723Config


@dataclass
class RemoteProbeResult:
    ok: bool
    output: str = ""
    error: str = ""


def run_remote_readonly(cfg: DS723Config, script_body: str, *, label: str = "preflight") -> RemoteProbeResult:
    """Execute read-only commands on remote host via SSH. Does not mutate environment."""
    full_script = cfg.remote_preamble() + script_body
    command = ["ssh", "-p", str(cfg.port), cfg.ssh_target, "bash", "-s"]
    try:
        result = subprocess.run(
            command,
            input=full_script,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return RemoteProbeResult(ok=False, error=str(exc))

    output = (result.stdout or "").strip()
    error = (result.stderr or "").strip()
    if result.returncode != 0:
        return RemoteProbeResult(ok=False, output=output, error=error or f"ssh exit {result.returncode}")
    return RemoteProbeResult(ok=True, output=output, error=error)
