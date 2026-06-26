from __future__ import annotations

from pathlib import Path


def path_exists(root: Path, relative: str) -> bool:
    return (root / relative).exists()
