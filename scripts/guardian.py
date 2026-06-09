#!/usr/bin/env python3
"""IFG Guardian MVP — weryfikuje zgodność endpointów mobile-expo z backendem IFG."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET_BRANCH = "production"
DEFAULT_REMOTE_HOST = "ds723"
DEFAULT_REMOTE_PATH = "/volume1/docker/ifg_v2/ifg_standalone"

MOBILE_API_GLOB = "mobile-expo/src/api/**/*.ts"
ROUTER_GLOB = "app/api/routers/**/*.py"
MAIN_FILE = ROOT / "app" / "main.py"

HTTP_METHODS = ("get", "post", "put", "delete")

FRONTEND_CALL_RE = re.compile(
    r"apiClient\.(get|post|put|delete)\s*(?:<[^>]*>)?\s*\(\s*([`\"'])(.*?)\2",
    re.DOTALL,
)
ROUTER_DEF_RE = re.compile(
    r"^(\w+)\s*=\s*APIRouter\s*\((.*?)\)",
    re.MULTILINE | re.DOTALL,
)
ROUTER_PREFIX_RE = re.compile(r"""prefix\s*=\s*["']([^"']*)["']""")
ROUTE_DECORATOR_RE = re.compile(
    r"@(\w+)\.(get|post|put|delete)\(\s*[\"']([^\"']+)[\"']",
)
MAIN_IMPORT_RE = re.compile(
    r"from\s+app\.api\.routers\.(\w+)\s+import\s+(.+)",
)
INCLUDE_ROUTER_RE = re.compile(r"include_router\s*\(\s*(\w+)")


@dataclass(frozen=True)
class Endpoint:
    method: str
    path: str
    source: str

    def key(self) -> tuple[str, str]:
        return (self.method.upper(), self.path)


@dataclass(frozen=True)
class RouterDef:
    module: str
    variable: str
    prefix: str
    source: str


def _normalize_path(path: str) -> str:
    base = path.split("?", 1)[0].split("#", 1)[0].strip()
    if not base.startswith("/"):
        base = f"/{base}"
    base = re.sub(r"/+", "/", base)
    if base != "/" and base.endswith("/"):
        base = base.rstrip("/")
    # template literals / parametry frontendu → segment wildcard
    parts = []
    for segment in base.strip("/").split("/"):
        if segment.startswith("${") or segment.startswith("{") or segment == "*":
            parts.append("*")
        else:
            parts.append(segment)
    return "/" + "/".join(parts) if parts else "/"


def _path_matches(frontend_path: str, backend_path: str) -> bool:
    fe_parts = frontend_path.strip("/").split("/")
    be_parts = backend_path.strip("/").split("/")
    if len(fe_parts) != len(be_parts):
        return False
    for fe, be in zip(fe_parts, be_parts, strict=True):
        if fe == "*" or (be.startswith("{") and be.endswith("}")):
            continue
        if fe != be:
            return False
    return True


def _extract_frontend_endpoints() -> list[Endpoint]:
    endpoints: list[Endpoint] = []
    for ts_file in sorted(ROOT.glob(MOBILE_API_GLOB)):
        if not ts_file.is_file():
            continue
        text = ts_file.read_text(encoding="utf-8")
        rel = ts_file.relative_to(ROOT).as_posix()
        for match in FRONTEND_CALL_RE.finditer(text):
            method = match.group(1).lower()
            raw_path = match.group(3).strip()
            if not raw_path.startswith("/"):
                continue
            endpoints.append(
                Endpoint(
                    method=method,
                    path=_normalize_path(raw_path),
                    source=rel,
                )
            )
    return endpoints


def _router_prefix(router_args: str) -> str:
    prefix_match = ROUTER_PREFIX_RE.search(router_args)
    return prefix_match.group(1) if prefix_match else ""


def _join_paths(prefix: str, route: str) -> str:
    combined = f"{prefix.rstrip('/')}/{route.lstrip('/')}"
    return _normalize_path(combined)


def _extract_backend_endpoints() -> tuple[list[Endpoint], list[RouterDef]]:
    endpoints: list[Endpoint] = []
    router_defs: list[RouterDef] = []

    for py_file in sorted(ROOT.glob(ROUTER_GLOB)):
        if not py_file.is_file() or py_file.name == "__init__.py":
            continue

        text = py_file.read_text(encoding="utf-8")
        rel = py_file.relative_to(ROOT).as_posix()
        module = py_file.stem

        prefixes: dict[str, str] = {}
        for router_match in ROUTER_DEF_RE.finditer(text):
            var_name = router_match.group(1)
            prefix = _router_prefix(router_match.group(2))
            prefixes[var_name] = prefix
            router_defs.append(
                RouterDef(
                    module=module,
                    variable=var_name,
                    prefix=prefix,
                    source=rel,
                )
            )

        for route_match in ROUTE_DECORATOR_RE.finditer(text):
            router_var = route_match.group(1)
            method = route_match.group(2).lower()
            route_path = route_match.group(3)
            prefix = prefixes.get(router_var, "")
            endpoints.append(
                Endpoint(
                    method=method,
                    path=_join_paths(prefix, route_path),
                    source=rel,
                )
            )

    return endpoints, router_defs


def _parse_main_registrations() -> tuple[dict[str, set[str]], set[str]]:
    """Zwraca mapę module -> zaimportowane nazwy routerów oraz zbiór routerów w include_router."""
    if not MAIN_FILE.is_file():
        return {}, set()

    text = MAIN_FILE.read_text(encoding="utf-8")
    imported: dict[str, set[str]] = {}
    included: set[str] = set()

    for match in MAIN_IMPORT_RE.finditer(text):
        module = match.group(1)
        names_part = match.group(2)
        for part in names_part.split(","):
            part = part.strip()
            if " as " in part:
                original, alias = part.split(" as ", 1)
                imported.setdefault(module, set()).add(original.strip())
                imported.setdefault(module, set()).add(alias.strip())
            else:
                imported.setdefault(module, set()).add(part.strip())

    for match in INCLUDE_ROUTER_RE.finditer(text):
        included.add(match.group(1))

    return imported, included


def _find_backend_match(
    frontend: Endpoint, backend_endpoints: list[Endpoint]
) -> Endpoint | None:
    for backend in backend_endpoints:
        if frontend.method != backend.method:
            continue
        if _path_matches(frontend.path, backend.path):
            return backend
    return None


def _is_router_registered(router_def: RouterDef, imported: dict[str, set[str]], included: set[str]) -> bool:
    module_imports = imported.get(router_def.module, set())
    if router_def.variable not in module_imports:
        return False
    # router musi być użyty w include_router — jako oryginalna nazwa lub alias
    if router_def.variable in included:
        return True
    for name in module_imports:
        if name in included and name.startswith(router_def.variable):
            return True
        if name.endswith("_router") and router_def.variable.replace("router", "") in name:
            pass
    # aliasy typu router as ksef_session_router
    for name in included:
        if name in module_imports:
            return True
    return any(name in included for name in module_imports if router_def.variable in name or name.endswith("_router"))


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(detail or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def _short_sha(sha: str) -> str:
    return sha[:7]


def _porcelain_is_dirty(porcelain: str) -> bool:
    for line in porcelain.splitlines():
        if not line.strip():
            continue
        status = line[:2]
        path = line[3:].strip() if len(line) > 3 else ""
        if status == "??" and (path == "backups" or path.startswith("backups/")):
            continue
        return True
    return False


def _ssh(host: str, remote_cmd: str) -> str:
    result = subprocess.run(
        ["ssh", host, remote_cmd],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(detail or f"ssh {host} failed")
    return result.stdout.strip()


def _remote_git(host: str, repo_path: str, git_args: str) -> str:
    return _ssh(host, f"cd {repo_path} && git {git_args}")


def run_repo_sync(
    *,
    do_fetch: bool = False,
    remote: str | None = None,
    remote_host: str = DEFAULT_REMOTE_HOST,
    remote_path: str = DEFAULT_REMOTE_PATH,
) -> int:
    print("IFG Guardian Repo Sync")
    print("=" * 40)

    has_error = False
    has_warning = False
    notes: list[str] = []

    if do_fetch:
        try:
            _git("fetch", "origin", TARGET_BRANCH, "--quiet")
        except RuntimeError as exc:
            print(f"\n❌ git fetch origin {TARGET_BRANCH} failed: {exc}")
            print("\nStatus: ERROR")
            return 1
    else:
        notes.append(
            f"⚠️  origin/{TARGET_BRANCH} may be stale. Run: git fetch origin {TARGET_BRANCH}"
        )

    try:
        branch = _git("branch", "--show-current")
        local_head = _git("rev-parse", "HEAD")
        origin_head = _git("rev-parse", f"origin/{TARGET_BRANCH}")
        porcelain = _git("status", "--porcelain")
        counts = _git("rev-list", "--left-right", "--count", f"HEAD...origin/{TARGET_BRANCH}")
    except RuntimeError as exc:
        print(f"\n❌ Nie udało się odczytać stanu repo: {exc}")
        print("\nStatus: ERROR")
        return 1

    ahead_s, behind_s = counts.split("\t", 1)
    ahead = int(ahead_s)
    behind = int(behind_s)
    dirty = _porcelain_is_dirty(porcelain)
    on_production = branch == TARGET_BRANCH
    local_ok = on_production and not dirty and ahead == 0 and behind == 0

    print(f"\nLocal branch: {branch}")
    print(f"Local HEAD: {local_head}")
    print(f"Origin {TARGET_BRANCH}: {origin_head}")
    print(f"Local ahead: {ahead}")
    print(f"Local behind: {behind}")
    print(f"Local working tree: {'dirty' if dirty else 'clean'}")
    print()

    if not on_production:
        has_error = True
        notes.append(f"❌ local not on {TARGET_BRANCH} branch")
    else:
        notes.append(f"✅ local on {TARGET_BRANCH} branch")

    if dirty:
        has_warning = True
        notes.append("⚠️  local working tree dirty")
    else:
        notes.append("✅ local working tree clean")

    if ahead > 0:
        has_warning = True
        notes.append(f"⚠️  local ahead of origin/{TARGET_BRANCH} ({ahead} commit(s))")
    elif behind > 0:
        has_warning = True
        notes.append(f"⚠️  local behind origin/{TARGET_BRANCH} ({behind} commit(s))")
    elif local_ok:
        notes.append(f"✅ local clean + synced with origin/{TARGET_BRANCH}")

    if not do_fetch:
        has_warning = True

    remote_ok = True
    if remote == "ds723":
        print(f"Remote DS723 ({remote_host}:{remote_path})")
        print("-" * 40)
        try:
            remote_branch = _remote_git(remote_host, remote_path, "branch --show-current")
            remote_head = _remote_git(remote_host, remote_path, "rev-parse HEAD")
            remote_porcelain = _remote_git(remote_host, remote_path, "status --porcelain")
        except RuntimeError as exc:
            has_error = True
            notes.append(f"❌ SSH/git failed on DS723+: {exc}")
            remote_ok = False
        else:
            remote_dirty = _porcelain_is_dirty(remote_porcelain)
            remote_on_production = remote_branch == TARGET_BRANCH

            print(f"Remote DS723 branch: {remote_branch}")
            print(f"Remote DS723 HEAD: {remote_head}")
            print(f"Remote DS723 working tree: {'dirty' if remote_dirty else 'clean'}")
            print()

            if not remote_on_production:
                has_error = True
                notes.append(f"❌ remote not on {TARGET_BRANCH} branch")
                remote_ok = False
            else:
                notes.append(f"✅ remote on {TARGET_BRANCH} branch")

            if remote_dirty:
                has_warning = True
                notes.append("⚠️  remote working tree dirty")
                remote_ok = False
            else:
                notes.append("✅ remote working tree clean")

            if remote_head == origin_head:
                notes.append("✅ remote HEAD matches origin/production")
            else:
                try:
                    rb_counts = _git(
                        "rev-list",
                        "--left-right",
                        "--count",
                        f"{origin_head}...{remote_head}",
                    )
                    r_behind_s, r_ahead_s = rb_counts.split("\t", 1)
                    r_behind = int(r_behind_s)
                    r_ahead = int(r_ahead_s)
                except RuntimeError:
                    r_behind = r_ahead = -1

                if r_behind > 0:
                    has_warning = True
                    remote_ok = False
                    notes.append(f"⚠️  DS723+ behind origin/{TARGET_BRANCH} ({r_behind} commit(s))")
                if r_ahead > 0:
                    has_warning = True
                    remote_ok = False
                    notes.append(f"⚠️  DS723+ ahead of origin/{TARGET_BRANCH} ({r_ahead} commit(s))")
                if r_behind == 0 and r_ahead == 0 and remote_head != origin_head:
                    has_warning = True
                    remote_ok = False
                    notes.append("⚠️  remote HEAD differs from origin/production")

            print("Sync summary:")
            print(f"  Mac mini : {_short_sha(local_head)}")
            print(f"  GitHub   : {_short_sha(origin_head)}")
            print(f"  DS723+   : {_short_sha(remote_head)}")
            if remote_head == origin_head:
                print("  ✅ DS723+ matches GitHub (origin/production)")
            elif remote_ok is False:
                print("  ⚠️  DS723+ out of sync with GitHub (origin/production)")
            print()

    for note in notes:
        print(note)

    print("\n" + "=" * 40)
    if has_error:
        print("Status: ERROR")
        return 1
    if has_warning:
        print("Status: WARNING")
        return 1
    if local_ok and (remote != "ds723" or remote_ok):
        print("Status: OK")
        return 0

    print("Status: WARNING")
    return 1


def run_api_guardian() -> int:
    print("IFG Guardian MVP")
    print("=" * 40)

    frontend_endpoints = _extract_frontend_endpoints()
    backend_endpoints, router_defs = _extract_backend_endpoints()
    imported, included = _parse_main_registrations()

    has_errors = False

    print("\nFrontend → Backend endpoints:\n")
    if not frontend_endpoints:
        print("⚠️  Brak wywołań apiClient w mobile-expo/src/api/")
    for fe in frontend_endpoints:
        match = _find_backend_match(fe, backend_endpoints)
        if match:
            print(f"✅ {fe.method.upper()} {fe.path}  ({fe.source}) → {match.source}")
        else:
            has_errors = True
            print(f"❌ {fe.method.upper()} {fe.path}  ({fe.source}) → endpoint missing")

    print("\nRouter registration (app/main.py):\n")
    seen_routers: set[tuple[str, str]] = set()
    for router_def in router_defs:
        key = (router_def.module, router_def.variable)
        if key in seen_routers:
            continue
        seen_routers.add(key)

        module_imports = imported.get(router_def.module, set())
        is_imported = router_def.variable in module_imports or bool(
            module_imports & included
        )
        is_included = _is_router_registered(router_def, imported, included)

        if is_imported and is_included:
            prefix_label = router_def.prefix or "(no prefix)"
            print(
                f"✅ {router_def.source} [{router_def.variable}, prefix={prefix_label}] → registered"
            )
        else:
            has_errors = True
            print(
                f"⚠️  {router_def.source} [{router_def.variable}] → router not registered in app/main.py"
            )

    print("\n" + "=" * 40)
    if has_errors:
        print("Guardian: FAILED")
        return 1

    print("Guardian: OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="IFG Guardian MVP")
    parser.add_argument(
        "--repo-sync",
        action="store_true",
        help="Sprawdź synchronizację repo (Mac mini ↔ GitHub ↔ DS723+)",
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Przed --repo-sync wykonaj git fetch origin production",
    )
    parser.add_argument(
        "--remote",
        choices=["ds723"],
        help="Porównaj stan repo zdalnego DS723+ przez SSH",
    )
    parser.add_argument(
        "--remote-host",
        default=DEFAULT_REMOTE_HOST,
        help=f"Host SSH (domyślnie: {DEFAULT_REMOTE_HOST})",
    )
    parser.add_argument(
        "--remote-path",
        default=DEFAULT_REMOTE_PATH,
        help=f"Ścieżka repo na hoście zdalnym (domyślnie: {DEFAULT_REMOTE_PATH})",
    )
    args = parser.parse_args()

    if args.repo_sync:
        return run_repo_sync(
            do_fetch=args.fetch,
            remote=args.remote,
            remote_host=args.remote_host,
            remote_path=args.remote_path,
        )
    return run_api_guardian()


if __name__ == "__main__":
    sys.exit(main())
