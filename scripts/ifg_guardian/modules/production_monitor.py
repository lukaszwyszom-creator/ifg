"""Stateful runtime monitor CLI — Mac mini orchestration only."""
from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path

from ifg_guardian.config import ROOT
from ifg_guardian.core.execution_guard import is_ds723_target_host
from ifg_guardian.core.git import resolve_ds723_host
from ifg_guardian.core.prod_health_collector import collect_prod_health_snapshot
from ifg_guardian.core.runtime_audit import RuntimeAuditSession
from ifg_guardian.core.runtime_maintenance import load_maintenance_marker
from ifg_guardian.core.runtime_monitor import MonitorCheckResult, evaluate_monitor_transition
from ifg_guardian.core.runtime_status import ProductionRuntimeStatus
from ifg_guardian.config import DEFAULT_REMOTE_PATH

LAUNCHD_LABEL = "com.ifg.guardian.prod-monitor"
STATE_DIR = ROOT / ".state"
MONITOR_LOG = STATE_DIR / "prod_monitor.log"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_LABEL}.plist"


def _python_executable() -> str:
    venv = ROOT / ".venv" / "bin" / "python3"
    if venv.is_file():
        return str(venv)
    return sys.executable


def _guardian_monitor_command() -> list[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "scripts")
    return [
        _python_executable(),
        "-m",
        "ifg_guardian.cli",
        "prod",
        "monitor",
        "check",
    ]


def run_prod_monitor_check(
    *,
    remote_host: str | None = None,
    remote_path: str = DEFAULT_REMOTE_PATH,
    ssh_timeout_seconds: int = 30,
) -> int:
    host = resolve_ds723_host(remote_host)
    print("IFG Guardian — prod monitor check")
    print("=" * 40)

    audit = RuntimeAuditSession(workflow="prod.monitor.check", event_type="monitor_check")
    audit.started()

    marker = load_maintenance_marker()
    snapshot = collect_prod_health_snapshot(
        host,
        remote_path=remote_path,
        ssh_timeout_seconds=ssh_timeout_seconds,
    )

    if not snapshot.reachable:
        observed = "UNREACHABLE"
        diagnostic = snapshot.error or "SSH unreachable"
    else:
        observed = snapshot.runtime.status.value
        diagnostic = "; ".join(snapshot.runtime.problems[:3]) if snapshot.runtime.problems else snapshot.health_detail

    result: MonitorCheckResult = evaluate_monitor_transition(
        observed_state=observed,
        diagnostic=diagnostic,
        maintenance_active=marker is not None,
    )

    print(f"Observed: {result.observed_state}")
    print(f"Previous: {result.previous_state}")
    if result.alert_reason:
        print(f"Alert: {result.alert_reason}")
    if result.recovery_sent:
        print("Recovery notification sent")
    if result.alert_sent and not result.recovery_sent:
        print("Alert notification sent")

    audit.completed(
        result=result.observed_state,
        extra={
            "alert_sent": result.alert_sent,
            "recovery_sent": result.recovery_sent,
        },
    )
    return result.exit_code


def _build_plist() -> dict:
    cmd = _guardian_monitor_command()
    return {
        "Label": LAUNCHD_LABEL,
        "ProgramArguments": cmd,
        "WorkingDirectory": str(ROOT),
        "EnvironmentVariables": {"PYTHONPATH": str(ROOT / "scripts")},
        "StartInterval": 300,
        "RunAtLoad": True,
        "StandardOutPath": str(MONITOR_LOG),
        "StandardErrorPath": str(MONITOR_LOG),
        "ProcessType": "Background",
    }


def run_prod_monitor_install() -> int:
    print("IFG Guardian — prod monitor install")
    print("=" * 40)
    if is_ds723_target_host(root=ROOT):
        print("❌ Monitor must run on Mac mini orchestration host, not DS723+")
        return 1

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    plist = _build_plist()
    PLIST_PATH.write_bytes(plistlib.dumps(plist))
    print(f"Plist: {PLIST_PATH}")

    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(PLIST_PATH)], check=False, capture_output=True)
    boot = subprocess.run(
        ["launchctl", "bootstrap", f"gui/{uid}", str(PLIST_PATH)],
        capture_output=True,
        text=True,
    )
    if boot.returncode != 0:
        print(f"❌ launchctl bootstrap failed: {boot.stderr or boot.stdout}")
        return 1
    subprocess.run(["launchctl", "enable", f"gui/{uid}/{LAUNCHD_LABEL}"], check=False)
    print("✅ Monitor scheduled every 5 minutes (launchd)")
    return 0


def run_prod_monitor_status() -> int:
    print("IFG Guardian — prod monitor status")
    print("=" * 40)
    if is_ds723_target_host(root=ROOT):
        print("❌ Monitor status must be checked from Mac mini")
        return 1

    uid = os.getuid()
    proc = subprocess.run(
        ["launchctl", "print", f"gui/{uid}/{LAUNCHD_LABEL}"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print("Status: not installed")
        if PLIST_PATH.is_file():
            print(f"Plist exists: {PLIST_PATH} (not loaded)")
        return 1
    print("Status: installed")
    print(proc.stdout[:800])
    if MONITOR_LOG.is_file():
        print(f"\nLog tail ({MONITOR_LOG}):")
        lines = MONITOR_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in lines[-5:]:
            print(f"  {line}")
    return 0


def run_prod_monitor_uninstall() -> int:
    print("IFG Guardian — prod monitor uninstall")
    print("=" * 40)
    if is_ds723_target_host(root=ROOT):
        print("❌ Monitor uninstall must run from Mac mini")
        return 1

    uid = os.getuid()
    if PLIST_PATH.is_file():
        subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(PLIST_PATH)], check=False)
    print("✅ Monitor launchd job removed (plist kept for reference)" if PLIST_PATH.is_file() else "✅ Monitor not installed")
    return 0
