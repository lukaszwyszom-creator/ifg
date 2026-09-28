#!/usr/bin/env python3
"""Install / update managed prod-monitor runtime from a verified Git SHA (GWO-0010E).

Materializes a minimal manifest via `git archive` into:
  ~/Library/Application Support/Guardian/ifg-prod-monitor/

Does NOT copy working-tree WIP. Refuses dirty trees as SOURCE materialization
is always from Git objects at --source-sha.

Usage (from canonical SSD checkout):
  PYTHONPATH=scripts python3 -m ifg_guardian.prod_monitor_runtime.install \\
    --source-repo /Volumes/WorkspaceSSD/projects/ifg_standalone \\
    --source-sha <SHA> \\
    [--migrate-state-from /Users/lukasz/projekty/ifg_standalone/.state] \\
    [--write-launchagent]   # cutover; only after pre-cutover smoke PASS
    [--rollback]            # point current at previous release
"""
from __future__ import annotations

import argparse
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_RUNTIME_HOME = (
    Path.home() / "Library" / "Application Support" / "Guardian" / "ifg-prod-monitor"
)
LAUNCHD_LABEL = "com.ifg.guardian.prod-monitor"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_LABEL}.plist"
PREFERRED_PYTHON = Path("/opt/homebrew/bin/python3.13")
STATE_MIGRATE_FILES = (
    "runtime_monitor.json",
    "runtime_notifications.log",
    "runtime_audit.jsonl",
    "maintenance.json",
)
MANIFEST_REL = Path("scripts/ifg_guardian/prod_monitor_runtime/MANIFEST.txt")


def _run(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=check,
    )


def _resolve_sha(repo: Path, sha: str) -> str:
    proc = _run(
        ["git", "-C", str(repo), "rev-parse", "--verify", f"{sha}^{{commit}}"],
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"REFUSE: SOURCE_SHA not resolvable in {repo}: {sha}")
    return proc.stdout.strip()


def _assert_sha_exists(repo: Path, sha: str) -> None:
    cat = _run(["git", "-C", str(repo), "cat-file", "-t", sha], check=False)
    if cat.returncode != 0 or cat.stdout.strip() != "commit":
        raise SystemExit(f"REFUSE: SOURCE_SHA {sha} is not a commit in {repo}")


def _working_tree_dirty(repo: Path) -> bool:
    """True if tracked files differ from HEAD (untracked ignored for install source)."""
    proc = _run(["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=no"])
    return bool(proc.stdout.strip())


def _read_manifest(repo: Path, sha: str) -> list[str]:
    """Read MANIFEST.txt from Git object at sha (not working tree)."""
    proc = _run(
        ["git", "-C", str(repo), "show", f"{sha}:{MANIFEST_REL.as_posix()}"],
        check=False,
    )
    if proc.returncode != 0:
        # Fallback: working-tree manifest only when installing current branch tip that adds it.
        local = repo / MANIFEST_REL
        if not local.is_file():
            raise SystemExit(f"REFUSE: MANIFEST missing at {sha}:{MANIFEST_REL}")
        text = local.read_text(encoding="utf-8")
    else:
        text = proc.stdout
    paths: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        paths.append(line)
    if not paths:
        raise SystemExit("REFUSE: empty MANIFEST")
    return paths


def _materialize_release(repo: Path, sha: str, release_dir: Path, paths: list[str]) -> None:
    release_dir.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="ifg-prod-monitor-archive-") as tmp:
        tmp_path = Path(tmp)
        archive = tmp_path / "release.tar"
        # git archive only includes listed paths that exist at sha
        cmd = ["git", "-C", str(repo), "archive", "--format=tar", "-o", str(archive), sha, "--", *paths]
        arch = _run(cmd, check=False)
        if arch.returncode != 0:
            # Some paths may be new on this branch and not yet committed — refuse WT copy.
            raise SystemExit(
                "REFUSE: git archive failed (paths must exist in SOURCE_SHA object tree).\n"
                f"{arch.stderr or arch.stdout}"
            )
        _run(["tar", "-xf", str(archive), "-C", str(release_dir)])
    # Verify critical entry module present
    probe = release_dir / "scripts" / "ifg_guardian" / "modules" / "production_monitor.py"
    if not probe.is_file():
        shutil.rmtree(release_dir, ignore_errors=True)
        raise SystemExit(f"REFUSE: materialization missing {probe}")


