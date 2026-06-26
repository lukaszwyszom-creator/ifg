from __future__ import annotations

import re

from guardian_platform.profiles.ifg.config.defaults import COMPOSE_FILE, REQUIRED_COMPOSE_SERVICES
from guardian_platform.profiles.ifg.infra.ssh import ssh


def container_state_ok(state: str) -> bool:
    normalized = state.lower()
    if any(bad in normalized for bad in ("exited", "dead", "restarting", "paused")):
        return False
    return "running" in normalized or re.search(r"\bup\b", normalized) is not None


def parse_compose_service_states(ps_output: str) -> dict[str, str]:
    states: dict[str, str] = {}
    for line in ps_output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("NAME") or stripped.startswith("SERVICE"):
            continue
        tab_parts = stripped.split("\t")
        if len(tab_parts) == 2 and tab_parts[0] in REQUIRED_COMPOSE_SERVICES:
            states[tab_parts[0]] = tab_parts[1]
            continue
        parts = stripped.split()
        if not parts:
            continue
        service = parts[-1]
        if service in REQUIRED_COMPOSE_SERVICES and service not in states:
            states[service] = stripped
            continue
        for svc in REQUIRED_COMPOSE_SERVICES:
            if svc in states:
                continue
            if re.search(rf"\b{svc}\b", stripped, re.IGNORECASE):
                states[svc] = stripped
    return states


def compose_services_healthy(states: dict[str, str]) -> tuple[bool, list[str]]:
    problems: list[str] = []
    for svc in REQUIRED_COMPOSE_SERVICES:
        raw = states.get(svc)
        if raw is None:
            problems.append(f"{svc}: brak w docker compose ps")
        elif not container_state_ok(raw):
            problems.append(f"{svc}: {raw}")
    return not problems, problems


def remote_compose_ps(host: str, repo_path: str) -> str:
    compose_cmd = (
        f"cd {repo_path} && sudo docker compose -f {COMPOSE_FILE} ps "
        "--format '{{.Service}}\t{{.State}}'"
    )
    try:
        return ssh(host, compose_cmd)
    except RuntimeError:
        return ssh(host, f"cd {repo_path} && sudo docker compose -f {COMPOSE_FILE} ps")
