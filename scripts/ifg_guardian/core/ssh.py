from __future__ import annotations

import subprocess


def ssh(host: str, remote_cmd: str) -> str:
    result = subprocess.run(
        ["ssh", host, remote_cmd],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(detail or f"ssh {host} failed")
    return result.stdout.strip()


def remote_git(host: str, repo_path: str, git_args: str) -> str:
    return ssh(host, f"cd {repo_path} && git {git_args}")
