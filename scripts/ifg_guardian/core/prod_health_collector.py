"""Shared production health collection for prod health / monitor / maintenance."""
from __future__ import annotations

from dataclasses import dataclass

from ifg_guardian.config import COMPOSE_FILE, DEFAULT_REMOTE_PATH, REQUIRED_COMPOSE_SERVICES
from ifg_guardian.core.compose import remote_compose_ps
from ifg_guardian.core.runtime_maintenance import load_maintenance_marker
from ifg_guardian.core.runtime_status import ProductionRuntimeStatus, RuntimeStatusReport, classify_runtime_status
from ifg_guardian.core.ssh import ssh


@dataclass
class ProdHealthSnapshot:
    reachable: bool
    compose_ps: str
    health_ok: bool
    health_detail: str
    restart_policies: dict[str, str]
    project_registered: bool | None
    runtime: RuntimeStatusReport
    error: str | None = None


def fetch_restart_policies(host: str, repo_path: str) -> dict[str, str]:
    policies: dict[str, str] = {}
    for svc in REQUIRED_COMPOSE_SERVICES:
        container = f"ifg-{svc}-1"
        try:
            raw = ssh(
                host,
                f"sudo docker inspect {container} --format '{{{{.HostConfig.RestartPolicy.Name}}}}' 2>/dev/null || true",
            )
            name = raw.strip()
            if name:
                policies[svc] = name
        except RuntimeError:
            continue
    return policies


def compose_project_registered(host: str, repo_path: str) -> bool | None:
    try:
        listing = ssh(host, f"cd {repo_path} && sudo docker compose ls 2>/dev/null || true")
        if not listing.strip():
            return None
        return any(line.lower().startswith("ifg") for line in listing.splitlines())
    except RuntimeError:
        return None


def probe_health(host: str, *, timeout_seconds: int = 10) -> tuple[bool, str]:
    health_url = "http://127.0.0.1:8000/health"
    try:
        body = ssh(
            host,
            f"curl -sS -m {timeout_seconds} -o /dev/null -w '%{{http_code}}' {health_url} 2>/dev/null || echo 000",
        )
        code = body.strip()
        if code == "200":
            body_text = ssh(host, f"curl -sS -m {timeout_seconds} {health_url}")
            return True, body_text[:200]
        return False, f"HTTP {code}"
    except RuntimeError as exc:
        return False, str(exc)


def collect_prod_health_snapshot(
    host: str,
    *,
    remote_path: str = DEFAULT_REMOTE_PATH,
    ssh_timeout_seconds: int = 10,
    maintenance_active: bool | None = None,
) -> ProdHealthSnapshot:
    marker = load_maintenance_marker()
    active = maintenance_active if maintenance_active is not None else marker is not None
    try:
        compose_ps = remote_compose_ps(host, remote_path)
        health_ok, health_detail = probe_health(host, timeout_seconds=ssh_timeout_seconds)
        restart_policies = fetch_restart_policies(host, remote_path)
        project_registered = compose_project_registered(host, remote_path)
        runtime = classify_runtime_status(
            compose_ps,
            health_endpoint_ok=health_ok,
            restart_policies=restart_policies or None,
            expected_restart_policy="always",
            compose_project_registered=project_registered,
            maintenance_active=active,
        )
        return ProdHealthSnapshot(
            reachable=True,
            compose_ps=compose_ps,
            health_ok=health_ok,
            health_detail=health_detail,
            restart_policies=restart_policies,
            project_registered=project_registered,
            runtime=runtime,
        )
    except RuntimeError as exc:
        unreachable = RuntimeStatusReport(
            status=ProductionRuntimeStatus.PRODUCTION_DEGRADED,
            problems=[f"SSH unreachable: {exc}"],
        )
        return ProdHealthSnapshot(
            reachable=False,
            compose_ps="",
            health_ok=False,
            health_detail=str(exc),
            restart_policies={},
            project_registered=None,
            runtime=unreachable,
            error=str(exc),
        )


def remote_compose_stop(host: str, remote_path: str = DEFAULT_REMOTE_PATH) -> None:
    cmd = f"cd {remote_path} && sudo docker compose -f {COMPOSE_FILE} stop"
    ssh(host, cmd)


def remote_compose_up(host: str, remote_path: str = DEFAULT_REMOTE_PATH) -> None:
    cmd = f"cd {remote_path} && sudo docker compose -f {COMPOSE_FILE} up -d"
    ssh(host, cmd)


def wait_stack_healthy(host: str, *, remote_path: str = DEFAULT_REMOTE_PATH, timeout_seconds: int = 180) -> ProdHealthSnapshot:
    import time

    deadline = time.monotonic() + timeout_seconds
    last = collect_prod_health_snapshot(host, remote_path=remote_path)
    while time.monotonic() < deadline:
        last = collect_prod_health_snapshot(host, remote_path=remote_path)
        if last.runtime.status == ProductionRuntimeStatus.PRODUCTION_RUNNING:
            if last.health_ok:
                return last
        time.sleep(5)
    return last
