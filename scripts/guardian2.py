#!/usr/bin/env python3
"""IFG Guardian2 MVP — półautomatyczny deploy KSeF async sync (Guardian = read-only)."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET_BRANCH = "production"
DEFAULT_REMOTE_HOST = "ds723"
DEFAULT_REMOTE_PATH = "/volume1/docker/ifg_v2/ifg_standalone"
COMPOSE_FILE = "docker/docker-compose.prod.yml"
COMMIT_MSG = "fix: harden KSeF async sync deploy flow"

DEPLOY_ALLOWLIST = (
    "app/api/routers/ksef_session.py",
    "app/worker/job_handlers/sync_purchase_invoices.py",
    "frontend-react/src/api/ksef.js",
    "frontend-react/src/api/ksef.purchase-sync.test.mjs",
    "frontend-react/src/components/dashboard/KSeFSessionBar.jsx",
    "frontend-react/src/components/layout/KSeFTopbarInfo.jsx",
    "scripts/guardian.py",
    "scripts/guardian2.py",
    "docs/KSEF_FORCE_ASYNC_PURCHASE_SYNC.md",
    "docs/KSEF_SYNC_REFRESH_UX_FIX.md",
    "docs/KSEF_ASYNC_SYNC_E2E_DIAGNOSTIC.md",
    "docs/GUARDIAN2_DEPLOY.md",
)


class DeployAbort(Exception):
    pass


def _section(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def _resolve_host(cli_host: str | None) -> str:
    return cli_host or os.environ.get("IFG_DS723_HOST", DEFAULT_REMOTE_HOST)


def _quote_shell(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def run(
    cmd: list[str] | str,
    *,
    cwd: Path | None = None,
    remote: bool = False,
    host: str | None = None,
    dry_run: bool = False,
) -> None:
    workdir = cwd or ROOT
    display = " ".join(cmd) if isinstance(cmd, list) else cmd

    if remote:
        host = host or DEFAULT_REMOTE_HOST
        remote_cmd = f"cd {_quote_shell(DEFAULT_REMOTE_PATH)} && {display}"
        full_display = f"ssh {host} {remote_cmd!r}"
        argv = ["ssh", host, remote_cmd]
        exec_cwd = None
    elif isinstance(cmd, list):
        full_display = f"(cwd={workdir}) {display}"
        argv = cmd
        exec_cwd = workdir
    else:
        full_display = f"(cwd={workdir}) {display}"
        argv = ["bash", "-lc", cmd]
        exec_cwd = workdir

    print(f"{'[dry-run] ' if dry_run else ''}> {full_display}")
    if dry_run:
        return

    try:
        subprocess.run(argv, cwd=exec_cwd, check=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise DeployAbort(f"Polecenie nie powiodło się (exit {exc.returncode}): {display}") from exc


def _git_output(args: list[str]) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _ensure_local_production_branch(*, dry_run: bool) -> None:
    if dry_run:
        run(["git", "branch", "--show-current"], dry_run=True)
        return
    branch = _git_output(["branch", "--show-current"])
    if branch != TARGET_BRANCH:
        raise DeployAbort(f"Wymagany branch {TARGET_BRANCH}, aktualny: {branch or '(unknown)'}")


def _remote_branch(host: str) -> str:
    result = subprocess.run(
        ["ssh", host, f"cd {_quote_shell(DEFAULT_REMOTE_PATH)} && git branch --show-current"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _ensure_remote_production_branch(*, host: str, dry_run: bool) -> None:
    if dry_run:
        run("git branch --show-current", remote=True, host=host, dry_run=True)
        return
    branch = _remote_branch(host)
    if branch != TARGET_BRANCH:
        raise DeployAbort(
            f"DS723+ wymaga branch {TARGET_BRANCH}, aktualny: {branch or '(unknown)'}",
        )


def _stage_allowlist(*, dry_run: bool) -> list[str]:
    existing = [rel for rel in DEPLOY_ALLOWLIST if (ROOT / rel).exists()]
    for rel in existing:
        run(["git", "add", rel], dry_run=dry_run)
    if dry_run:
        return existing
    staged_raw = _git_output(["diff", "--cached", "--name-only"])
    return [line for line in staged_raw.splitlines() if line.strip()]


def deploy_ksef_local(*, dry_run: bool) -> None:
    _section("LOCAL — deploy-ksef")

    _ensure_local_production_branch(dry_run=dry_run)
    run(["node", "--test", "frontend-react/src/api/ksef.purchase-sync.test.mjs"], dry_run=dry_run)
    run("npm ci && npm run build", cwd=ROOT / "frontend-react", dry_run=dry_run)
    run(["python3", "scripts/guardian.py", "--ksef-async-check"], dry_run=dry_run)
    run(["git", "status", "--short"], dry_run=dry_run)

    staged = _stage_allowlist(dry_run=dry_run)
    if dry_run:
        print(f"[dry-run] staged: {', '.join(staged) if staged else '(brak)'}")
        if staged:
            run(["git", "commit", "-m", COMMIT_MSG], dry_run=True)
        run(["git", "push", "origin", TARGET_BRANCH], dry_run=True)
        return

    if staged:
        run(["git", "commit", "-m", COMMIT_MSG])
    else:
        print("Brak zmian staged z allowlisty — pomijam commit.")
    run(["git", "push", "origin", TARGET_BRANCH])


def deploy_ksef_remote(*, host: str, dry_run: bool) -> None:
    _section(f"REMOTE — {host} ({DEFAULT_REMOTE_PATH})")

    _ensure_remote_production_branch(host=host, dry_run=dry_run)
    run("git pull origin production", remote=True, host=host, dry_run=dry_run)
    run(
        "cd frontend-react && npm ci && npm run build",
        remote=True,
        host=host,
        dry_run=dry_run,
    )

    compose = f"sudo docker compose -f {COMPOSE_FILE}"
    run(f"{compose} build api", remote=True, host=host, dry_run=dry_run)
    run(
        f"{compose} up -d --no-deps --force-recreate api worker",
        remote=True,
        host=host,
        dry_run=dry_run,
    )

    run(["python3", "scripts/guardian.py", "--ksef-async-check"], remote=True, host=host, dry_run=dry_run)
    run(["python3", "scripts/guardian.py", "--deploy-check"], remote=True, host=host, dry_run=dry_run)
    run("curl -fsS http://127.0.0.1:8000/health", remote=True, host=host, dry_run=dry_run)


def _confirm_remote(*, assume_yes: bool, dry_run: bool) -> None:
    if assume_yes or dry_run:
        if dry_run and not assume_yes:
            print("[dry-run] Pytałbym: Kontynuować deploy na DS723+? [y/N]")
        return
    answer = input("Kontynuować deploy na DS723+? [y/N] ").strip().lower()
    if answer not in ("y", "yes"):
        raise DeployAbort("Deploy remote anulowany przez użytkownika.")


def deploy_ksef(*, dry_run: bool, assume_yes: bool, host: str) -> int:
    print("IFG Guardian2 MVP — deploy-ksef")
    if dry_run:
        print("[dry-run] Żadne polecenie nie zostanie wykonane.")

    try:
        deploy_ksef_local(dry_run=dry_run)
        _confirm_remote(assume_yes=assume_yes, dry_run=dry_run)
        deploy_ksef_remote(host=host, dry_run=dry_run)
        _section("SUKCES")
        print("deploy-ksef zakończony pomyślnie.")
        return 0
    except DeployAbort as exc:
        print(f"\nABORT: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nABORT: przerwano.", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="IFG Guardian2 MVP — deploy KSeF async sync (Guardian = read-only).",
        epilog=(
            "Przykłady:\n"
            "  python3 scripts/guardian2.py deploy-ksef --dry-run\n"
            "  python3 scripts/guardian2.py deploy-ksef\n"
            "  python3 scripts/guardian2.py deploy-ksef --yes\n"
            "\n"
            "IFG_DS723_HOST — host SSH (domyślnie: ds723)\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("command", choices=["deploy-ksef"], help="Scenariusz deployu")
    parser.add_argument("--dry-run", action="store_true", help="Wypisz polecenia bez wykonywania")
    parser.add_argument("--yes", action="store_true", help="Pomiń pytanie przed etapem remote")
    parser.add_argument(
        "--remote-host",
        default=None,
        help=f"Host SSH (domyślnie IFG_DS723_HOST lub {DEFAULT_REMOTE_HOST})",
    )
    args = parser.parse_args()

    if args.command == "deploy-ksef":
        return deploy_ksef(dry_run=args.dry_run, assume_yes=args.yes, host=_resolve_host(args.remote_host))
    return 1


if __name__ == "__main__":
    sys.exit(main())