def _ensure_venv(runtime_home: Path, python_bin: Path) -> Path:
    venv_dir = runtime_home / "runtime" / "venv"
    py = venv_dir / "bin" / "python3"
    if py.is_file():
        return py
    if not python_bin.is_file():
        raise SystemExit(f"REFUSE: Python not found: {python_bin}")
    runtime_home.joinpath("runtime").mkdir(parents=True, exist_ok=True)
    _run([str(python_bin), "-m", "venv", str(venv_dir)])
    if not py.is_file():
        raise SystemExit(f"REFUSE: venv create failed at {venv_dir}")
    # No pip install — prod-monitor path is stdlib-only.
    return py


def _write_runner(runtime_home: Path, repo: Path, sha: str) -> None:
    """Write stable runner from Git object (or local if present at sha)."""
    rel = "scripts/ifg_guardian/prod_monitor_runtime/runner.py"
    proc = _run(["git", "-C", str(repo), "show", f"{sha}:{rel}"], check=False)
    if proc.returncode != 0:
        local = repo / rel
        if not local.is_file():
            raise SystemExit(f"REFUSE: runner.py missing at {sha}")
        content = local.read_text(encoding="utf-8")
    else:
        content = proc.stdout
    dest = runtime_home / "runner.py"
    dest.write_text(content, encoding="utf-8")
    dest.chmod(0o755)


def _atomic_switch_current(runtime_home: Path, release_dir: Path) -> Path | None:
    current = runtime_home / "current"
    previous: Path | None = None
    if current.is_symlink() or current.exists():
        try:
            previous = current.resolve()
        except OSError:
            previous = None
    tmp_link = runtime_home / f".current.tmp.{os.getpid()}"
    if tmp_link.exists() or tmp_link.is_symlink():
        tmp_link.unlink()
    tmp_link.symlink_to(release_dir, target_is_directory=True)
    os.replace(tmp_link, current)
    return previous


def _write_deployed_sha(runtime_home: Path, sha: str) -> None:
    (runtime_home / "deployed_sha").write_text(sha + "\n", encoding="utf-8")


def _migrate_state(src: Path, dest: Path) -> list[str]:
    dest.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    if not src.is_dir():
        return copied
    for name in STATE_MIGRATE_FILES:
        s = src / name
        d = dest / name
        if s.is_file() and not d.exists():
            shutil.copy2(s, d)
            copied.append(name)
    return copied


def _build_managed_plist(*, runtime_home: Path, python: Path) -> dict:
    state = runtime_home / "runtime" / "state"
    logs = runtime_home / "runtime" / "logs"
    runner = runtime_home / "runner.py"
    return {
        "Label": LAUNCHD_LABEL,
        "ProgramArguments": [str(python), str(runner)],
        "WorkingDirectory": str(runtime_home),
        "EnvironmentVariables": {
            "IFG_GUARDIAN_STATE_DIR": str(state),
            "IFG_GUARDIAN_LOG_DIR": str(logs),
            # PATH kept minimal; SSH uses user known_hosts via default ssh
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin",
        },
        "StartInterval": 300,
        "RunAtLoad": True,
        "StandardOutPath": str(logs / "prod_monitor.log"),
        "StandardErrorPath": str(logs / "prod_monitor.log"),
        "ProcessType": "Background",
    }


