"""Production runtime status — independent from release gate (GDD-0010)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ifg_guardian.config import REQUIRED_COMPOSE_SERVICES
from ifg_guardian.core.compose import (
    compose_services_healthy,
    parse_compose_service_states,
    service_state_is_healthy,
    service_state_is_running,
    service_state_is_restarting,
)


class ProductionRuntimeStatus(str, Enum):
    PRODUCTION_RUNNING = "PRODUCTION_RUNNING"
    PRODUCTION_STOPPED = "PRODUCTION_STOPPED"
    PRODUCTION_DEGRADED = "PRODUCTION_DEGRADED"
    PRODUCTION_MAINTENANCE = "PRODUCTION_MAINTENANCE"


@dataclass
class RuntimeStatusReport:
    status: ProductionRuntimeStatus
    problems: list[str] = field(default_factory=list)
    stopped_services: list[str] = field(default_factory=list)
    running_services: list[str] = field(default_factory=list)
    health_endpoint_ok: bool | None = None
    restart_policy_mismatches: list[str] = field(default_factory=list)
    compose_project_registered: bool | None = None
    maintenance_active: bool = False
    maintenance_inconsistent: bool = False

    @property
    def exit_code(self) -> int:
        if self.status in (
            ProductionRuntimeStatus.PRODUCTION_RUNNING,
            ProductionRuntimeStatus.PRODUCTION_MAINTENANCE,
        ):
            return 0
        return 1


def _service_is_stopped(state_line: str | None) -> bool:
    if not state_line:
        return True
    normalized = state_line.lower()
    if service_state_is_restarting(state_line):
        return False
    if service_state_is_running(state_line):
        return False
    return any(token in normalized for token in ("exited", "dead", "paused", "created"))


def classify_runtime_status(
    compose_ps: str,
    *,
    health_endpoint_ok: bool | None = None,
    restart_policies: dict[str, str] | None = None,
    expected_restart_policy: str = "always",
    compose_project_registered: bool | None = None,
    maintenance_active: bool = False,
) -> RuntimeStatusReport:
    """Classify DS723+ runtime from compose ps output and optional health signal."""
    states = parse_compose_service_states(compose_ps)
    _, problems = compose_services_healthy(states)

    stopped: list[str] = []
    running: list[str] = []
    for svc in REQUIRED_COMPOSE_SERVICES:
        raw = states.get(svc)
        if _service_is_stopped(raw):
            stopped.append(svc)
        elif service_state_is_running(raw):
            running.append(svc)

    all_stopped = len(stopped) == len(REQUIRED_COMPOSE_SERVICES)
    any_stopped = bool(stopped)
    any_running = bool(running)

    restart_mismatches: list[str] = []
    if restart_policies:
        for svc in REQUIRED_COMPOSE_SERVICES:
            actual = restart_policies.get(svc)
            if actual and actual != expected_restart_policy:
                restart_mismatches.append(f"{svc}: {actual} (expected {expected_restart_policy})")

    if all_stopped:
        status = ProductionRuntimeStatus.PRODUCTION_STOPPED
        detail_problems = [f"all services stopped: {', '.join(stopped)}"]
        if health_endpoint_ok is False:
            detail_problems.append("/health unreachable (stack stopped)")
    elif any_stopped or problems:
        status = ProductionRuntimeStatus.PRODUCTION_DEGRADED
        detail_problems = list(problems)
        if stopped:
            detail_problems.insert(0, f"stopped: {', '.join(stopped)}")
    elif health_endpoint_ok is False:
        status = ProductionRuntimeStatus.PRODUCTION_DEGRADED
        detail_problems = ["/health endpoint failed while containers report running"]
    else:
        unhealthy = [
            svc
            for svc in REQUIRED_COMPOSE_SERVICES
            if states.get(svc)
            and service_state_is_running(states[svc])
            and "unhealthy" in states[svc].lower()
        ]
        if unhealthy:
            status = ProductionRuntimeStatus.PRODUCTION_DEGRADED
            detail_problems = [f"running but not healthy: {', '.join(unhealthy)}"]
        else:
            status = ProductionRuntimeStatus.PRODUCTION_RUNNING
            detail_problems = []

    if restart_mismatches:
        detail_problems.extend([f"restart policy mismatch: {m}" for m in restart_mismatches])

    if compose_project_registered is False:
        detail_problems.append("compose project 'ifg' not registered in Container Manager (docker compose ls)")

    maintenance_inconsistent = False
    final_status = status
    if maintenance_active:
        if all_stopped or (any_stopped and not all_stopped):
            if any_running and not all_stopped:
                final_status = ProductionRuntimeStatus.PRODUCTION_DEGRADED
                maintenance_inconsistent = True
                detail_problems.insert(0, "maintenance marker active but stack is partially running")
            else:
                final_status = ProductionRuntimeStatus.PRODUCTION_MAINTENANCE
                detail_problems = [p for p in detail_problems if "all services stopped" not in p]
                if all_stopped:
                    detail_problems.insert(0, "stack stopped under active maintenance")
        elif final_status == ProductionRuntimeStatus.PRODUCTION_RUNNING:
            final_status = ProductionRuntimeStatus.PRODUCTION_DEGRADED
            maintenance_inconsistent = True
            detail_problems.insert(0, "maintenance marker active but stack reports running")

    return RuntimeStatusReport(
        status=final_status,
        problems=detail_problems,
        stopped_services=stopped,
        running_services=running,
        health_endpoint_ok=health_endpoint_ok,
        restart_policy_mismatches=restart_mismatches,
        compose_project_registered=compose_project_registered,
        maintenance_active=maintenance_active,
        maintenance_inconsistent=maintenance_inconsistent,
    )
