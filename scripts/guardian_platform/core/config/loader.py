from __future__ import annotations

from pathlib import Path

from guardian_platform.core.config.models import ProjectConfig


def _find_config_file(start: Path) -> Path | None:
    current = start.resolve()
    for _ in range(8):
        for name in (".guardian.yml", ".guardian.yaml"):
            path = current / name
            if path.is_file():
                return path
        nested = current / ".guardian" / "project.yaml"
        if nested.is_file():
            return nested
        if current.parent == current:
            break
        current = current.parent
    return None


def _parse_profiles_active(lines: list[str]) -> list[str]:
    active: list[str] = []
    in_active = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("active:"):
            in_active = True
            continue
        if in_active:
            if stripped.startswith("- "):
                active.append(stripped[2:].strip())
            elif stripped and not stripped.startswith("#"):
                break
    return active


def load_project_config(*, root: Path | None = None) -> ProjectConfig:
    start = (root or Path.cwd()).resolve()
    path = _find_config_file(start)
    base = start
    if path is not None:
        base = path.parent if path.name != "project.yaml" else path.parent.parent
    config = ProjectConfig.defaults(base)
    if path is None:
        return config

    lines = path.read_text(encoding="utf-8").splitlines()
    active = _parse_profiles_active(lines)
    if active:
        config.active_profiles = active

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("reports_dir:"):
            value = stripped.split(":", 1)[1].strip()
            if value:
                config.reports_dir = (config.root / value).resolve()

    return config