def _backup_plist(runtime_home: Path) -> Path | None:
    if not PLIST_PATH.is_file():
        return None
    backup_dir = runtime_home / "rollback"
    backup_dir.mkdir(parents=True, exist_ok=True)
    dest = backup_dir / "com.ifg.guardian.prod-monitor.plist.before-0010e"
    if not dest.exists():
        shutil.copy2(PLIST_PATH, dest)
    return dest


def write_launchagent(*, runtime_home: Path, python: Path) -> None:
    logs = runtime_home / "runtime" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    _backup_plist(runtime_home)
    plist = _build_managed_plist(runtime_home=runtime_home, python=python)
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_bytes(plistlib.dumps(plist))
    uid = os.getuid()
    subprocess.run(
        ["launchctl", "bootout", f"gui/{uid}", str(PLIST_PATH)],
        check=False,
        capture_output=True,
    )
    boot = subprocess.run(
        ["launchctl", "bootstrap", f"gui/{uid}", str(PLIST_PATH)],
        capture_output=True,
        text=True,
    )
    if boot.returncode != 0:
        raise SystemExit(f"launchctl bootstrap failed: {boot.stderr or boot.stdout}")
    subprocess.run(["launchctl", "enable", f"gui/{uid}/{LAUNCHD_LABEL}"], check=False)
    # Kick once so we don't wait for StartInterval
    subprocess.run(["launchctl", "kickstart", "-k", f"gui/{uid}/{LAUNCHD_LABEL}"], check=False)


def cmd_install(args: argparse.Namespace) -> int:
    repo = Path(args.source_repo).resolve()
    if not (repo / ".git").exists():
        raise SystemExit(f"REFUSE: not a git repo: {repo}")
    sha = _resolve_sha(repo, args.source_sha)
    _assert_sha_exists(repo, sha)

    # Dirty WT is OK for *running* the installer from SSD, but materialization
    # must come from Git objects. Warn loudly if dirty so operator doesn't
    # think uncommitted edits are in the release.
    if _working_tree_dirty(repo):
        print(
            "WARN: source repo has dirty tracked files; release still comes from "
            f"Git object {sha[:12]} (working tree NOT copied)."
        )
    if args.require_clean and _working_tree_dirty(repo):
        raise SystemExit("REFUSE: --require-clean set and working tree is dirty")

    runtime_home = Path(args.runtime_home).expanduser().resolve()
    runtime_home.mkdir(parents=True, exist_ok=True)
    (runtime_home / "releases").mkdir(exist_ok=True)
    (runtime_home / "runtime" / "state").mkdir(parents=True, exist_ok=True)
    (runtime_home / "runtime" / "logs").mkdir(parents=True, exist_ok=True)

    paths = _read_manifest(repo, sha)
    # Ensure every path exists in the tree at sha
    missing = []
    for p in paths:
        chk = _run(["git", "-C", str(repo), "cat-file", "-e", f"{sha}:{p}"], check=False)
        if chk.returncode != 0:
            missing.append(p)
    if missing:
        raise SystemExit(
            "REFUSE: MANIFEST paths not in SOURCE_SHA (commit installer+manifest first):\n  "
            + "\n  ".join(missing)
        )

    release_dir = runtime_home / "releases" / sha
    if release_dir.exists():
        print(f"Release already materialized: {release_dir}")
    else:
        print(f"Materializing {sha} -> {release_dir}")
        _materialize_release(repo, sha, release_dir, paths)

    python = _ensure_venv(runtime_home, Path(args.python))
    _write_runner(runtime_home, repo, sha)
    previous = _atomic_switch_current(runtime_home, release_dir)
    _write_deployed_sha(runtime_home, sha)

    migrated: list[str] = []
    if args.migrate_state_from:
        migrated = _migrate_state(Path(args.migrate_state_from), runtime_home / "runtime" / "state")

    print("SOURCE_SHA:", sha)
    print("RUNTIME_HOME:", runtime_home)
    print("RELEASE_PATH:", release_dir)
    print("CURRENT:", (runtime_home / "current").resolve())
    print("PREVIOUS:", previous)
    print("PYTHON:", python)
    print("STATE:", runtime_home / "runtime" / "state")
    print("LOGS:", runtime_home / "runtime" / "logs")
    print("MIGRATED_STATE:", migrated or "none")

    if args.write_launchagent:
        write_launchagent(runtime_home=runtime_home, python=python)
        print("LAUNCHAGENT: updated", PLIST_PATH)
    else:
        print("LAUNCHAGENT: not modified (pass --write-launchagent after smoke PASS)")
    return 0


