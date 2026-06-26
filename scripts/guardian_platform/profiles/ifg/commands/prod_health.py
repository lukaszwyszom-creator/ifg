from __future__ import annotations

from guardian_platform.core.runtime.context import CommandContext
from guardian_platform.profiles.ifg.config.defaults import DEFAULT_REMOTE_PATH, resolve_remote_host
from guardian_platform.profiles.ifg.infra.compose import (
    compose_services_healthy,
    parse_compose_service_states,
    remote_compose_ps,
)
from guardian_platform.profiles.ifg.infra.ssh import remote_git, ssh


def run_prod_health(ctx: CommandContext) -> int:
    remote_path = ctx.extra.get("remote_path") or DEFAULT_REMOTE_PATH
    host = resolve_remote_host(ctx.extra.get("remote_host"))

    print("IFG Guardian — prod health")
    print("=" * 40)

    try:
        compose_ps = remote_compose_ps(host, remote_path)
        states = parse_compose_service_states(compose_ps)
        ok, problems = compose_services_healthy(states)
        print("\ndocker compose ps:")
        for line in compose_ps.splitlines():
            print(f"  {line}")
        if ok:
            print("\n✅ api/worker/db running")
        else:
            print("\n❌ container problems:")
            for p in problems:
                print(f"  • {p}")

        health_url = "http://127.0.0.1:8000/health"
        try:
            body = ssh(host, f"curl -sS -m 10 {health_url}")
            health_ok = bool(body) and ("ok" in body.lower() or '"status"' in body.lower())
            print(f"\nHealth {health_url}: {'OK' if health_ok else 'FAIL'}")
            if body:
                print(f"  {body[:200]}")
        except RuntimeError as exc:
            print(f"\n❌ Health check failed: {exc}")
            health_ok = False

        branch = remote_git(host, remote_path, "branch --show-current")
        head = remote_git(host, remote_path, "rev-parse --short HEAD")
        print(f"\nRemote branch: {branch}")
        print(f"Remote HEAD: {head}")

    except RuntimeError as exc:
        print(f"\n❌ SSH failed: {exc}")
        print("\nStatus: ERROR")
        return 1

    print("\n" + "=" * 40)
    if ok and health_ok:
        print("Status: OK")
        return 0
    print("Status: ERROR")
    return 1
