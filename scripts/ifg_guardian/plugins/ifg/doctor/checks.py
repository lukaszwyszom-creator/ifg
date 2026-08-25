from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

from ifg_guardian.config import COMPOSE_FILE, DEFAULT_REMOTE_PATH, ROOT, TARGET_BRANCH
from ifg_guardian.core.compose import compose_services_healthy, parse_compose_service_states, remote_compose_ps
from ifg_guardian.core.git import git, porcelain_is_dirty, resolve_ds723_host
from ifg_guardian.core.repo_audit.models import RepoAuditState
from ifg_guardian.core.risk import FileCategory
from ifg_guardian.core.ssh import remote_git, ssh
from ifg_guardian.modules.frontend import (
    check_frontend_dist_freshness,
    check_frontend_worktree_requires_build,
    frontend_src_dirty_max_mtime,
)
from ifg_guardian.plugins.ifg.doctor.models import CheckResult, CheckStatus

GROUP = "environment"
PRODUCTION_REQUIRED_KEYS = (
    "DATABASE_URL",
    "JWT_SECRET_KEY",
    "POSTGRES_PASSWORD",
    "SELLER_NIP",
    "SELLER_NAME",
)


def _run(cmd: list[str], *, cwd: Path | None = None) -> tuple[int, str]:
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        output = (result.stdout or result.stderr or "").strip()
        return result.returncode, output
    except OSError as exc:
        return 1, str(exc)


def _tool_version(name: str, args: list[str]) -> CheckResult:
    path = shutil.which(name)
    if not path:
        return CheckResult(
            f"env.{name}",
            GROUP,
            name,
            CheckStatus.WARN,
            f"{name} not found in PATH",
        )
    code, output = _run([path, *args])
    if code != 0:
        return CheckResult(
            f"env.{name}",
            GROUP,
            name,
            CheckStatus.WARN,
            f"{name} unavailable: {output or f'exit {code}'}",
        )
    return CheckResult(
        f"env.{name}",
        GROUP,
        name,
        CheckStatus.PASS,
        output.splitlines()[0] if output else name,
    )


def run_environment_checks(*, do_fetch: bool = False) -> list[CheckResult]:
    checks: list[CheckResult] = []

    if do_fetch:
        code, output = _run(["git", "fetch", "origin", TARGET_BRANCH, "--quiet"])
        if code != 0:
            checks.append(
                CheckResult(
                    "env.git_fetch",
                    GROUP,
                    "git fetch",
                    CheckStatus.WARN,
                    f"fetch failed: {output or f'exit {code}'}",
                )
            )

    try:
        branch = git("branch", "--show-current")
        porcelain = git("status", "--porcelain")
        head = git("rev-parse", "--short", "HEAD")
    except RuntimeError as exc:
        checks.append(
            CheckResult(
                "env.git",
                GROUP,
                "git",
                CheckStatus.CRITICAL,
                f"cannot read repository: {exc}",
            )
        )
        return checks

    if branch == TARGET_BRANCH:
        checks.append(
            CheckResult(
                "env.branch",
                GROUP,
                "branch",
                CheckStatus.PASS,
                f"on {TARGET_BRANCH} ({head})",
            )
        )
    elif not branch.strip():
        # Detached HEAD is expected for immutable commit snapshots / release clones.
        checks.append(
            CheckResult(
                "env.branch",
                GROUP,
                "branch",
                CheckStatus.WARN,
                f"detached HEAD at {head} — immutable snapshot builds pin commit explicitly",
            )
        )
    else:
        checks.append(
            CheckResult(
                "env.branch",
                GROUP,
                "branch",
                CheckStatus.FAIL,
                f"on `{branch}` — expected `{TARGET_BRANCH}`",
            )
        )

    dirty = porcelain_is_dirty(porcelain)
    checks.append(
        CheckResult(
            "env.git_status",
            GROUP,
            "git status",
            CheckStatus.WARN if dirty else CheckStatus.PASS,
            "working tree dirty" if dirty else "working tree clean",
        )
    )

    try:
        counts = git("rev-list", "--left-right", "--count", f"HEAD...origin/{TARGET_BRANCH}")
        ahead_s, behind_s = counts.split("\t", 1)
        ahead, behind = int(ahead_s), int(behind_s)
    except RuntimeError:
        ahead, behind = 0, 0

    if ahead == 0 and behind == 0:
        sync_status = CheckStatus.PASS
        sync_msg = f"synced with origin/{TARGET_BRANCH}"
    else:
        sync_status = CheckStatus.WARN
        sync_msg = f"ahead={ahead}, behind={behind} vs origin/{TARGET_BRANCH}"
    checks.append(
        CheckResult(
            "env.ahead_behind",
            GROUP,
            "ahead/behind",
            sync_status,
            sync_msg,
        )
    )

    py_code, py_out = _run([sys.executable, "--version"])
    checks.append(
        CheckResult(
            "env.python",
            GROUP,
            "python",
            CheckStatus.PASS if py_code == 0 else CheckStatus.WARN,
            py_out.splitlines()[0] if py_out else sys.executable,
        )
    )
    checks.append(_tool_version("node", ["--version"]))
    checks.append(_tool_version("npm", ["--version"]))
    return checks


