from __future__ import annotations

from ifg_guardian.config import DEFAULT_REMOTE_PATH, ROOT
from ifg_guardian.core.execution_guard import enforce_mutating_live_orchestration
from ifg_guardian.core.git import resolve_ds723_host
from ifg_guardian.core.prod_health_collector import collect_prod_health_snapshot
from ifg_guardian.core.runtime_audit import RuntimeAuditSession
from ifg_guardian.core.runtime_maintenance import load_maintenance_marker
from ifg_guardian.core.runtime_status import ProductionRuntimeStatus
from ifg_guardian.core.ssh import remote_git


def run_prod_health(
    *,
    remote_host: str | None = None,
    remote_path: str = DEFAULT_REMOTE_PATH,
) -> int:
    """Read-only production health — runtime status independent from release gate (GDD-0010)."""
    host = resolve_ds723_host(remote_host)
    print("IFG Guardian — prod health")
    print("=" * 40)

    marker = load_maintenance_marker()
    snapshot = collect_prod_health_snapshot(host, remote_path=remote_path)
    if not snapshot.reachable:
        print(f"\n❌ SSH failed: {snapshot.error}")
        print("\nRuntime: UNREACHABLE")
        print("Release: (not evaluated — SSH failure)")
        return 1

    print("\ndocker compose ps:")
    for line in snapshot.compose_ps.splitlines():
        print(f"  {line}")

    runtime = snapshot.runtime
    if runtime.status in (ProductionRuntimeStatus.PRODUCTION_RUNNING, ProductionRuntimeStatus.PRODUCTION_MAINTENANCE):
        print("\n✅ api/worker/db acceptable for runtime status")
    else:
        print("\n❌ container problems:")
        for p in runtime.problems:
            print(f"  • {p}")

    print(f"\nHealth http://127.0.0.1:8000/health: {'OK' if snapshot.health_ok else 'FAIL'}")
    if snapshot.health_detail:
        print(f"  {snapshot.health_detail}")

    if snapshot.restart_policies:
        print("\nRestart policies:")
        from ifg_guardian.config import REQUIRED_COMPOSE_SERVICES

        for svc in REQUIRED_COMPOSE_SERVICES:
            policy = snapshot.restart_policies.get(svc, "(unknown)")
            print(f"  {svc}: {policy}")

    if snapshot.project_registered is not None:
        label = "registered" if snapshot.project_registered else "NOT registered"
        print(f"\nContainer Manager project 'ifg': {label}")

    if marker is not None:
        print(f"\nMaintenance: active since {marker.started_at_utc}")
        if marker.reason:
            print(f"  reason: {marker.reason}")

    branch = remote_git(host, remote_path, "branch --show-current")
    head = remote_git(host, remote_path, "rev-parse --short HEAD")
    print(f"\nRemote branch: {branch}")
    print(f"Remote HEAD: {head}")

    print("\n" + "=" * 40)
    print(f"Runtime: {runtime.status.value}")
    if runtime.problems:
        print("Runtime details:")
        for item in runtime.problems:
            print(f"  • {item}")
    print(
        "Release: (not evaluated — run `guardian release evaluate` for "
        "READY_FOR_DEPLOY / PRODUCTION_BLOCKED)"
    )
    if runtime.status == ProductionRuntimeStatus.PRODUCTION_STOPPED:
        print(
            "Note: PRODUCTION_STOPPED reflects container runtime only; "
            "PRODUCTION_BLOCKED (release gate) does not cause stack shutdown."
        )
    if runtime.status == ProductionRuntimeStatus.PRODUCTION_MAINTENANCE:
        print("Note: PRODUCTION_MAINTENANCE is expected during controlled maintenance.")
    return runtime.exit_code


def run_prod_recover(*, dry_run: bool = False, assume_yes: bool = False, remote_host: str | None = None) -> int:
    """Mutating operation — delegates to guardian2 recover-prod."""
    import subprocess
    import sys
    from pathlib import Path

    try:
        enforce_mutating_live_orchestration(dry_run=dry_run, root=ROOT)
    except RuntimeError as exc:
        print(f"\n❌ prod recover blocked: {exc}")
        return 1

    audit = RuntimeAuditSession(workflow="prod.recover", event_type="prod_recover")
    if dry_run:
        audit.started(extra={"dry_run": True})
        audit.completed(result="dry_run")
    else:
        audit.started()

    scripts = Path(__file__).resolve().parent.parent.parent
    cmd = [sys.executable, str(scripts / "guardian2.py"), "recover-prod"]
    if dry_run:
        cmd.append("--dry-run")
    if assume_yes:
        cmd.append("--yes")
    if remote_host:
        cmd.extend(["--remote-host", remote_host])
    code = subprocess.call(cmd)
    if dry_run:
        return code
    if code == 0:
        audit.completed(result="ok")
    else:
        audit.failed(f"guardian2 recover-prod exit {code}")
    return code
