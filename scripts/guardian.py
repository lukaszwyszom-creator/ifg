#!/usr/bin/env python3
"""IFG Guardian MVP — weryfikuje zgodność endpointów mobile-expo z backendem IFG."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET_BRANCH = "production"
DEFAULT_REMOTE_HOST = "ds723"
DEFAULT_REMOTE_PATH = "/volume1/docker/ifg_v2/ifg_standalone"
REQUIRED_COMPOSE_SERVICES = ("api", "worker", "db")
COMPOSE_FILE = "docker/docker-compose.prod.yml"

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


def _resolve_ds723_host(cli_host: str | None) -> str:
    if cli_host is not None:
        return cli_host
    return os.environ.get("IFG_DS723_HOST", DEFAULT_REMOTE_HOST)


def _container_state_ok(state: str) -> bool:
    normalized = state.lower()
    if any(bad in normalized for bad in ("exited", "dead", "restarting", "paused")):
        return False
    return "running" in normalized or re.search(r"\bup\b", normalized) is not None


def _parse_compose_service_states(ps_output: str) -> dict[str, str]:
    """Parsuje `docker compose ps` (format tabelaryczny lub --format)."""
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


def _compose_services_healthy(states: dict[str, str]) -> tuple[bool, list[str]]:
    problems: list[str] = []
    for svc in REQUIRED_COMPOSE_SERVICES:
        raw = states.get(svc)
        if raw is None:
            problems.append(f"{svc}: brak w docker compose ps")
        elif not service_state_is_running(raw):
            problems.append(f"{svc}: {raw}")
    return not problems, problems


def parse_compose_service_states(ps_output: str) -> dict[str, str]:
    """Publiczny parser `docker compose ps` dla api/worker/db."""
    return _parse_compose_service_states(ps_output)


def service_state_is_running(state_line: str | None) -> bool:
    if not state_line:
        return False
    return _container_state_ok(state_line)


def service_state_is_restarting(state_line: str | None) -> bool:
    if not state_line:
        return False
    return "restarting" in state_line.lower()


def service_state_is_healthy(state_line: str | None) -> bool:
    if not state_line:
        return False
    normalized = state_line.lower()
    return "healthy" in normalized and "unhealthy" not in normalized


def _remote_compose_ps(host: str, repo_path: str) -> str:
    compose_cmd = (
        f"cd {repo_path} && sudo docker compose -f {COMPOSE_FILE} ps "
        "--format '{{.Service}}\t{{.State}}'"
    )
    try:
        return _ssh(host, compose_cmd)
    except RuntimeError:
        return _ssh(host, f"cd {repo_path} && sudo docker compose -f {COMPOSE_FILE} ps")


def _dist_js_blobs() -> str:
    dist_assets = ROOT / "frontend-react" / "dist" / "assets"
    if not dist_assets.is_dir():
        return ""
    return "\n".join(
        js_file.read_text(encoding="utf-8", errors="replace")
        for js_file in sorted(dist_assets.glob("*.js"))
    )


FRONTEND_SRC_PREFIX = "frontend-react/src"
FRONTEND_DIST_STALE_MSG = "Frontend dist wymaga przebudowy (npm run build)."
KSEF_CONNECT_JS_MARKERS = ("openSessionOnce", "openSession: (nip) => openSessionOnce(nip)")
KSEF_CONNECT_TILE_MARKERS = ("actionInFlightRef", "response?.status === 409")
KSEF_CONNECT_DIST_MARKERS = (
    "KSeFConnectionTile.connect",
    "Sesja KSeF jest już aktywna",
)


def _frontend_src_last_commit_epoch() -> int | None:
    try:
        return int(_git("log", "-1", "--format=%ct", "--", FRONTEND_SRC_PREFIX))
    except RuntimeError:
        return None


def _frontend_dist_newest_epoch() -> float | None:
    dist_assets = ROOT / "frontend-react" / "dist" / "assets"
    if not dist_assets.is_dir():
        return None
    js_files = list(dist_assets.glob("*.js"))
    if not js_files:
        return None
    return max(f.stat().st_mtime for f in js_files)


def _frontend_src_dirty_max_mtime() -> float | None:
    try:
        porcelain = _git("status", "--porcelain", "--", FRONTEND_SRC_PREFIX)
    except RuntimeError:
        return None
    max_mtime: float | None = None
    for line in porcelain.splitlines():
        if not line.strip():
            continue
        path_part = line[3:].strip()
        if " -> " in path_part:
            path_part = path_part.split(" -> ", 1)[1]
        path = ROOT / path_part
        if path.is_file():
            max_mtime = max(max_mtime or 0.0, path.stat().st_mtime)
    return max_mtime


def check_frontend_worktree_requires_build(*, label: str = "lokalnie") -> tuple[bool, str]:
    dirty_mtime = _frontend_src_dirty_max_mtime()
    if dirty_mtime is None:
        return True, f"✅ [{label}] brak niezcommitowanych zmian {FRONTEND_SRC_PREFIX}"
    dist_ts = _frontend_dist_newest_epoch()
    if dist_ts is None:
        return False, (
            f"❌ [{label}] niezcommitowane zmiany {FRONTEND_SRC_PREFIX} — "
            f"brak dist (cd frontend-react && npm run build)"
        )
    if dist_ts < dirty_mtime:
        return False, (
            f"❌ [{label}] niezcommitowane zmiany {FRONTEND_SRC_PREFIX} — "
            f"dist nieaktualny (cd frontend-react && npm run build)"
        )
    return True, f"✅ [{label}] dist nowszy niż niezcommitowane zmiany src"


def check_ksef_connect_button_fix() -> tuple[bool, list[str]]:
    notes: list[str] = []
    ok = True

    ksef_js = ROOT / "frontend-react" / "src" / "api" / "ksef.js"
    tile = ROOT / "frontend-react" / "src" / "components" / "layout" / "KSeFConnectionTile.jsx"

    if not ksef_js.is_file():
        ok = False
        notes.append("❌ brak frontend-react/src/api/ksef.js")
    else:
        js_source = ksef_js.read_text(encoding="utf-8")
        if all(marker in js_source for marker in KSEF_CONNECT_JS_MARKERS):
            notes.append("✅ ksef.js: openSessionOnce + dedupe connect")
        else:
            ok = False
            notes.append("❌ ksef.js: brak openSessionOnce (KSEF_CONNECT_BUTTON_FIX)")

    if not tile.is_file():
        ok = False
        notes.append("❌ brak KSeFConnectionTile.jsx")
    else:
        tile_source = tile.read_text(encoding="utf-8")
        if all(marker in tile_source for marker in KSEF_CONNECT_TILE_MARKERS):
            notes.append("✅ KSeFConnectionTile: actionInFlightRef + obsługa 409")
        else:
            ok = False
            notes.append("❌ KSeFConnectionTile: brak guard/409 (KSEF_CONNECT_BUTTON_FIX)")

    dist_blob = _dist_js_blobs()
    if not dist_blob:
        ok = False
        notes.append("❌ dist/assets/*.js — brak bundle (npm run build)")
    elif all(marker in dist_blob for marker in KSEF_CONNECT_DIST_MARKERS):
        notes.append("✅ dist zawiera markery connect fix (409 fallback + connect sync trigger)")
    else:
        ok = False
        notes.append(
            "❌ dist NIE zawiera connect fix — wymagany: cd frontend-react && npm run build"
        )

    return ok, notes


def check_frontend_dist_freshness(*, label: str = "lokalnie") -> tuple[bool, str]:
    commit_ts = _frontend_src_last_commit_epoch()
    dist_ts = _frontend_dist_newest_epoch()
    if dist_ts is None:
        return False, f"❌ [{label}] {FRONTEND_DIST_STALE_MSG}"
    try:
        src_head = _git("log", "-1", "--format=%H", "--", FRONTEND_SRC_PREFIX)
        dist_head = _git("log", "-1", "--format=%H", "--", "frontend-react/dist")
        if src_head == dist_head:
            return True, (
                f"✅ [{label}] dist i src w tym samym commicie ({src_head[:7]})"
            )
    except RuntimeError:
        pass
    if commit_ts is None:
        return True, f"✅ [{label}] brak historii commitów {FRONTEND_SRC_PREFIX} (pominięto)"
    if dist_ts < commit_ts:
        try:
            commit_ref = _git("log", "-1", "--format=%h", "--", FRONTEND_SRC_PREFIX)
        except RuntimeError:
            commit_ref = "?"
        return False, (
            f"❌ [{label}] {FRONTEND_DIST_STALE_MSG} "
            f"(dist starszy niż commit {commit_ref} w {FRONTEND_SRC_PREFIX})"
        )
    return True, f"✅ [{label}] frontend-react/dist aktualny względem ostatniego commita src"


def _remote_frontend_dist_newest_epoch(host: str, repo_path: str) -> float | None:
    quoted_path = repo_path.replace("'", "'\"'\"'")
    raw = _ssh(
        host,
        "cd '" + quoted_path + "' && "
        "ls frontend-react/dist/assets/*.js 2>/dev/null | "
        "xargs stat -c %Y 2>/dev/null | sort -n | tail -1",
    )
    if not raw:
        return None
    try:
        return float(raw.splitlines()[-1].strip())
    except ValueError:
        return None


def check_remote_frontend_dist_freshness(host: str, repo_path: str) -> tuple[bool, str]:
    try:
        src_head = _remote_git(
            host, repo_path, f"log -1 --format=%H -- {FRONTEND_SRC_PREFIX}"
        )
        dist_head = _remote_git(
            host, repo_path, "log -1 --format=%H -- frontend-react/dist"
        )
        if src_head == dist_head:
            return True, f"✅ [DS723+] dist i src w tym samym commicie ({src_head[:7]})"
        commit_ts = int(
            _remote_git(host, repo_path, f"log -1 --format=%ct -- {FRONTEND_SRC_PREFIX}")
        )
    except RuntimeError as exc:
        return False, f"❌ [DS723+] nie udało się odczytać commita src: {exc}"
    dist_ts = _remote_frontend_dist_newest_epoch(host, repo_path)
    if dist_ts is None:
        return False, f"❌ [DS723+] {FRONTEND_DIST_STALE_MSG}"
    if dist_ts < commit_ts:
        try:
            commit_ref = _remote_git(
                host, repo_path, f"log -1 --format=%h -- {FRONTEND_SRC_PREFIX}"
            )
        except RuntimeError:
            commit_ref = "?"
        return False, (
            f"❌ [DS723+] {FRONTEND_DIST_STALE_MSG} "
            f"(dist starszy niż commit {commit_ref} w {FRONTEND_SRC_PREFIX})"
        )
    return True, "✅ [DS723+] frontend-react/dist aktualny względem ostatniego commita src"


def _fetch_openapi_text() -> tuple[str | None, str]:
    import urllib.error
    import urllib.request

    for url in (
        os.environ.get("IFG_OPENAPI_URL", "http://127.0.0.1:8000/openapi.json"),
        str(ROOT / "openapi.json"),
    ):
        if url.startswith("http"):
            try:
                with urllib.request.urlopen(url, timeout=5) as resp:
                    return resp.read().decode("utf-8", errors="replace"), url
            except (urllib.error.URLError, TimeoutError, OSError):
                continue
        else:
            path = Path(url)
            if path.is_file():
                return path.read_text(encoding="utf-8", errors="replace"), str(path)
    return None, ""


def run_ksef_async_check() -> int:
    print("IFG Guardian KSeF Async Sync Check")
    print("=" * 40)

    has_error = False
    notes: list[str] = []

    components_dir = ROOT / "frontend-react" / "src" / "components"
    sync_hits: list[str] = []
    if components_dir.is_dir():
        for jsx in sorted(components_dir.rglob("*.jsx")):
            text = jsx.read_text(encoding="utf-8")
            if "syncPurchasesNow(" in text:
                sync_hits.append(jsx.relative_to(ROOT).as_posix())

    if sync_hits:
        has_error = True
        notes.append(f"❌ syncPurchasesNow( w komponentach: {', '.join(sync_hits)}")
    else:
        notes.append("✅ brak syncPurchasesNow( w frontend-react/src/components")

    ksef_api = ROOT / "frontend-react" / "src" / "api" / "ksef.js"
    if not ksef_api.is_file():
        has_error = True
        notes.append("❌ brak frontend-react/src/api/ksef.js")
    else:
        source = ksef_api.read_text(encoding="utf-8")
        if "runPurchaseSync" in source and "err.response?.status === 404" in source:
            notes.append("✅ ksef.js: runPurchaseSync + fallback tylko 404")
        else:
            has_error = True
            notes.append("❌ ksef.js: brak runPurchaseSync lub fallback 404")

    dist_blob = _dist_js_blobs()
    if not dist_blob:
        has_error = True
        notes.append("⚠️  frontend-react/dist/assets/*.js — brak (uruchom npm run build)")
    elif "runPurchaseSync" in dist_blob:
        notes.append("✅ dist zawiera runPurchaseSync")
    else:
        has_error = True
        notes.append("❌ dist NIE zawiera runPurchaseSync")

    if dist_blob:
        if "syncPurchasesNow(!1" in dist_blob or "syncPurchasesNow(false" in dist_blob:
            has_error = True
            notes.append("❌ dist zawiera syncPurchasesNow(!1/false — stary fallback w bundle")
        else:
            notes.append("✅ dist NIE zawiera syncPurchasesNow(!1/false")

    dist_ok, dist_note = check_frontend_dist_freshness()
    if not dist_ok:
        has_error = True
    notes.append(dist_note)

    worktree_ok, worktree_note = check_frontend_worktree_requires_build()
    if not worktree_ok:
        has_error = True
    notes.append(worktree_note)

    connect_ok, connect_notes = check_ksef_connect_button_fix()
    if not connect_ok:
        has_error = True
    notes.extend(connect_notes)

    openapi_text, openapi_src = _fetch_openapi_text()
    if openapi_text is None:
        has_error = True
        notes.append("⚠️  openapi.json niedostępny (API offline?)")
    elif "/api/v1/ksef-sessions/sync-purchase" in openapi_text:
        notes.append(f"✅ openapi zawiera /api/v1/ksef-sessions/sync-purchase ({openapi_src})")
    else:
        has_error = True
        notes.append(f"❌ openapi bez /api/v1/ksef-sessions/sync-purchase ({openapi_src})")

    print()
    for note in notes:
        print(note)

    print("\n" + "-" * 40)
    print("Obserwacja logów DS723+ (tylko odczyt):")
    print(
        f"  sudo docker compose -f {COMPOSE_FILE} logs -f api | grep KSEF_ASYNC_SYNC"
    )
    print(
        f"  sudo docker compose -f {COMPOSE_FILE} logs -f worker | grep KSEF_ASYNC_SYNC"
    )

    print("\n" + "=" * 40)
    if has_error:
        print("Status: ERROR")
        return 1
    print("Status: OK")
    return 0


def run_deploy_check(
    *,
    remote_host: str | None = None,
    remote_path: str = DEFAULT_REMOTE_PATH,
) -> int:
    host = _resolve_ds723_host(remote_host)

    print("IFG Guardian Deploy Check")
    print("Mac mini → DS723+")
    print("=" * 40)

    try:
        local_branch = _git("branch", "--show-current")
        local_head = _git("rev-parse", "HEAD")
        local_status = _git("status", "--short")
    except RuntimeError as exc:
        print(f"\n❌ Nie udało się odczytać stanu lokalnego repo: {exc}")
        print("\nWerdykt: NIE MOŻNA POTWIERDZIĆ — BRAK SSH / BŁĄD UPRAWNIEŃ")
        return 1

    local_dirty = _porcelain_is_dirty(local_status)
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
    remote_dist_note = ""
    containers_ok: bool | None = None
    container_problems: list[str] = []
    remote_branch = remote_head = remote_status = ""

    print(f"\nZdalnie (DS723+ — {host}:{remote_path}):")
    print("-" * 40)
    try:
        remote_branch = _remote_git(host, remote_path, "branch --show-current")
        remote_head = _remote_git(host, remote_path, "rev-parse HEAD")
        remote_status = _remote_git(host, remote_path, "status --short")
        compose_ps = _remote_compose_ps(host, remote_path)
    except RuntimeError as exc:
        ssh_ok = False
        print(f"  ❌ SSH / odczyt zdalny nieudany: {exc}")
    else:
        remote_dirty = _porcelain_is_dirty(remote_status)
        branch_match = local_branch == remote_branch
        commit_match = local_head == remote_head
        remote_dist_ok, remote_dist_note = check_remote_frontend_dist_freshness(host, remote_path)
        service_states = _parse_compose_service_states(compose_ps)
        containers_ok, container_problems = _compose_services_healthy(service_states)

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
          f"  (local: {_short_sha(local_head)}, DS723+: {_short_sha(remote_head)})")

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
    if ssh_ok and remote_dist_ok is not None:
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
    parser = argparse.ArgumentParser(
        description=(
            "IFG Guardian — weryfikacja zgodności API (mobile-expo ↔ backend) "
            "oraz kontrola wdrożenia Mac mini ↔ DS723+."
        ),
        epilog=(
            "Przykłady:\n"
            "  python3 scripts/guardian.py\n"
            "      Sprawdź endpointy mobile-expo vs backend (domyślnie).\n"
            "  python3 scripts/guardian.py --deploy-check\n"
            "      Porównaj branch/HEAD/repo i kontenery DS723+ z lokalnym kodem.\n"
            "  python3 scripts/guardian.py --ksef-async-check\n"
            "      Sprawdź bundle frontendu i endpoint async sync KSeF.\n"
            "  python3 scripts/guardian.py --repo-sync --remote ds723 --fetch\n"
            "      Porównaj Mac mini, origin/production i DS723+ (git only).\n"
            "\n"
            "Zmienne środowiskowe:\n"
            "  IFG_DS723_HOST   Host SSH DS723+ (domyślnie: ds723)\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--ksef-async-check",
        action="store_true",
        help=(
            "Kontrola async sync KSeF: brak syncPurchasesNow w UI, runPurchaseSync w dist, "
            "świeżość frontend-react/dist, endpoint w openapi.json"
        ),
    )
    parser.add_argument(
        "--deploy-check",
        action="store_true",
        help=(
            "Kontrola wdrożenia Mac mini → DS723+: branch, HEAD, git status, "
            "świeżość frontend-react/dist, docker compose ps (tylko odczyt, bez deploy/restart/pull)"
        ),
    )
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
        help="Porównaj stan repo zdalnego DS723+ przez SSH (--repo-sync)",
    )
    parser.add_argument(
        "--remote-host",
        default=None,
        help=f"Host SSH DS723+ (domyślnie: IFG_DS723_HOST lub {DEFAULT_REMOTE_HOST})",
    )
    parser.add_argument(
        "--remote-path",
        default=DEFAULT_REMOTE_PATH,
        help=f"Ścieżka repo na hoście zdalnym (domyślnie: {DEFAULT_REMOTE_PATH})",
    )
    args = parser.parse_args()

    if args.deploy_check:
        return run_deploy_check(
            remote_host=args.remote_host,
            remote_path=args.remote_path,
        )
    if args.ksef_async_check:
        return run_ksef_async_check()
    if args.repo_sync:
        return run_repo_sync(
            do_fetch=args.fetch,
            remote=args.remote,
            remote_host=_resolve_ds723_host(args.remote_host),
            remote_path=args.remote_path,
        )
    return run_api_guardian()


if __name__ == "__main__":
    sys.exit(main())