def run_repository_checks(audit: RepoAuditState | None) -> list[CheckResult]:
    group = "repository"
    checks: list[CheckResult] = []

    if audit is None:
        checks.append(
            CheckResult(
                "repo.audit",
                group,
                "repo audit",
                CheckStatus.CRITICAL,
                "repo audit workflow did not produce results",
            )
        )
        return checks

    checks.append(
        CheckResult(
            "repo.audit",
            group,
            "repo audit",
            CheckStatus.PASS,
            f"overall risk {audit.overall_risk.value}, {len(audit.files)} classified file(s)",
        )
    )

    if audit.dirty:
        checks.append(
            CheckResult(
                "repo.dirty",
                group,
                "dirty repo",
                CheckStatus.WARN,
                "working tree has tracked/untracked changes",
            )
        )
    else:
        checks.append(
            CheckResult(
                "repo.dirty",
                group,
                "dirty repo",
                CheckStatus.PASS,
                "working tree clean (audit)",
            )
        )

    eol_unknown = [f.path for f in audit.files if f.category == FileCategory.UNKNOWN_LINE_ENDINGS]
    eol_crlf = [f.path for f in audit.files if f.category == FileCategory.CRLF_ONLY]
    if eol_crlf:
        checks.append(
            CheckResult(
                "repo.line_endings.crlf",
                group,
                "line endings",
                CheckStatus.WARN,
                f"{len(eol_crlf)} CRLF-only file(s)",
                details=eol_crlf[:5],
            )
        )
    if eol_unknown:
        checks.append(
            CheckResult(
                "repo.line_endings.unknown",
                group,
                "line endings",
                CheckStatus.WARN,
                f"{len(eol_unknown)} file(s) with unknown line endings",
                details=eol_unknown[:5],
            )
        )
    if not eol_crlf and not eol_unknown:
        checks.append(
            CheckResult(
                "repo.line_endings",
                group,
                "line endings",
                CheckStatus.PASS,
                "no line-ending issues detected",
            )
        )

    ignored = [f.path for f in audit.files if f.category == FileCategory.IGNORE]
    if ignored:
        checks.append(
            CheckResult(
                "repo.ignored_tracked",
                group,
                "ignored files",
                CheckStatus.WARN,
                f"{len(ignored)} tracked/ignored conflict(s)",
                details=ignored[:5],
            )
        )
    else:
        checks.append(
            CheckResult(
                "repo.ignored_tracked",
                group,
                "ignored files",
                CheckStatus.PASS,
                "no tracked ignore conflicts",
            )
        )

    blockers = [f.path for f in audit.files if f.category == FileCategory.DEPLOY_BLOCKER]
    if blockers:
        checks.append(
            CheckResult(
                "repo.deploy_blockers",
                group,
                "deploy blockers",
                CheckStatus.CRITICAL,
                f"{len(blockers)} deploy blocker(s)",
                details=blockers,
            )
        )

    return checks


