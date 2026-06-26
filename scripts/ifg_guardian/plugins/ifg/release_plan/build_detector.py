from __future__ import annotations

from ifg_guardian.plugins.ifg.doctor.models import CheckResult, CheckStatus, DoctorState, OverallStatus
from ifg_guardian.plugins.ifg.release_plan.models import BuildDecision, RepositorySnapshot


def _find_check(doctor: DoctorState, check_id: str) -> CheckResult | None:
    for check in doctor.checks:
        if check.check_id == check_id:
            return check
    return None


def _check_failed(check: CheckResult | None) -> bool:
    if check is None:
        return False
    return check.status in (CheckStatus.FAIL, CheckStatus.CRITICAL)


def _check_warn_or_worse(check: CheckResult | None) -> bool:
    if check is None:
        return False
    return check.status != CheckStatus.PASS


def detect_build_decisions(
    doctor: DoctorState,
    repository: RepositorySnapshot,
) -> list[BuildDecision]:
    frontend_build = _find_check(doctor, "frontend.build_required")
    frontend_dist = _find_check(doctor, "frontend.dist_freshness")
    frontend_src = _find_check(doctor, "frontend.src_changed")
    backend_changes = _find_check(doctor, "backend.changes")
    backend_build = _find_check(doctor, "backend.build_required")
    alembic_pending = _find_check(doctor, "alembic.pending")

    frontend_required = (
        _check_failed(frontend_build)
        or _check_failed(frontend_dist)
        or bool(repository.frontend_changes)
        or _check_warn_or_worse(frontend_src)
    )
    frontend_reason = (
        frontend_build.message if frontend_build and _check_failed(frontend_build)
        else frontend_dist.message if frontend_dist and _check_failed(frontend_dist)
        else "frontend-react/src changes detected"
        if repository.frontend_changes
        else "dist freshness OK"
    )
    frontend_confidence = "HIGH" if _check_failed(frontend_build) or _check_failed(frontend_dist) else "MEDIUM"

    backend_required = (
        _check_failed(backend_build)
        or _check_failed(backend_changes)
        or bool(repository.backend_changes)
    )
    backend_reason = (
        backend_build.message if backend_build and _check_failed(backend_build)
        else backend_changes.message if backend_changes and _check_failed(backend_changes)
        else "app/ or alembic/ changes detected"
        if repository.backend_changes
        else "no backend changes"
    )
    backend_confidence = "HIGH" if _check_failed(backend_build) or bool(repository.backend_changes) else "MEDIUM"

    worker_required = backend_required
    worker_reason = (
        "worker shares api image rebuild when backend changes"
        if worker_required
        else "no worker rebuild needed"
    )

    migration_required = _check_failed(alembic_pending)
    migration_reason = (
        alembic_pending.message if alembic_pending else "schema at head"
    )

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
        BuildDecision("Frontend Build", frontend_required, frontend_reason, frontend_confidence),
        BuildDecision("Backend Build", backend_required, backend_reason, backend_confidence),
        BuildDecision("Worker Build", worker_required, worker_reason, backend_confidence),
        BuildDecision("Compose Restart", compose_restart, compose_reason, "HIGH"),
        BuildDecision("Migration Required", migration_required, migration_reason, "HIGH"),
        BuildDecision("Static Files", static_files, static_reason, frontend_confidence),
    ]


def analyze_repository_from_doctor(doctor: DoctorState) -> RepositorySnapshot:
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

    if backend and backend.details:
        snapshot.backend_changes = list(backend.details)
    if frontend_src and _check_warn_or_worse(frontend_src):
        snapshot.frontend_changes = ["frontend-react/src (uncommitted)"]

    return snapshot
