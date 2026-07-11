"""Production maintenance mode — controlled stack stop/start via Guardian."""
from __future__ import annotations

from datetime import UTC, datetime

from ifg_guardian.config import DEFAULT_REMOTE_PATH, ROOT
from ifg_guardian.core.execution_guard import enforce_mutating_live_orchestration
from ifg_guardian.core.git import resolve_ds723_host
from ifg_guardian.core.prod_health_collector import (
    collect_prod_health_snapshot,
    remote_compose_stop,
    wait_stack_healthy,
)
from ifg_guardian.core.runtime_audit import RuntimeAuditSession
from ifg_guardian.core.runtime_maintenance import (
    MaintenanceMarker,
    clear_maintenance_marker,
    load_maintenance_marker,
    maintenance_is_active,
    save_maintenance_marker,
)
from ifg_guardian.core.runtime_status import ProductionRuntimeStatus
from ifg_guardian.core.ssh import remote_git


def _git_short_head() -> str:
    import subprocess

    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return ""


def run_prod_maintenance_status() -> int:
    marker = load_maintenance_marker()
    print("IFG Guardian — prod maintenance status")
    print("=" * 40)
    if marker is None:
        print("Status: inactive")
        return 0
    print("Status: active")
    print(f"Started (UTC): {marker.started_at_utc}")
    print(f"Operation ID: {marker.operation_id}")
    print(f"Actor: {marker.actor}@{marker.hostname}")
    print(f"Reason: {marker.reason or '(none)'}")
    print(f"Commit: {marker.commit or '(unknown)'}")
    return 0


def run_prod_maintenance_start(
    *,
    reason: str | None = None,
    assume_yes: bool = False,
    dry_run: bool = False,
    remote_host: str | None = None,
    remote_path: str = DEFAULT_REMOTE_PATH,
) -> int:
    try:
        enforce_mutating_live_orchestration(dry_run=dry_run, root=ROOT)
    except RuntimeError as exc:
        print(f"\n❌ prod maintenance start blocked: {exc}")
        return 1

    if not assume_yes and not dry_run:
        print("prod maintenance start wymaga --yes (operacja mutująca).", flush=True)
        return 1

    host = resolve_ds723_host(remote_host)
    print("IFG Guardian — prod maintenance start")
    print("=" * 40)

    if maintenance_is_active():
        print("❌ Maintenance already active — run `guardian prod maintenance status`")
        return 1

    snapshot = collect_prod_health_snapshot(host, remote_path=remote_path)
    if not snapshot.reachable:
        print(f"❌ Precheck failed: {snapshot.error}")
        return 1

    runtime = snapshot.runtime.status
    if runtime not in (ProductionRuntimeStatus.PRODUCTION_RUNNING, ProductionRuntimeStatus.PRODUCTION_DEGRADED):
        print(f"❌ Unsafe runtime for maintenance start: {runtime.value}")
        for item in snapshot.runtime.problems:
            print(f"  • {item}")
        return 1

    audit = RuntimeAuditSession(
        workflow="prod.maintenance.start",
        event_type="maintenance_start",
        reason=reason,
        target=remote_path,
    )

    if dry_run:
        print("[dry-run] Would write maintenance marker, then compose stop")
        print(f"  reason: {reason or '(none)'}")
        audit.started(extra={"dry_run": True})
        audit.completed(result="dry_run")
        return 0

    started_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    from ifg_guardian.core.runtime_audit import AuditActor

    actor = AuditActor.current()
    marker = MaintenanceMarker(
        active=True,
        operation_id=audit.operation_id,
        started_at_utc=started_at,
        actor=actor.user,
        hostname=actor.hostname,
        reason=reason,
        commit=_git_short_head(),
    )

    try:
        audit.started()
        save_maintenance_marker(marker)
        remote_compose_stop(host, remote_path)
        post = collect_prod_health_snapshot(host, remote_path=remote_path, maintenance_active=True)
        if post.runtime.status not in (
            ProductionRuntimeStatus.PRODUCTION_MAINTENANCE,
            ProductionRuntimeStatus.PRODUCTION_STOPPED,
        ):
            audit.failed(f"stack not stopped after compose stop: {post.runtime.status.value}")
            print(f"❌ Stack not fully stopped: {post.runtime.status.value}")
            return 1
        audit.completed(result="stopped", extra={"runtime": post.runtime.status.value})
        print("✅ Maintenance started — stack stopped under marker")
        print(f"Operation ID: {audit.operation_id}")
        return 0
    except RuntimeError as exc:
        clear_maintenance_marker()
        audit.failed(str(exc))
        print(f"❌ Maintenance start failed: {exc}")
        return 1


def run_prod_maintenance_end(
    *,
    assume_yes: bool = False,
    dry_run: bool = False,
    remote_host: str | None = None,
    remote_path: str = DEFAULT_REMOTE_PATH,
) -> int:
    try:
        enforce_mutating_live_orchestration(dry_run=dry_run, root=ROOT)
    except RuntimeError as exc:
        print(f"\n❌ prod maintenance end blocked: {exc}")
        return 1

    if not assume_yes and not dry_run:
        print("prod maintenance end wymaga --yes (operacja mutująca).", flush=True)
        return 1

    marker = load_maintenance_marker()
    if marker is None:
        print("❌ No active maintenance marker")
        return 1

    host = resolve_ds723_host(remote_host)
    print("IFG Guardian — prod maintenance end")
    print("=" * 40)
    print(f"Maintenance since: {marker.started_at_utc}")
    print(f"Operation ID: {marker.operation_id}")

    audit = RuntimeAuditSession(
        workflow="prod.maintenance.end",
        event_type="maintenance_end",
        reason=marker.reason,
        target=remote_path,
        operation_id=marker.operation_id,
    )

    if dry_run:
        print("[dry-run] Would recover stack and clear marker on success")
        audit.started(extra={"dry_run": True})
        audit.completed(result="dry_run")
        return 0

    audit.started()
    try:
        from ifg_guardian.modules.production import run_prod_recover

        code = run_prod_recover(dry_run=False, assume_yes=True, remote_host=remote_host)
        if code != 0:
            audit.failed("prod recover failed during maintenance end")
            print("❌ Maintenance end failed — marker preserved")
            return code

        final = wait_stack_healthy(host, remote_path=remote_path)
        if final.runtime.status != ProductionRuntimeStatus.PRODUCTION_RUNNING or not final.health_ok:
            audit.failed(f"health not confirmed: {final.runtime.status.value}")
            print("❌ Stack up but health not confirmed — marker preserved")
            return 1

        clear_maintenance_marker()
        audit.completed(result="running", extra={"health": "200"})
        branch = remote_git(host, remote_path, "branch --show-current")
        head = remote_git(host, remote_path, "rev-parse --short HEAD")
        print(f"✅ Maintenance ended — Runtime PRODUCTION_RUNNING")
        print(f"Remote: {branch} @ {head}")
        return 0
    except RuntimeError as exc:
        audit.failed(str(exc))
        print(f"❌ Maintenance end failed: {exc} — marker preserved")
        return 1