def run_frontend_checks() -> list[CheckResult]:
    group = "frontend"
    checks: list[CheckResult] = []

    dirty_mtime = frontend_src_dirty_max_mtime()
    if dirty_mtime is None:
        checks.append(
            CheckResult(
                "frontend.src_changed",
                group,
                "frontend-react/src",
                CheckStatus.PASS,
                "no uncommitted src changes",
            )
        )
    else:
        checks.append(
            CheckResult(
                "frontend.src_changed",
                group,
                "frontend-react/src",
                CheckStatus.WARN,
                "uncommitted changes in frontend-react/src",
            )
        )

    build_ok, build_msg = check_frontend_worktree_requires_build()
    checks.append(
        CheckResult(
            "frontend.build_required",
            group,
            "npm run build",
            CheckStatus.PASS if build_ok else CheckStatus.WARN,
            build_msg if build_ok else f"BUILD_REQUIRED: {build_msg}",
        )
    )

    dist_ok, dist_msg = check_frontend_dist_freshness()
    checks.append(
        CheckResult(
            "frontend.dist_freshness",
            group,
            "dist freshness",
            CheckStatus.PASS if dist_ok else CheckStatus.WARN,
            dist_msg if dist_ok else f"BUILD_REQUIRED: {dist_msg}",
        )
    )
    return checks


def run_backend_checks(
    audit: RepoAuditState | None,
    *,
    remote_host: str | None = None,
    remote_path: str | None = None,
    defer_remote_image_verify: bool = True,
) -> list[CheckResult]:
    from ifg_guardian.plugins.ifg.deploy_decision.git_scope import list_deploy_changed_files, split_deploy_changes
    from ifg_guardian.plugins.ifg.deploy_decision.image_gate_resolve import resolve_image_rebuild_gate
    from ifg_guardian.plugins.ifg.deploy_decision.image_rebuild_gate import ImageRebuildDecision
    from ifg_guardian.plugins.ifg.deploy_decision.paths import dockerfile_paths

    group = "backend"
    checks: list[CheckResult] = []

    dockerfile_ok = any((ROOT / path).is_file() for path in dockerfile_paths())
    if not dockerfile_ok:
        checks.append(
            CheckResult(
                "backend.dockerfile",
                group,
                "Dockerfile",
                CheckStatus.FAIL,
                "missing Dockerfile (docker/Dockerfile or Dockerfile)",
                scope="local",
            )
        )

    deploy_files = list_deploy_changed_files()
    backend_files, _ = split_deploy_changes(deploy_files)

    gate = resolve_image_rebuild_gate(
        remote_host=remote_host,
        remote_path=remote_path,
        defer_remote_verify=defer_remote_image_verify,
    )
    checks.append(
        CheckResult(
            "backend.image_rebuild_gate",
            group,
            "image rebuild gate",
            CheckStatus.FAIL if gate.is_failure else CheckStatus.PASS,
            f"{gate.decision.value}: {gate.reason}",
            details=list(gate.trigger_files[:12]),
            scope="local",
        )
    )

    if gate.is_failure:
        checks.append(
            CheckResult(
                "backend.changes",
                group,
                "backend changes",
                CheckStatus.FAIL,
                gate.reason,
                details=list(gate.trigger_files[:10]),
                scope="local",
            )
        )
        checks.append(
            CheckResult(
                "backend.build_required",
                group,
                "build required",
                CheckStatus.FAIL,
                "image rebuild gate blocked deploy — docker build SKIP forbidden",
                details=list(gate.trigger_files[:10]),
                scope="local",
            )
        )
        return checks

    if gate.decision == ImageRebuildDecision.REQUIRE_REBUILD:
        trigger = gate.trigger_files or backend_files
        checks.append(
            CheckResult(
                "backend.changes",
                group,
                "backend changes",
                CheckStatus.WARN,
                gate.reason,
                details=list(trigger[:10]),
                scope="local",
            )
        )
        checks.append(
            CheckResult(
                "backend.build_required",
                group,
                "build required",
                CheckStatus.WARN if dockerfile_ok else CheckStatus.FAIL,
                (
                    "IMAGE_REBUILD_REQUIRED: rebuild api/worker required before deploy "
                    "(image rebuild gate)"
                    if dockerfile_ok
                    else "image rebuild required but Dockerfile missing — deploy blocked"
                ),
                details=list(trigger[:10]),
                scope="local",
            )
        )
        return checks

    # ALLOW_SKIP
    if not backend_files:
        checks.append(
            CheckResult(
                "backend.changes",
                group,
                "backend changes",
                CheckStatus.PASS,
                "no backend changes vs origin/production",
                scope="local",
            )
        )
    else:
        # Backend paths poza image-context (np. worker/ bez COPY) — informacyjnie
        checks.append(
            CheckResult(
                "backend.changes",
                group,
                "backend changes",
                CheckStatus.WARN,
                f"{len(backend_files)} backend change(s); image gate ALLOW_SKIP",
                details=list(backend_files[:10]),
                scope="local",
            )
        )
    checks.append(
        CheckResult(
            "backend.build_required",
            group,
            "build required",
            CheckStatus.PASS,
            gate.reason,
            scope="local",
        )
    )
    return checks


