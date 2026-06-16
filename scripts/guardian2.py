#!/usr/bin/env python3
"""IFG Guardian2 MVP — deploy i recovery produkcji DS723+."""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_guardian_spec = importlib.util.spec_from_file_location(
    "guardian", ROOT / "scripts" / "guardian.py"
)
assert _guardian_spec and _guardian_spec.loader
_guardian = importlib.util.module_from_spec(_guardian_spec)
sys.modules["guardian"] = _guardian
_guardian_spec.loader.exec_module(_guardian)

COMPOSE_FILE = _guardian.COMPOSE_FILE
DEFAULT_REMOTE_HOST = _guardian.DEFAULT_REMOTE_HOST
DEFAULT_REMOTE_PATH = _guardian.DEFAULT_REMOTE_PATH
parse_compose_service_states = _guardian.parse_compose_service_states
service_state_is_healthy = _guardian.service_state_is_healthy
service_state_is_restarting = _guardian.service_state_is_restarting
service_state_is_running = _guardian.service_state_is_running
TARGET_BRANCH = "production"
COMMIT_MSG = "fix: harden KSeF async sync deploy flow"
REMOTE_NPM_PATH = "/usr/local/bin:/opt/bin:/opt/homebrew/bin"
NPM_NOT_FOUND_MSG = "npm not found on DS723+ non-interactive SSH session"
RECOVERY_REPORT_PATH = ROOT / "docs" / "GUARDIAN2_RECOVERY_DS723.md"
RECOVERY_WAIT_SECONDS = 60
RECOVERY_POLL_SECONDS = 5

DEPLOY_ALLOWLIST = (
    "app/api/routers/ksef_session.py",
    "app/worker/job_handlers/sync_purchase_invoices.py",
    "frontend-react/src/api/ksef.js",
    "frontend-react/src/api/ksef.purchase-sync.test.mjs",
    "frontend-react/src/components/dashboard/KSeFSessionBar.jsx",
    "frontend-react/src/components/layout/KSeFConnectionTile.jsx",
    "frontend-react/src/components/layout/KSeFTopbarInfo.jsx",
    "scripts/guardian.py",
    "scripts/guardian2.py",
    "docs/KSEF_FORCE_ASYNC_PURCHASE_SYNC.md",
    "docs/KSEF_SYNC_REFRESH_UX_FIX.md",
    "docs/KSEF_CONNECT_BUTTON_FIX.md",
    "docs/KSEF_ASYNC_SYNC_E2E_DIAGNOSTIC.md",
    "docs/GUARDIAN2_DEPLOY.md",
    "docs/GUARDIAN_FRONTEND_BUILD_CHECK.md",
    "docs/GUARDIAN2_RECOVERY_DS723.md",
)


class DeployAbort(Exception):
    pass


@dataclass
class RecoveryReport:
    host: str
    repo_path: str
    git_branch: str = ""
    git_head: str = ""
    git_status: str = ""
    compose_services: str = ""
    ps_before: str = ""
    ps_after: str = ""
    db_has_service: bool = False
    db_ok: bool = False
    api_ok: bool = False
    worker_ok: bool = False
    cloudflared_ok: bool = False
    health_url: str = ""
    health_body: str = ""
    health_ok: bool = False
    api_logs: str = ""
    cloudflared_ps: str = ""
    cloudflared_logs: str = ""
    ksef_connect_blocker: str = ""
    notes: list[str] = field(default_factory=list)
    aborted: bool = False
    abort_reason: str = ""

    def summary_lines(self) -> list[str]:
        return [
            f"- **db:** {'działa' if self.db_ok else 'NIE działa'}",
            f"- **api:** {'działa' if self.api_ok else 'NIE działa'}",
            f"- **worker:** {'działa' if self.worker_ok else 'NIE działa'}",
            f"- **cloudflared-ifg:** {'działa' if self.cloudflared_ok else 'NIE działa / brak'}",
            f"- **health check:** `{self.health_url or 'brak'}` → "
            f"{'OK' if self.health_ok else 'FAIL'}",
            f"- **KSeF Connect blocker:** {self.ksef_connect_blocker or 'brak (API+worker OK)'}",
        ]


