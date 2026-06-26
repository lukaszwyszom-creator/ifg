from __future__ import annotations

import ast
import re
from pathlib import Path

DEFAULT_SCAN_ROOTS = ("app", "scripts", "tests", "agent", "alembic")
SKIP_DIR_NAMES = {
    "__pycache__",
    ".venv",
    ".venv313",
    "node_modules",
    "dist",
    ".git",
    ".pytest_cache",
    "ksef_backend.egg-info",
}
SKIP_FILE_SUFFIXES = {".pyc", ".pyo"}

_PATH_REF_RE = re.compile(
    r"(?<![\w./])(?:app|scripts|tests|agent|alembic)/[\w./-]+\.pyw?(?![\w./])"
)
_BACKTICK_PATH_RE = re.compile(r"`((?:app|scripts|tests|agent|alembic)/[^`\s]+\.py)`")
_COMMAND_SPEC_RE = re.compile(
    r'CommandSpec\s*\(\s*["\']([\w_]+)["\']\s*,\s*\(([^)]+)\)\s*,\s*([\w_]+)'
)
_WORKFLOW_CONST_RE = re.compile(r"([A-Z][A-Z0-9_]+_WORKFLOW)\s*=")
_HANDLER_IMPORT_RE = re.compile(
    r"from\s+guardian_platform\.([\w.]+)\s+import\s+([\w_,\s]+)"
)


def normalize_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def iter_repo_files(root: Path, scan_roots: tuple[str, ...] = DEFAULT_SCAN_ROOTS) -> list[Path]:
    files: list[Path] = []
    for name in scan_roots:
        base = root / name
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            if path.suffix in SKIP_FILE_SUFFIXES:
                continue
            files.append(path)
    return sorted(files)


def iter_doc_files(root: Path) -> list[Path]:
    docs = root / "docs"
    if not docs.exists():
        return []
    return sorted(
        p
        for p in docs.rglob("*")
        if p.is_file() and p.suffix in {".md", ".txt", ".rst"}
    )


def is_python(path: Path) -> bool:
    return path.suffix == ".py"


def is_shell_script(path: Path) -> bool:
    return path.suffix == ".sh"


def module_name_from_path(root: Path, path: Path) -> str:
    rel = path.resolve().relative_to(root.resolve())
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def resolve_import_to_path(root: Path, importer: Path, module: str | None, level: int) -> list[str]:
    """Resolve import target(s) to repo-relative paths."""
    if level > 0:
        rel = importer.resolve().relative_to(root.resolve())
        pkg_parts = list(rel.parent.parts)
        if level > len(pkg_parts):
            return []
        base_parts = pkg_parts[: len(pkg_parts) - level + 1]
        if module:
            base_parts.extend(module.split("."))
        candidate = root.joinpath(*base_parts)
        resolved: list[str] = []
        if candidate.with_suffix(".py").is_file():
            resolved.append(normalize_path(root, candidate.with_suffix(".py")))
        init = candidate / "__init__.py"
        if init.is_file():
            resolved.append(normalize_path(root, init))
        return resolved

    if not module:
        return []

    resolved: list[str] = []
    parts = module.split(".")

    def _append_candidate(base_parts: list[str]) -> None:
        candidate = root.joinpath(*base_parts)
        if candidate.with_suffix(".py").is_file():
            resolved.append(normalize_path(root, candidate.with_suffix(".py")))
        init = candidate / "__init__.py"
        if init.is_file():
            resolved.append(normalize_path(root, init))

    if module.startswith(("app.", "scripts.", "tests.", "agent.", "alembic.")):
        _append_candidate(parts)

    for scan_root in DEFAULT_SCAN_ROOTS:
        _append_candidate([scan_root, *parts])

    return sorted(set(resolved))


def parse_python_imports(root: Path, path: Path) -> tuple[list[str], bool]:
    source = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return [], False

    imports: list[str] = []
    is_entry = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.extend(resolve_import_to_path(root, path, alias.name, 0))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.extend(resolve_import_to_path(root, path, node.module, node.level or 0))
            # from pkg import submodule → pkg/submodule.py
            if node.module and node.names:
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    subpaths = resolve_import_to_path(
                        root,
                        path,
                        f"{node.module}.{alias.name}" if node.level == 0 else alias.name,
                        node.level or 0,
                    )
                    imports.extend(subpaths)
                    if node.level == 0:
                        parts = node.module.split(".") + [alias.name]
                        candidate = root.joinpath(*parts).with_suffix(".py")
                        if candidate.is_file():
                            imports.append(normalize_path(root, candidate))
        elif isinstance(node, ast.If):
            if (
                isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Name)
                and node.test.left.id == "__name__"
            ):
                is_entry = True
    if '__main__' in source and 'if __name__' in source:
        is_entry = True
    return sorted(set(imports)), is_entry


def extract_doc_references(text: str) -> list[str]:
    refs: set[str] = set()
    for match in _PATH_REF_RE.finditer(text):
        refs.add(match.group(0))
    for match in _BACKTICK_PATH_RE.finditer(text):
        refs.add(match.group(1))
    return sorted(refs)


def scan_command_specs(root: Path) -> list[tuple[str, tuple[str, ...], str]]:
    platform = root / "scripts" / "guardian_platform"
    if not platform.exists():
        return []
    results: list[tuple[str, tuple[str, ...], str]] = []
    for path in platform.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in _COMMAND_SPEC_RE.finditer(text):
            profile = match.group(1)
            path_tokens = tuple(
                t.strip().strip('"').strip("'")
                for t in match.group(2).split(",")
                if t.strip()
            )
            handler = match.group(3).strip()
            command_key = " ".join((profile, *path_tokens)) if profile != "core" else " ".join(path_tokens)
            results.append((command_key, path_tokens, handler))
    return results


def scan_workflow_constants(root: Path) -> list[tuple[str, str]]:
    platform = root / "scripts" / "guardian_platform"
    found: list[tuple[str, str]] = []
    if not platform.exists():
        return found
    for path in platform.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in _WORKFLOW_CONST_RE.finditer(text):
            found.append((match.group(1), normalize_path(root, path)))
    return found


def handler_to_module_path(root: Path, handler_name: str, spec_file: Path) -> str | None:
    text = spec_file.read_text(encoding="utf-8", errors="replace")
    pattern = re.compile(rf"from\s+([\w.]+)\s+import\s+[^;\n]*\b{re.escape(handler_name)}\b")
    match = pattern.search(text)
    if not match:
        return None
    module = match.group(1)
    if module.startswith("guardian_platform."):
        module = module[len("guardian_platform.") :]
    parts = ["scripts", "guardian_platform", *module.split(".")]
    candidate = root.joinpath(*parts).with_suffix(".py")
    if candidate.is_file():
        return normalize_path(root, candidate)
    return None


def map_handlers_from_profiles(root: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for spec_file in (root / "scripts" / "guardian_platform").rglob("*.py"):
        text = spec_file.read_text(encoding="utf-8", errors="replace")
        for match in _COMMAND_SPEC_RE.finditer(text):
            profile = match.group(1)
            path_tokens = tuple(
                t.strip().strip('"').strip("'")
                for t in match.group(2).split(",")
                if t.strip()
            )
            handler = match.group(3).strip()
            command_key = " ".join((profile, *path_tokens)) if profile != "core" else " ".join(path_tokens)
            module_path = handler_to_module_path(root, handler, spec_file)
            if module_path:
                mapping[command_key] = module_path
    return mapping