def run_docker_checks(*, remote_host: str, remote_path: str, dry_run: bool) -> list[CheckResult]:
    group = "docker"
    checks: list[CheckResult] = []
    compose_path = ROOT / COMPOSE_FILE

    if compose_path.is_file():
        code, output = _run(
            ["docker", "compose", "-f", str(compose_path), "config", "--quiet"],
        )
        if code == 0:
            checks.append(
                CheckResult(
                    "docker.compose_config",
                    group,
                    "compose config",
                    CheckStatus.PASS,
                    "compose file valid",
                )
            )
        elif ".env.production" in (output or ""):
            # Secret stays on DS723+ / operator input — never required inside snapshot.
            checks.append(
                CheckResult(
                    "docker.compose_config",
                    group,
                    "compose config",
                    CheckStatus.WARN,
                    "OPERATOR_INPUT: .env.production missing locally "
                    "(expected only on DS723+; not part of immutable snapshot)",
                )
            )
        else:
            checks.append(
                CheckResult(
                    "docker.compose_config",
                    group,
                    "compose config",
                    CheckStatus.FAIL,
                    output or f"exit {code}",
                )
            )
    else:
        checks.append(
            CheckResult(
                "docker.compose_config",
                group,
                "compose config",
                CheckStatus.FAIL,
                f"missing {COMPOSE_FILE}",
            )
        )

    if dry_run:
        checks.append(
            CheckResult(
                "docker.remote",
                group,
                "remote containers",
                CheckStatus.WARN,
                "skipped in dry-run (would inspect DS723+ via SSH)",
            )
        )
        return checks

    host = resolve_ds723_host(remote_host)
    try:
        compose_ps = remote_compose_ps(host, remote_path)
        states = parse_compose_service_states(compose_ps)
        ok, problems = compose_services_healthy(states)
        checks.append(
            CheckResult(
                "docker.containers",
                group,
                "containers",
                CheckStatus.PASS if ok else CheckStatus.FAIL,
                "api/worker/db running" if ok else "; ".join(problems),
                details=problems,
            )
        )
        checks.append(
            CheckResult(
                "docker.images",
                group,
                "images",
                CheckStatus.PASS,
                f"compose ps returned {len(states)} service(s)",
            )
        )
    except RuntimeError as exc:
        checks.append(
            CheckResult(
                "docker.remote",
                group,
                "remote docker",
                CheckStatus.FAIL,
                f"DS723+ unreachable: {exc}",
                scope="remote",
            )
        )
    return checks


