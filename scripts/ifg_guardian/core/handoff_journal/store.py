from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from ifg_guardian.config import ROOT
from ifg_guardian.core.handoff_journal.models import HandoffIndex

HANDOFF_DIR = ROOT / "docs" / "handoff"
INDEX_PATH = HANDOFF_DIR / "index.json"
LATEST_PATH = HANDOFF_DIR / "latest.md"


class HandoffStoreError(ValueError):
    pass


def ensure_handoff_dir(path: Path | None = None) -> Path:
    handoff_dir = path or HANDOFF_DIR
    handoff_dir.mkdir(parents=True, exist_ok=True)
    return handoff_dir


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _atomic_write_text(path: Path, content: str) -> None:
    _atomic_write_bytes(path, content.encode("utf-8"))


def load_index(path: Path | None = None) -> HandoffIndex:
    index_path = path or INDEX_PATH
    if not index_path.is_file():
        return HandoffIndex()
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HandoffStoreError(f"invalid handoff index: {index_path}") from exc
    if not isinstance(payload, dict):
        raise HandoffStoreError(f"invalid handoff index root: {index_path}")
    return HandoffIndex.from_dict(payload)


def save_index(index: HandoffIndex, path: Path | None = None) -> Path:
    index_path = path or INDEX_PATH
    ensure_handoff_dir(index_path.parent)
    payload = json.dumps(index.to_dict(), ensure_ascii=False, indent=2) + "\n"
    _atomic_write_text(index_path, payload)
    return index_path


def handoff_path(handoff_id: int, root: Path | None = None) -> Path:
    handoff_dir = ensure_handoff_dir(root or HANDOFF_DIR)
    return handoff_dir / f"handoff-{handoff_id:04d}.md"


def write_latest(content: str, path: Path | None = None) -> Path:
    latest_path = path or LATEST_PATH
    ensure_handoff_dir(latest_path.parent)
    _atomic_write_bytes(latest_path, content.encode("utf-8"))
    return latest_path
