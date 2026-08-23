"""Agregacja statusu workflow przeładowania środowiska IFG."""
from __future__ import annotations

from ifg_guardian.plugins.ifg.env_reload.models import (
    EnvReloadOverallStatus,
    EnvReloadStageStatus,
    EnvReloadState,
)


def aggregate_env_reload_status(state: EnvReloadState) -> EnvReloadOverallStatus:
    if state.preflight_has_fail():
        return EnvReloadOverallStatus.BLOCKED
    if state.dry_run:
        return EnvReloadOverallStatus.READY
    if not state.compose_up_executed:
        return EnvReloadOverallStatus.BLOCKED
    if not state.services_running():
        return EnvReloadOverallStatus.BLOCKED
    if not state.health_ok:
        return EnvReloadOverallStatus.BLOCKED
    return EnvReloadOverallStatus.READY


def exit_code_for_env_reload(state: EnvReloadState) -> int:
    if state.overall_status == EnvReloadOverallStatus.READY:
        return 0
    return 1


def build_operator_actions(state: EnvReloadState) -> list[str]:
    actions: list[str] = []
    for check in state.preflight_checks:
        if check.status == EnvReloadStageStatus.FAIL:
            actions.append(f"Fix preflight `{check.key}`: {check.message}")
    if not state.dry_run:
        if not state.compose_up_executed:
            actions.append("Compose up did not run — verify SSH access and remote docker compose.")
        for svc in state.service_statuses:
            if not svc.running:
                actions.append(f"Service `{svc.service}` not running: {svc.state_line}")
        if not state.health_ok:
            actions.append(f"Health endpoint failed: {state.health_detail}")
    if not actions:
        if state.dry_run:
            actions.append("Dry-run complete — re-run with --yes to reload environment on DS723+.")
        else:
            actions.append("Environment reloaded — no further action required.")
    return actions


def summarize_startup_logs(raw: str, *, max_lines: int = 8) -> list[str]:
    if not raw.strip():
        return ["Brak logów startowych."]
    lines = [line.rstrip() for line in raw.splitlines() if line.strip()]
    if not lines:
        return ["Brak logów startowych."]
    tail = lines[-max_lines:]
    return [f"`{line}`" if len(line) <= 120 else f"`{line[:117]}...`" for line in tail]
