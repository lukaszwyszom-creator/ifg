from __future__ import annotations

import fnmatch
import re
from enum import Enum
from pathlib import Path

from guardian_platform.core.repository.models import FileStatus, Recommendation


class ProtectedCategory(str, Enum):
    NONE = "NONE"
    PACKAGE_INIT = "PACKAGE_INIT"
    ALEMBIC = "ALEMBIC"
    DOCUMENTATION = "DOCUMENTATION"
    CONFIGURATION = "CONFIGURATION"
    ENTRYPOINT = "ENTRYPOINT"
    FRAMEWORK = "FRAMEWORK"


_NON_DELETABLE_CATEGORIES = frozenset(
    {
        ProtectedCategory.PACKAGE_INIT,
        ProtectedCategory.ALEMBIC,
        ProtectedCategory.DOCUMENTATION,
        ProtectedCategory.CONFIGURATION,
        ProtectedCategory.ENTRYPOINT,
        ProtectedCategory.FRAMEWORK,
    }
)

_NON_DELETABLE_STATUSES = frozenset(
    {
        FileStatus.PROTECTED,
        FileStatus.ENTRYPOINT,
        FileStatus.FRAMEWORK,
    }
)

_FRAMEWORK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("fastapi_router", re.compile(r"\b(?:APIRouter|include_router|app\.include_router)\b")),
    ("alembic_runtime", re.compile(r"\b(?:alembic\.|op\.(?:create_table|drop_table|add_column|execute))\b")),
    ("celery_worker", re.compile(r"\b(?:Celery\s*\(|@(?:celery|app)\.task\b)")),
    ("typer_cli", re.compile(r"\b(?:typer\.Typer|@app\.command\b)")),
    ("click_cli", re.compile(r"\b(?:click\.command|@click\.(?:command|group))\b")),
    ("pytest_discovery", re.compile(r"\b(?:pytest\.mark|def test_|conftest\b)")),
    ("unittest_discovery", re.compile(r"\b(?:unittest\.main|TestCase\b)")),
)


def detect_framework_signals(source: str, path: str) -> list[str]:
    signals: list[str] = []
    for name, pattern in _FRAMEWORK_PATTERNS:
        if pattern.search(source):
            signals.append(name)
    name = Path(path).name
    if path.startswith("tests/"):
        if name == "conftest.py" or name.startswith("test_"):
            if "pytest_discovery" not in signals:
                signals.append("pytest_discovery")
    return signals


def _basename_matches(name: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(name, pat) for pat in patterns)


def is_documentation_path(path: str) -> bool:
    if path.startswith("docs/"):
        return True
    base = Path(path).name
    return _basename_matches(
        base,
        ("README*", "CHANGELOG*", "LICENSE*", "CONTRIBUTING*"),
    )


def is_configuration_path(path: str) -> bool:
    base = Path(path).name
    if _basename_matches(
        base,
        (
            "pyproject.toml",
            "package.json",
            "package-lock.json",
            "requirements*",
            "docker-compose*",
            "Dockerfile*",
            ".env.example",
            ".guardian.yml",
            ".cursorignore",
            ".gitignore",
        ),
    ):
        return True
    return path.startswith(".github/")


def is_alembic_path(path: str) -> bool:
    return path == "alembic/env.py" or path == "alembic/script.py.mako" or path.startswith("alembic/versions/")


def is_package_init(path: str) -> bool:
    return path.endswith("/__init__.py") or path == "__init__.py"


def is_main_module(path: str) -> bool:
    base = Path(path).name
    return base == "main.py" or base == "__main__.py"


def classify_protected_artifact(
    path: str,
    *,
    source: str = "",
    is_entry_point: bool = False,
    has_console_scripts: bool = False,
) -> tuple[FileStatus | None, ProtectedCategory, str]:
    """Return override status, category, and reason. None status = use normal scoring."""
    if is_documentation_path(path):
        return FileStatus.PROTECTED, ProtectedCategory.DOCUMENTATION, "documentation"

    if is_configuration_path(path):
        return FileStatus.PROTECTED, ProtectedCategory.CONFIGURATION, "configuration"

    if is_alembic_path(path) or path.startswith("alembic/"):
        return FileStatus.PROTECTED, ProtectedCategory.ALEMBIC, "migration system"

    if is_package_init(path):
        return FileStatus.PROTECTED, ProtectedCategory.PACKAGE_INIT, "package marker"

    if is_main_module(path):
        return FileStatus.ENTRYPOINT, ProtectedCategory.ENTRYPOINT, "application entry module"

    if is_entry_point or has_console_scripts:
        return FileStatus.ENTRYPOINT, ProtectedCategory.ENTRYPOINT, "executable entry point"

    framework = detect_framework_signals(source, path)
    if framework:
        return FileStatus.FRAMEWORK, ProtectedCategory.FRAMEWORK, f"framework discovery: {', '.join(framework)}"

    return None, ProtectedCategory.NONE, ""


def recommendation_for_protected(
    status: FileStatus,
    category: ProtectedCategory,
) -> Recommendation:
    if category in _NON_DELETABLE_CATEGORIES or status in _NON_DELETABLE_STATUSES:
        return Recommendation.KEEP
    return Recommendation.REVIEW


def is_non_deletable(analysis_status: FileStatus, category: ProtectedCategory) -> bool:
    return category in _NON_DELETABLE_CATEGORIES or analysis_status in _NON_DELETABLE_STATUSES


def iter_root_config_paths(root: Path) -> list[str]:
    paths: list[str] = []
    for pattern in (
        "pyproject.toml",
        "package.json",
        "package-lock.json",
        "requirements*.txt",
        "docker-compose*.yml",
        "docker-compose*.yaml",
        "Dockerfile*",
        ".env.example",
        ".guardian.yml",
        ".cursorignore",
        ".gitignore",
    ):
        for match in root.glob(pattern):
            if match.is_file():
                paths.append(match.relative_to(root).as_posix())

    github = root / ".github"
    if github.exists():
        for match in github.rglob("*"):
            if match.is_file():
                paths.append(match.relative_to(root).as_posix())

    for pattern in ("README*", "CHANGELOG*", "LICENSE*", "CONTRIBUTING*"):
        for match in root.glob(pattern):
            if match.is_file():
                paths.append(match.relative_to(root).as_posix())

    return sorted(set(paths))