def run_database_checks(*, dry_run: bool) -> list[CheckResult]:
    group = "database"
    checks: list[CheckResult] = []
    compose_text = (ROOT / COMPOSE_FILE).read_text(encoding="utf-8") if (ROOT / COMPOSE_FILE).is_file() else ""

    if "db:" in compose_text or "postgres" in compose_text.lower():
        checks.append(
            CheckResult(
                "database.postgres",
                group,
                "postgres",
                CheckStatus.PASS,
                "postgres service declared in compose",
            )
        )
    else:
        checks.append(
            CheckResult(
                "database.postgres",
                group,
                "postgres",
                CheckStatus.FAIL,
                "postgres service not found in compose file",
            )
        )

    if dry_run:
        checks.append(
            CheckResult(
                "database.connection",
                group,
                "connection",
                CheckStatus.WARN,
                "skipped in dry-run",
            )
        )
    else:
        code, output = _run(
            [sys.executable, "-c", "import psycopg; print('ok')"],
        )
        checks.append(
            CheckResult(
                "database.connection",
                group,
                "connection",
                CheckStatus.PASS if code == 0 else CheckStatus.WARN,
                "psycopg available locally" if code == 0 else f"psycopg check: {output}",
            )
        )

    backup_doc = ROOT / "docs" / "migracja_mac_mini.md"
    checks.append(
        CheckResult(
            "database.backup_policy",
            group,
            "backup policy",
            CheckStatus.PASS if backup_doc.is_file() else CheckStatus.WARN,
            "backup documented in docs/migracja_mac_mini.md"
            if backup_doc.is_file()
            else "no backup policy documentation found",
        )
    )
    return checks


def run_alembic_checks(
    *,
    remote_host: str = "",
    remote_path: str = "",
    dry_run: bool = False,
) -> list[CheckResult]:
    from ifg_guardian.plugins.ifg.deploy_decision.alembic_scope import build_alembic_deploy_snapshot

    group = "alembic"
    checks: list[CheckResult] = []
    snapshot = build_alembic_deploy_snapshot(
        remote_host=remote_host or None,
        remote_path=remote_path or DEFAULT_REMOTE_PATH,
        dry_run=dry_run,
    )

    if snapshot.local_head:
        checks.append(
            CheckResult(
                "alembic.head",
                group,
                "local head",
                CheckStatus.PASS,
                snapshot.local_head,
                scope="local",
            )
        )
    else:
        checks.append(
            CheckResult(
                "alembic.head",
                group,
                "local head",
                CheckStatus.WARN,
                "alembic heads unavailable locally",
                scope="local",
            )
        )

    if snapshot.local_current_available:
        checks.append(
            CheckResult(
                "alembic.current",
                group,
                "local current",
                CheckStatus.PASS,
                snapshot.local_current or "current revision read",
                scope="local",
            )
        )
    else:
        checks.append(
            CheckResult(
                "alembic.current",
                group,
                "local current",
                CheckStatus.WARN,
                snapshot.local_current or "local DATABASE_URL unavailable — using remote revision",
                scope="local",
            )
        )

    if dry_run:
        checks.append(
            CheckResult(
                "alembic.remote_revision",
                group,
                "remote revision",
                CheckStatus.WARN,
                "skipped in dry-run",
                scope="remote",
            )
        )
        checks.append(
            CheckResult(
                "alembic.pending",
                group,
                "pending migration",
                CheckStatus.WARN,
                "remote comparison skipped in dry-run",
                scope="remote",
            )
        )
        return checks

    if not snapshot.remote_available:
        checks.append(
            CheckResult(
                "alembic.remote_revision",
                group,
                "remote revision",
                CheckStatus.FAIL,
                snapshot.remote_error or "cannot read production revision on DS723+",
                scope="remote",
            )
        )
        checks.append(
            CheckResult(
                "alembic.pending",
                group,
                "pending migration",
                CheckStatus.FAIL,
                "cannot verify migration state without remote revision",
                scope="remote",
            )
        )
        return checks

    checks.append(
        CheckResult(
            "alembic.remote_revision",
            group,
            "remote revision",
            CheckStatus.PASS,
            snapshot.remote_revision or "empty",
            scope="remote",
        )
    )

    if snapshot.migration_required:
        pending = snapshot.pending_revisions
        message = (
            f"remote={snapshot.remote_revision}, local_head={snapshot.local_head}, "
            f"pending={', '.join(pending) if pending else 'yes'}"
        )
        checks.append(
            CheckResult(
                "alembic.pending",
                group,
                "pending migration",
                CheckStatus.FAIL,
                message,
                details=pending,
                scope="remote",
            )
        )
    else:
        checks.append(
            CheckResult(
                "alembic.pending",
                group,
                "pending migration",
                CheckStatus.PASS,
                f"schema at head (remote={snapshot.remote_revision}, local={snapshot.local_head})",
                scope="remote",
            )
        )
    return checks


