"""Klasyfikacja ścieżek wpływających na decyzje deploy IFG."""
from __future__ import annotations

BACKEND_PREFIXES: tuple[str, ...] = (
    "app/",
    "alembic/",
    "docker/",
    "worker/",
    "requirements",
)

BACKEND_EXACT: frozenset[str] = frozenset({
    "pyproject.toml",
    "Dockerfile",
    "docker/Dockerfile",
})

# Kontekst faktycznie kopiowany do obrazu ifg-api (docker/Dockerfile COPY) + Dockerfile.
IMAGE_CONTEXT_PREFIXES: tuple[str, ...] = (
    "app/",
    "alembic/",
)

IMAGE_CONTEXT_EXACT: frozenset[str] = frozenset({
    "pyproject.toml",
    "README.md",
    "alembic.ini",
    "Dockerfile",
    "docker/Dockerfile",
})

FRONTEND_PREFIXES: tuple[str, ...] = (
    "frontend-react/src/",
    "frontend-react/public/",
    "frontend-react/index.html",
    "frontend-react/vite.config",
    "frontend-react/package.json",
)


def is_backend_deploy_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    if normalized in BACKEND_EXACT:
        return True
    return any(normalized.startswith(prefix) for prefix in BACKEND_PREFIXES)


def is_image_context_path(path: str) -> bool:
    """True gdy plik wchodzi w kontekst buildu obrazu API/worker."""
    normalized = path.replace("\\", "/").lstrip("./")
    if normalized in IMAGE_CONTEXT_EXACT:
        return True
    return any(normalized.startswith(prefix) for prefix in IMAGE_CONTEXT_PREFIXES)


def is_frontend_deploy_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    return any(normalized.startswith(prefix) for prefix in FRONTEND_PREFIXES)


def dockerfile_paths() -> tuple[str, str]:
    return "Dockerfile", "docker/Dockerfile"
