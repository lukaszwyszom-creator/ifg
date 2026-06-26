from __future__ import annotations

import re
from dataclasses import dataclass

from ifg_guardian.config import MAIN_FILE, MOBILE_API_GLOB, ROUTER_GLOB, ROOT

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
            endpoints.append(Endpoint(method=method, path=_normalize_path(raw_path), source=rel))
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
                RouterDef(module=module, variable=var_name, prefix=prefix, source=rel)
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


def _find_backend_match(frontend: Endpoint, backend_endpoints: list[Endpoint]) -> Endpoint | None:
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
    if router_def.variable in included:
        return True
    for name in included:
        if name in module_imports:
            return True
    return any(name in included for name in module_imports if router_def.variable in name or name.endswith("_router"))


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
        is_imported = router_def.variable in module_imports or bool(module_imports & included)
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
