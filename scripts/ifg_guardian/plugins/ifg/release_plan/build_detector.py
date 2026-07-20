from __future__ import annotations

from ifg_guardian.config import ROOT
from ifg_guardian.plugins.ifg.deploy_decision.alembic_scope import AlembicDeploySnapshot
from ifg_guardian.plugins.ifg.deploy_decision.paths import dockerfile_paths
from ifg_guardian.plugins.ifg.doctor.models import CheckResult, CheckStatus, DoctorState, OverallStatus
from ifg_guardian.plugins.ifg.release_plan.models import BuildDecision, RepositorySnapshot


def _find_check(doctor: DoctorState, check_id: str) -> CheckResult | None:
    from ifg_guardian.plugins.ifg.doctor.models import CHECK_SEVERITY

    matches = [c for c in doctor.checks if c.check_id == check_id]
    if not matches:
        return None
    return max(matches, key=lambda check: CHECK_SEVERITY[check.status])


def _check_failed(check: CheckResult | None) -> bool:
    if check is None:
        return False
    return check.status in (CheckStatus.FAIL, CheckStatus.CRITICAL)


def _check_warn_or_worse(check: CheckResult | None) -> bool:
    if check is None:
        return False
    return check.status != CheckStatus.PASS


def _format_trigger_files(files: list[str], *, limit: int = 8) -> str:
    if not files:
        return ""
    shown = files[:limit]
    lines = "\n".join(f"- {path}" for path in shown)
    if len(files) > limit:
        lines += f"\n- ... (+{len(files) - limit} more)"
    return lines


def _dockerfile_present() -> bool:
    return any((ROOT / path).is_file() for path in dockerfile_paths())


def detect_build_decisions(
    doctor: DoctorState,
    repository: RepositorySnapshot,
    *,
    alembic: AlembicDeploySnapshot | None = None,
) -> list[BuildDecision]:
    frontend_build = _find_check(doctor, "frontend.build_required")
    frontend_dist = _find_check(doctor, "frontend.dist_freshness")
    frontend_src = _find_check(doctor, "frontend.src_changed")
    backend_changes = _find_check(doctor, "backend.changes")
    backend_build = _find_check(doctor, "backend.build_required")
    backend_dockerfile = _find_check(doctor, "backend.dockerfile")
    alembic_pending = _find_check(doctor, "alembic.pending")
    image_gate = _find_check(doctor, "backend.image_rebuild_gate")

    frontend_files = list(repository.frontend_changes)
    frontend_required = (
        _check_failed(frontend_build)
        or _check_failed(frontend_dist)
        or bool(frontend_files)
        or _check_warn_or_worse(frontend_src)
    )
    if frontend_files:
        frontend_reason = "Frontend build required:\n" + _format_trigger_files(frontend_files)
    elif frontend_build and _check_failed(frontend_build):
        frontend_reason = frontend_build.message
    elif frontend_dist and _check_failed(frontend_dist):
        frontend_reason = frontend_dist.message
    else:
        frontend_reason = "no frontend changes detected"
    frontend_confidence = "HIGH" if frontend_required else "MEDIUM"

    backend_files = list(repository.backend_changes)
    dockerfile_missing = _check_failed(backend_dockerfile)

    if dockerfile_missing:
        backend_required = False
        backend_confidence = "BLOCKED"
        if backend_files:
            backend_reason = (
                "Backend build blocked — Dockerfile missing:\n"
                + _format_trigger_files(backend_files)
            )
        else:
            backend_reason = backend_dockerfile.message if backend_dockerfile else "Dockerfile missing"
    else:
        image_gate_requires = False
        image_gate_fail = False
        if image_gate is not None:
            msg = (image_gate.message or "").upper()
            if image_gate.status == CheckStatus.FAIL or msg.startswith("FAIL:"):
                image_gate_fail = True
            elif "REQUIRE_REBUILD" in msg:
                image_gate_requires = True
        backend_required = (
            bool(backend_files)
            or _check_warn_or_worse(backend_build)
            or _check_warn_or_worse(backend_changes)
            or image_gate_requires
            or image_gate_fail
        )
        if image_gate_fail:
            backend_reason = image_gate.message if image_gate else "image rebuild gate FAIL"
            backend_confidence = "BLOCKED"
            backend_required = False
        elif image_gate_requires and image_gate:
            backend_reason = image_gate.message
            backend_confidence = "HIGH"
        elif backend_files:
            backend_reason = "Backend build required:\n" + _format_trigger_files(backend_files)
        elif backend_build and _check_warn_or_worse(backend_build):
            backend_reason = backend_build.message
        elif backend_changes and _check_warn_or_worse(backend_changes):
            backend_reason = backend_changes.message
        else:
            backend_reason = "no backend changes detected"
        if not image_gate_fail:
            backend_confidence = "HIGH" if backend_required else "MEDIUM"

    worker_required = backend_required and not dockerfile_missing
    if worker_required:
        worker_reason = "Worker build required:\n" + _format_trigger_files(backend_files or ["shared api image"])
        worker_confidence = backend_confidence
    elif dockerfile_missing and backend_files:
        worker_reason = "Worker build blocked — Dockerfile missing"
        worker_confidence = "BLOCKED"
    else:
        worker_reason = "no worker rebuild needed"
        worker_confidence = "MEDIUM"

    migration_required = False
    migration_reason = "schema at head"
    migration_files: list[str] = []
    if alembic is not None:
        if not alembic.remote_available:
            migration_required = True
            migration_reason = (
                "Migration verification required — remote revision unavailable: "
                f"{alembic.remote_error or 'DS723+ unreachable'}"
            )
        else:
            migration_required = alembic.migration_required
            if migration_required:
                pending = alembic.pending_revisions or ([alembic.local_head] if alembic.local_head else [])
                migration_files = [f"alembic/versions/{rev}" for rev in pending]
                migration_reason = (
                    "Migration required:\n"
                    f"- remote={alembic.remote_revision or 'unknown'}\n"
                    f"- local_head={alembic.local_head or 'unknown'}\n"
                    f"- pending={', '.join(pending) if pending else 'yes'}"
                )
            else:
                migration_reason = (
                    f"schema at head (remote={alembic.remote_revision or 'n/a'}, "
                    f"local={alembic.local_head or 'n/a'})"
                )
    elif _check_failed(alembic_pending):
        migration_required = True
        migration_reason = alembic_pending.message if alembic_pending else "pending migration detected"

    compose_restart = frontend_required or backend_required or migration_required
    compose_reason = (
        "services must restart after image/build/migration changes"
        if compose_restart
        else "no restart required beyond routine health check"
    )

    static_files = frontend_required
    static_reason = (
        "frontend dist must be rebuilt and synced to DS723+"
        if static_files
        else "static assets unchanged"
    )

    return [
        BuildDecision(
            "Frontend Build",
            frontend_required,
            frontend_reason,
            frontend_confidence,
            trigger_files=frontend_files,
        ),
        BuildDecision(
            "Backend Build",
            backend_required,
            backend_reason,
            backend_confidence,
            trigger_files=backend_files,
        ),
        BuildDecision(
            "Worker Build",
            worker_required,
            worker_reason,
            worker_confidence,
            trigger_files=backend_files,
        ),
        BuildDecision("Compose Restart", compose_restart, compose_reason, "HIGH"),
        BuildDecision(
            "Migration Required",
            migration_required,
            migration_reason,
            "HIGH",
            trigger_files=migration_files,
        ),
        BuildDecision("Static Files", static_files, static_reason, frontend_confidence, trigger_files=frontend_files),
    ]