def _section(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def _resolve_host(cli_host: str | None) -> str:
    return cli_host or os.environ.get("IFG_DS723_HOST", DEFAULT_REMOTE_HOST)


def _quote_shell(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _remote_with_npm(shell_cmd: str) -> str:
    return (
        f'export PATH="{REMOTE_NPM_PATH}:$PATH" && '
        "command -v npm >/dev/null 2>&1 || "
        f'{{ echo "{NPM_NOT_FOUND_MSG}" >&2; exit 127; }} && '
        f"{shell_cmd}"
    )


def _ssh_capture(
    host: str,
    remote_cmd: str,
    *,
    cwd: str | None = DEFAULT_REMOTE_PATH,
) -> tuple[int, str, str]:
    prefix = f"cd {_quote_shell(cwd)} && " if cwd else ""
    argv = ["ssh", host, prefix + remote_cmd]
    result = subprocess.run(argv, capture_output=True, text=True, check=False)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


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
        if remote and "npm" in display and exc.returncode == 127:
            raise DeployAbort(NPM_NOT_FOUND_MSG) from exc
        raise DeployAbort(f"Polecenie nie powiodło się (exit {exc.returncode}): {display}") from exc


def _git_output(args: list[str]) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _compose_cmd() -> str:
    return f"sudo docker compose -f {COMPOSE_FILE}"


def _remote_compose_ps(host: str, *, all_containers: bool = False) -> str:
    flag = " -a" if all_containers else ""
    code, out, err = _ssh_capture(
        host,
        f"{_compose_cmd()} ps{flag} --format '{{{{.Service}}}}\\t{{{{.State}}}}\\t{{{{.Health}}}}'",
    )
    if code != 0 or not out:
        _, out, _ = _ssh_capture(host, f"{_compose_cmd()} ps{flag}")
    if err and not out:
        return err
    return out


def _wait_for_service(
    host: str,
    service: str,
    *,
    predicate,
    timeout_seconds: int = RECOVERY_WAIT_SECONDS,
    label: str,
) -> tuple[bool, str]:
    deadline = time.monotonic() + timeout_seconds
    last_line = ""
    while time.monotonic() < deadline:
        ps_output = _remote_compose_ps(host)
        states = parse_compose_service_states(ps_output)
        last_line = states.get(service, "")
        if predicate(last_line):
            return True, last_line
        time.sleep(RECOVERY_POLL_SECONDS)
    return False, last_line or f"brak wpisu {service} w compose ps"


def _infer_ksef_blocker(report: RecoveryReport) -> str:
    if not report.db_ok:
        return "PostgreSQL (db) niedostępna — API nie może startować (depends_on db healthy)."
    if not report.api_ok or not report.health_ok:
        if report.api_logs and "could not connect to server" in report.api_logs.lower():
            return "API crash — brak połączenia z PostgreSQL."
        if service_state_is_restarting(parse_compose_service_states(report.ps_after).get("api")):
            return "Kontener API w stanie Restarting — backend niedostępny dla UI i KSeF Connect."
        return "HTTP /health niedostępny — Cloudflare/KSeF Connect nie ma działającego origin API."
    if not report.worker_ok:
        return "API działa, ale worker nie — async sync KSeF (background_jobs) nie będzie przetwarzany."
    if not report.cloudflared_ok:
        return (
            "API działa lokalnie, ale cloudflared-ifg nieosiągalny — tunel Cloudflare może nie "
            "kierować ruchu na http://127.0.0.1:8000 lub inny origin w tej samej sieci Docker."
        )
    if not report.health_ok:
        return "Health check FAIL mimo running API — sprawdź logi api i ingress cloudflared."
    return ""


def _write_recovery_report(report: RecoveryReport) -> None:
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# Guardian2 recover-prod — DS723+",
        "",
        "Tryb recovery: `python3 scripts/guardian2.py recover-prod --yes`",
        "",
        "Bezpieczne operacje: `up -d db`, `up -d api worker` — **bez** `down -v`, bez resetu DB.",
        "",
        f"**Wygenerowano:** {ts}  ",
        f"**Host:** `{report.host}`  ",
        f"**Repo:** `{report.repo_path}`  ",
        "",
        "## Podsumowanie",
        "",
        *report.summary_lines(),
        "",
    ]
    if report.aborted:
        lines.extend(["## Przerwano", "", f"**Powód:** {report.abort_reason}", ""])
    if report.notes:
        lines.extend(["## Notatki", ""])
        lines.extend(f"- {note}" for note in report.notes)
        lines.append("")
    lines.extend([
        "## Git",
        "",
        f"- branch: `{report.git_branch}`",
        f"- HEAD: `{report.git_head}`",
        "",
        "```",
        report.git_status or "(clean)",
        "```",
        "",
        "## Compose services (config)",
        "",
        "```",
        report.compose_services,
        "```",
        "",
        "## docker compose ps (przed)",
        "",
        "```",
        report.ps_before,
        "```",
        "",
        "## docker compose ps (po)",
        "",
        "```",
        report.ps_after,
        "```",
        "",
        "## Health",
        "",
        f"- URL: `{report.health_url}`",
        f"- OK: {report.health_ok}",
        "",
        "```",
        report.health_body or "(brak odpowiedzi)",
        "```",
        "",
        "## API logs (tail 120)",
        "",
        "```",
        report.api_logs,
        "```",
        "",
        "## cloudflared-ifg",
        "",
        "```",
        report.cloudflared_ps,
        "```",
        "",
        "```",
        report.cloudflared_logs,
        "```",
        "",
        "## Cloudflare / sieć",
        "",
        "Jeśli API odpowiada tylko wewnątrz compose (`127.0.0.1:8000` na hoście DS723+), "
        "tunel **cloudflared-ifg** musi wskazywać ten reachable origin (np. "
        "`http://127.0.0.1:8000`) albo współdzielić sieć Docker z kontenerem `api`. "
        "Ten krok **nie modyfikuje** config cloudflared — tylko diagnostyka.",
        "",
        "## Bezpieczeństwo",
        "",
        "- Nie wykonano `docker compose down -v`",
        "- Nie usuwano wolumenów",
        "- Dozwolone: `up -d db`, `up -d api worker`",
        "",
    ])
    RECOVERY_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nRaport zapisany: {RECOVERY_REPORT_PATH}")


def recover_prod(
    *,
    host: str,
    dry_run: bool = False,
    assume_yes: bool = False,
) -> int:
    print("IFG Guardian2 — recover-prod (DS723+)")
    if not assume_yes and not dry_run:
        answer = input("Uruchomić recovery na DS723+? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Anulowano.")
            return 1

    report = RecoveryReport(host=host, repo_path=DEFAULT_REMOTE_PATH)
    compose = _compose_cmd()

    _section("DIAGNOZA — git + compose")
    if dry_run:
        print(f"[dry-run] SSH {host} → {DEFAULT_REMOTE_PATH}")
        for cmd in (
            "git branch --show-current",
            "git rev-parse --short HEAD",
            "git status --short",
            f"{compose} config --services",
            f"{compose} ps -a",
        ):
            print(f"  > {cmd}")
        print("[dry-run] recovery steps: up -d db → wait → up -d api worker → health → cloudflared")
        return 0

    _, report.git_branch, _ = _ssh_capture(host, "git branch --show-current")
    _, report.git_head, _ = _ssh_capture(host, "git rev-parse --short HEAD")
    _, report.git_status, _ = _ssh_capture(host, "git status --short")
    _, report.compose_services, _ = _ssh_capture(host, f"{compose} config --services")
    report.ps_before = _remote_compose_ps(host, all_containers=True)

    print(f"branch: {report.git_branch}")
    print(f"HEAD:   {report.git_head}")
    print(f"services:\n{report.compose_services}")
    print(f"ps -a:\n{report.ps_before}")

    service_names = {line.strip() for line in report.compose_services.splitlines() if line.strip()}
    report.db_has_service = "db" in service_names

    if report.db_has_service:
        _section("RECOVERY — start db")
        code, out, err = _ssh_capture(host, f"{compose} up -d db")
        print(out or err)
        if code != 0:
            report.aborted = True
            report.abort_reason = f"`up -d db` exit {code}: {err or out}"
            report.ksef_connect_blocker = _infer_ksef_blocker(report)
            _write_recovery_report(report)
            return 1

        db_ready, db_state = _wait_for_service(
            host,
            "db",
            predicate=lambda s: service_state_is_running(s)
            and (service_state_is_healthy(s) or "running" in s.lower()),
            label="db",
        )
        report.db_ok = db_ready
        if not db_ready:
            report.aborted = True
            report.abort_reason = f"db nie healthy/running w {RECOVERY_WAIT_SECONDS}s (ostatni stan: {db_state})"
            report.ps_after = _remote_compose_ps(host, all_containers=True)
            report.ksef_connect_blocker = _infer_ksef_blocker(report)
            _write_recovery_report(report)
            print(f"\nABORT: {report.abort_reason}")
            return 1
        report.notes.append(f"db ready: {db_state}")
    else:
        report.notes.append("Brak usługi db w compose — pominięto up -d db")
        report.db_ok = False

    _section("RECOVERY — start api + worker")
    code, out, err = _ssh_capture(host, f"{compose} up -d api worker")
    print(out or err)
    if code != 0:
        report.aborted = True
        report.abort_reason = f"`up -d api worker` exit {code}: {err or out}"
        report.ps_after = _remote_compose_ps(host, all_containers=True)
        report.ksef_connect_blocker = _infer_ksef_blocker(report)
        _write_recovery_report(report)
        return 1

    api_ready, api_state = _wait_for_service(
        host,
        "api",
        predicate=lambda s: service_state_is_running(s) and not service_state_is_restarting(s),
        label="api",
    )
    if not api_ready:
        report.aborted = True
        report.abort_reason = f"api nie running w {RECOVERY_WAIT_SECONDS}s (ostatni stan: {api_state})"
        report.ps_after = _remote_compose_ps(host, all_containers=True)
        report.ksef_connect_blocker = _infer_ksef_blocker(report)
        _write_recovery_report(report)
        print(f"\nABORT: {report.abort_reason}")
        return 1
    report.notes.append(f"api running: {api_state}")

    report.ps_after = _remote_compose_ps(host, all_containers=True)
    worker_state = parse_compose_service_states(report.ps_after).get("worker", "")
    report.worker_ok = service_state_is_running(worker_state)

    _section("HEALTH CHECK")
    report.health_url = "http://127.0.0.1:8000/health"
    health_deadline = time.monotonic() + RECOVERY_WAIT_SECONDS
    while time.monotonic() < health_deadline:
        code, body, err = _ssh_capture(host, f"curl -sS -m 10 {report.health_url}")
        if code == 0 and body and ("ok" in body.lower() or '"status"' in body.lower()):
            report.health_body = body
            report.health_ok = True
            break
        time.sleep(RECOVERY_POLL_SECONDS)
    else:
        code, body, err = _ssh_capture(host, f"curl -sS -m 10 {report.health_url}")
        if code == 0 and body:
            report.health_body = body
            report.health_ok = "ok" in body.lower() or '"status"' in body.lower()
        else:
            report.notes.append(f"Host curl failed ({code}): {err or body}")
            inner_url = "http://127.0.0.1:8000/health"
            inner_cmd = f"{compose} exec -T api curl -sS -m 10 {inner_url}"
            code, body, err = _ssh_capture(host, inner_cmd)
            report.health_url = inner_url + " (via exec api)"
            report.health_body = body or err
            report.health_ok = code == 0 and bool(body) and (
                "ok" in body.lower() or '"status"' in body.lower()
            )

    report.api_ok = service_state_is_running(
        parse_compose_service_states(_remote_compose_ps(host)).get("api")
    ) and report.health_ok
    worker_state = parse_compose_service_states(_remote_compose_ps(host)).get("worker", "")
    report.worker_ok = service_state_is_running(worker_state)

    _, report.api_logs, _ = _ssh_capture(host, f"{compose} logs --tail=120 api")

    _section("CLOUDFLARED — diagnostyka (bez zmian config)")
    _, report.cloudflared_ps, _ = _ssh_capture(
        host,
        "sudo docker ps -a --filter name=cloudflared-ifg --format '{{.Names}}\t{{.Status}}\t{{.Ports}}'",
        cwd=None,
    )
    if not report.cloudflared_ps:
        _, report.cloudflared_ps, _ = _ssh_capture(
            host,
            "sudo docker ps -a | grep cloudflared-ifg || true",
            cwd=None,
        )
    _, report.cloudflared_logs, _ = _ssh_capture(
        host,
        "sudo docker logs --tail=80 cloudflared-ifg 2>&1 || true",
        cwd=None,
    )
    report.cloudflared_ok = bool(report.cloudflared_ps) and "up" in report.cloudflared_ps.lower()
    if report.cloudflared_logs and "error" in report.cloudflared_logs.lower():
        report.notes.append("cloudflared logs zawierają 'error' — sprawdź origin/ingress.")

    report.ksef_connect_blocker = _infer_ksef_blocker(report)
    _write_recovery_report(report)

    _section("PODSUMOWANIE")
    for line in report.summary_lines():
        print(line.replace("**", ""))

    if report.aborted or not report.health_ok:
        return 1
    return 0


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
        _remote_with_npm("cd frontend-react && npm ci && npm run build"),
        remote=True,
        host=host,
        dry_run=dry_run,
    )

    compose = _compose_cmd()
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
        description="IFG Guardian2 — deploy i recovery produkcji DS723+.",
        epilog=(
            "Przykłady:\n"
            "  python3 scripts/guardian2.py deploy-ksef --yes\n"
            "  python3 scripts/guardian2.py recover-prod --yes\n"
            "  python3 scripts/guardian2.py recover-prod --dry-run\n"
            "\n"
            "IFG_DS723_HOST — host SSH (domyślnie: ds723)\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command",
        choices=["deploy-ksef", "recover-prod"],
        help="Scenariusz: deploy KSeF lub recovery produkcji",
    )
    parser.add_argument("--dry-run", action="store_true", help="Wypisz polecenia bez wykonywania")
    parser.add_argument("--yes", action="store_true", help="Pomiń pytanie potwierdzające")
    parser.add_argument(
        "--remote-host",
        default=None,
        help=f"Host SSH (domyślnie IFG_DS723_HOST lub {DEFAULT_REMOTE_HOST})",
    )
    args = parser.parse_args()
    host = _resolve_host(args.remote_host)

    if args.command == "recover-prod":
        return recover_prod(host=host, dry_run=args.dry_run, assume_yes=args.yes)
    if args.command == "deploy-ksef":
        return deploy_ksef(dry_run=args.dry_run, assume_yes=args.yes, host=host)
    return 1


if __name__ == "__main__":
    sys.exit(main())