def _extract_revision(text: str) -> str:
    match = re.search(r"([0-9a-f]{8,})", text)
    return match.group(1) if match else text.strip().split()[0] if text.strip() else ""


def run_configuration_checks() -> list[CheckResult]:
    group = "configuration"
    checks: list[CheckResult] = []
    template = ROOT / ".env.production.template"
    example = ROOT / ".env.example"
    production = ROOT / ".env.production"

    checks.append(
        CheckResult(
            "config.template",
            group,
            ".env.production.template",
            CheckStatus.PASS if template.is_file() else CheckStatus.WARN,
            "template present" if template.is_file() else "template missing",
        )
    )

    if production.is_file():
        checks.append(
            CheckResult(
                "config.production_file",
                group,
                ".env.production",
                CheckStatus.PASS,
                ".env.production present locally",
            )
        )
        env_values = _parse_env_file(production)
    else:
        checks.append(
            CheckResult(
                "config.production_file",
                group,
                ".env.production",
                CheckStatus.WARN,
                ".env.production not found locally (may exist only on DS723+)",
            )
        )
        env_values = {}

    missing = [key for key in PRODUCTION_REQUIRED_KEYS if not env_values.get(key)]
    if missing and production.is_file():
        checks.append(
            CheckResult(
                "config.required_vars",
                group,
                "required variables",
                CheckStatus.CRITICAL if "JWT_SECRET_KEY" in missing else CheckStatus.FAIL,
                f"missing or empty: {', '.join(missing)}",
                details=missing,
            )
        )
    elif example.is_file():
        checks.append(
            CheckResult(
                "config.required_vars",
                group,
                "required variables",
                CheckStatus.PASS,
                "required keys documented in .env.example",
            )
        )
    return checks


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def run_health_checks(*, remote_host: str, remote_path: str, dry_run: bool) -> list[CheckResult]:
    group = "health"
    if dry_run:
        return [
            CheckResult(
                "health.endpoint",
                group,
                "/health",
                CheckStatus.WARN,
                "skipped in dry-run (would curl DS723+ /health)",
            )
        ]

    host = resolve_ds723_host(remote_host)
    health_url = "http://127.0.0.1:8000/health"
    try:
        body = ssh(host, f"curl -sS -m 10 {health_url}")
        ok = bool(body) and ("ok" in body.lower() or '"status"' in body.lower())
        return [
            CheckResult(
                "health.endpoint",
                group,
                "/health",
                CheckStatus.PASS if ok else CheckStatus.FAIL,
                body[:200] if body else "empty response",
            )
        ]
    except RuntimeError as exc:
        return [
            CheckResult(
                "health.endpoint",
                group,
                "/health",
                CheckStatus.WARN,
                f"health check unavailable: {exc}",
            )
        ]
