from __future__ import annotations

import os
import subprocess

from ifg_guardian.config import DEFAULT_REMOTE_HOST, ROOT


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(detail or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def short_sha(sha: str) -> str:
    return sha[:7]


def porcelain_is_dirty(porcelain: str) -> bool:
    for line in porcelain.splitlines():
        if not line.strip():
            continue
        status = line[:2]
        path = line[3:].strip() if len(line) > 3 else ""
        if status == "??" and (path == "backups" or path.startswith("backups/")):
            continue
        return True
    return False


def parse_porcelain_line(line: str) -> tuple[str, str]:
    """Parse `git status --porcelain` line into (XY status, path)."""
    line = line.rstrip("\n\r")
    if not line:
        return "", ""
    status = line[:2]
    rest = line[2:].lstrip()
    if " -> " in rest:
        rest = rest.split(" -> ", 1)[1]
    return status, rest


def resolve_ds723_host(cli_host: str | None) -> str:
    if cli_host is not None:
        return cli_host
    return os.environ.get("IFG_DS723_HOST", DEFAULT_REMOTE_HOST)