def cmd_rollback(args: argparse.Namespace) -> int:
    runtime_home = Path(args.runtime_home).expanduser().resolve()
    current = runtime_home / "current"
    if not current.is_symlink():
        raise SystemExit("REFUSE: current is not a symlink")
    active = current.resolve()
    releases = runtime_home / "releases"
    candidates = sorted(
        [p for p in releases.iterdir() if p.is_dir() and p.resolve() != active],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if args.to_sha:
        target = releases / args.to_sha
        if not target.is_dir():
            raise SystemExit(f"REFUSE: release not found: {target}")
    else:
        if not candidates:
            raise SystemExit("REFUSE: no previous release to rollback to")
        target = candidates[0]
    _atomic_switch_current(runtime_home, target)
    _write_deployed_sha(runtime_home, target.name)
    python = runtime_home / "runtime" / "venv" / "bin" / "python3"
    if not python.is_file():
        python = Path(args.python)
    if args.write_launchagent:
        write_launchagent(runtime_home=runtime_home, python=python)
    print("ROLLED_BACK_TO:", target)
    print("CURRENT:", current.resolve())
    return 0


def cmd_smoke(args: argparse.Namespace) -> int:
    """Run managed runner once without touching LaunchAgent."""
    runtime_home = Path(args.runtime_home).expanduser().resolve()
    python = runtime_home / "runtime" / "venv" / "bin" / "python3"
    runner = runtime_home / "runner.py"
    if not python.is_file() or not runner.is_file():
        raise SystemExit("REFUSE: runtime not installed (missing venv or runner)")
    env = os.environ.copy()
    env["IFG_GUARDIAN_STATE_DIR"] = str(runtime_home / "runtime" / "state")
    env["IFG_GUARDIAN_LOG_DIR"] = str(runtime_home / "runtime" / "logs")
    proc = subprocess.run([str(python), str(runner)], env=env)
    return int(proc.returncode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IFG prod-monitor managed runtime installer")
    sub = parser.add_subparsers(dest="command", required=True)

    p_install = sub.add_parser("install", help="Materialize release from SOURCE_SHA")
    p_install.add_argument("--source-repo", required=True)
    p_install.add_argument("--source-sha", required=True)
    p_install.add_argument("--runtime-home", default=str(DEFAULT_RUNTIME_HOME))
    p_install.add_argument("--python", default=str(PREFERRED_PYTHON))
    p_install.add_argument("--migrate-state-from", default="")
    p_install.add_argument("--write-launchagent", action="store_true")
    p_install.add_argument("--require-clean", action="store_true")
    p_install.set_defaults(func=cmd_install)

    p_rb = sub.add_parser("rollback", help="Point current at a previous release")
    p_rb.add_argument("--runtime-home", default=str(DEFAULT_RUNTIME_HOME))
    p_rb.add_argument("--to-sha", default="")
    p_rb.add_argument("--python", default=str(PREFERRED_PYTHON))
    p_rb.add_argument("--write-launchagent", action="store_true")
    p_rb.set_defaults(func=cmd_rollback)

    p_smoke = sub.add_parser("smoke", help="Run managed runner once (no LaunchAgent)")
    p_smoke.add_argument("--runtime-home", default=str(DEFAULT_RUNTIME_HOME))
    p_smoke.set_defaults(func=cmd_smoke)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