def analyze_repository_from_doctor(
    doctor: DoctorState,
    *,
    deploy_changed_files: list[str] | None = None,
    alembic: AlembicDeploySnapshot | None = None,
) -> RepositorySnapshot:
    from ifg_guardian.plugins.ifg.deploy_decision.git_scope import split_deploy_changes

    snapshot = RepositorySnapshot()
    branch = _find_check(doctor, "env.branch")
    status = _find_check(doctor, "env.git_status")
    ahead_behind = _find_check(doctor, "env.ahead_behind")
    backend = _find_check(doctor, "backend.changes")
    frontend_src = _find_check(doctor, "frontend.src_changed")

    if branch:
        snapshot.branch = branch.message.replace("on production (", "").split(")")[0] if "on production" in branch.message else branch.message
        if "`" in branch.message:
            parts = branch.message.split("`")
            if len(parts) >= 2:
                snapshot.branch = parts[1]

    if status:
        snapshot.dirty = "dirty" in status.message.lower()

    if ahead_behind and "ahead=" in ahead_behind.message:
        try:
            fragment = ahead_behind.message.split("ahead=")[1]
            ahead_s, behind_part = fragment.split(", behind=")
            snapshot.ahead = int(ahead_s)
            snapshot.behind = int(behind_part.split()[0])
        except (ValueError, IndexError):
            pass

    all_changes = list(deploy_changed_files or [])
    if backend and backend.details:
        for path in backend.details:
            if path not in all_changes:
                all_changes.append(path)
    if frontend_src and frontend_src.details:
        for path in frontend_src.details:
            if path not in all_changes:
                all_changes.append(path)

    backend_paths, frontend_paths = split_deploy_changes(all_changes)
    snapshot.deploy_changed_files = all_changes
    snapshot.backend_changes = backend_paths
    snapshot.frontend_changes = frontend_paths

    if alembic is not None:
        snapshot.alembic.local_head = alembic.local_head
        snapshot.alembic.local_current = alembic.local_current
        snapshot.alembic.remote_revision = alembic.remote_revision
        snapshot.alembic.pending_revisions = list(alembic.pending_revisions)
        snapshot.alembic.remote_available = alembic.remote_available

    return snapshot
