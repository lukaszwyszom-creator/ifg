from __future__ import annotations

from guardian_platform.core.runtime.context import CommandContext
from guardian_platform.profiles.ifg.config.defaults import DEFAULT_REMOTE_PATH, resolve_remote_host
from guardian_platform.profiles.ifg.infra.compose import (
    compose_services_healthy,
    parse_compose_service_states,
    remote_compose_ps,
)
from guardian_platform.profiles.ifg.infra.git import git, porcelain_is_dirty, short_sha
from guardian_platform.profiles.ifg.infra.ssh import remote_git
from guardian_platform.profiles.ifg.checks.frontend import (
    check_frontend_dist_freshness,
    check_frontend_worktree_requires_build,
    check_ksef_connect_button_fix,
    check_remote_frontend_dist_freshness,
)


def run_deploy_check(ctx: CommandContext) -> int:
    remote_path = ctx.extra.get("remote_path") or DEFAULT_REMOTE_PATH
    host = resolve_remote_host(ctx.extra.get("remote_host"))

    print("IFG Guardian Deploy Check")
    print("Mac mini → DS723+")
    print("=" * 40)

    try:
        local_branch = git("branch", "--show-current")
        local_head = git("rev-parse", "HEAD")
        local_status = git("status", "--short")
    except RuntimeError as exc:
        print(f"\n❌ Nie udało się odczytać stanu lokalnego repo: {exc}")
        print("\nWerdykt: NIE MOŻNA POTWIERDZIĆ — BRAK SSH / BŁĄD UPRAWNIEŃ")
        return 1

    local_dirty = porcelain_is_dirty(local_status)
    local_dist_ok, local_dist_note = check_frontend_dist_freshness()
    local_worktree_ok, local_worktree_note = check_frontend_worktree_requires_build()
    connect_ok, connect_notes = check_ksef_connect_button_fix()

    print("\nLokalnie (Mac mini):")
    print(f"  branch: {local_branch}")
    print(f"  HEAD:   {local_head}")
    print(f"  frontend dist: {local_dist_note}")
    print(f"  frontend worktree: {local_worktree_note}")
    for note in connect_notes:
        print(f"  connect fix: {note}")
    if local_status:
        print(f"  status:\n{local_status}")
    else:
        print("  status: (clean)")

    ssh_ok = True
    branch_match: bool | None = None
    commit_match: bool | None = None
    remote_dirty: bool | None = None
    remote_dist_ok: bool | None = None
    containers_ok: bool | None = None
    container_problems: list[str] = []
    remote_branch = remote_head = remote_status = ""

    print(f"\nZdalnie (DS723+ — {host}:{remote_path}):")
    print("-" * 40)
    try:
        remote_branch = remote_git(host, remote_path, "branch --show-current")
        remote_head = remote_git(host, remote_path, "rev-parse HEAD")
        remote_status = remote_git(host, remote_path, "status --short")
        compose_ps = remote_compose_ps(host, remote_path)
    except RuntimeError as exc:
        ssh_ok = False
        print(f"  ❌ SSH / odczyt zdalny nieudany: {exc}")
    else:
        remote_dirty = porcelain_is_dirty(remote_status)
        branch_match = local_branch == remote_branch
        commit_match = local_head == remote_head
        remote_dist_ok, remote_dist_note = check_remote_frontend_dist_freshness(host, remote_path)
        service_states = parse_compose_service_states(compose_ps)
        containers_ok, container_problems = compose_services_healthy(service_states)

        print(f"  branch: {remote_branch}")
        print(f"  HEAD:   {remote_head}")
        print(f"  frontend dist: {remote_dist_note}")
        if remote_status:
            print(f"  status:\n{remote_status}")
        else:
            print("  status: (clean)")
        print("\n  docker compose ps:")
        for line in compose_ps.splitlines():
            print(f"    {line}")

    print("\n" + "=" * 40)
    print("Raport:")
    print("-" * 40)

    if not ssh_ok:
        print("❌ branch: nie sprawdzono (brak SSH)")
        print("❌ commit: nie sprawdzono (brak SSH)")
        print("⚠️  repo: lokalne zmiany" if local_dirty else "✅ repo clean (lokalnie)")
        print("❌ kontenery: nie sprawdzono (brak SSH)")
        print("\nWerdykt: NIE MOŻNA POTWIERDZIĆ — BRAK SSH / BŁĄD UPRAWNIEŃ")
        return 1

    assert branch_match is not None and commit_match is not None
    assert remote_dirty is not None and containers_ok is not None

    print(f"{'✅' if branch_match else '❌'} branch {'zgodny' if branch_match else 'różny'}"
          f"  (local: {local_branch}, DS723+: {remote_branch})")
    print(f"{'✅' if commit_match else '❌'} commit {'zgodny' if commit_match else 'różny'}"
          f"  (local: {short_sha(local_head)}, DS723+: {short_sha(remote_head)})")

    if local_dirty or remote_dirty:
        parts = []
        if local_dirty:
            parts.append("Mac mini")
        if remote_dirty:
            parts.append("DS723+")
        print(f"⚠️  są lokalne zmiany ({', '.join(parts)})")
    else:
        print("✅ repo clean")

    if containers_ok:
        print("✅ kontenery działają (api, worker, db)")
    else:
        print("❌ problem z api/worker/db")
        for problem in container_problems:
            print(f"     • {problem}")

    print(f"{'✅' if local_dist_ok else '❌'} frontend dist commit-vs-dist (Mac mini)")
    print(f"{'✅' if local_worktree_ok else '❌'} frontend dist worktree-vs-dist (Mac mini)")
    print(f"{'✅' if connect_ok else '❌'} KSeF connect button fix w src+dist")
    if remote_dist_ok is not None:
        print(f"{'✅' if remote_dist_ok else '❌'} frontend dist commit-vs-dist (DS723+)")

    print()
    deploy_ok = (
        branch_match
        and commit_match
        and containers_ok
        and local_dist_ok
        and local_worktree_ok
        and connect_ok
        and (remote_dist_ok is not False)
    )
    if deploy_ok:
        print("Werdykt: PRODUKCJA ZGODNA Z LOKALNYM KODEM")
        return 0

    print("Werdykt: PRODUKCJA NIEZGODNA — WYMAGANY DEPLOY")
    return 1
