"""Atomic JSON state files for Guardian runtime (Mac mini orchestration host)."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, TypeVar

from ifg_guardian.config import ROOT

STATE_DIR = ROOT / ".state"
T = TypeVar("T", bound=dict[str, Any])


def state_path(name: str) -> Path:
    return STATE_DIR / name


def ensure_state_dir() -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_state_dir()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return None
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def load_or_default(path: Path, default: T) -> T:
    loaded = read_json(path)
    if loaded is None:
        return default
    merged = dict(default)
    merged.update(loaded)
    return merged  # type: ignore[return-value]


def delete_state(path: Path) -> bool:
    try:
        if path.is_file():
            path.unlink()
            return True
    except OSError:
        return False
    return False
