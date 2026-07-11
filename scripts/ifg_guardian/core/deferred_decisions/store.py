from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from ifg_guardian.config import ROOT
from ifg_guardian.core.deferred_decisions.integrity import ValidationReport, validate_store
from ifg_guardian.core.deferred_decisions.locking import GddRegistryLock
from ifg_guardian.core.deferred_decisions.models import DeferredDecisionStore

DEFAULT_STORE_PATH = ROOT / "docs" / "guardian" / "deferred_decisions.json"
BACKUP_DIR = ROOT / ".state" / "gdd_backups"


class GddStoreError(ValueError):
    pass


class GddIntegrityError(GddStoreError):
    def __init__(self, message: str, report: ValidationReport) -> None:
        super().__init__(message)
        self.report = report


def load_store(path: Path | None = None, *, validate: bool = False) -> DeferredDecisionStore:
    store_path = path or DEFAULT_STORE_PATH
    if not store_path.exists():
        return DeferredDecisionStore()
    try:
        payload = json.loads(store_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GddStoreError(f"invalid GDD store: {store_path}") from exc
    if not isinstance(payload, dict):
        raise GddStoreError(f"invalid GDD store root: {store_path}")
    store = DeferredDecisionStore.from_dict(payload)
    if validate:
        report = validate_store(store)
        if not report.valid:
            raise GddIntegrityError("GDD registry integrity violation on load", report)
    return store


def backup_store(path: Path) -> Path | None:
    if not path.is_file():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"deferred_decisions_{stamp}.json"
    shutil.copy2(path, backup_path)
    return backup_path


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def save_store(
    store: DeferredDecisionStore,
    path: Path | None = None,
    *,
    validate: bool = True,
    backup: bool = True,
    use_lock: bool = True,
) -> Path:
    store_path = path or DEFAULT_STORE_PATH
    if validate:
        report = validate_store(store)
        if not report.valid:
            raise GddIntegrityError("Refusing to save invalid GDD registry", report)

    payload = json.dumps(store.to_dict(), ensure_ascii=False, indent=2) + "\n"

    def _write() -> Path:
        if backup and store_path.is_file():
            backup_store(store_path)
        _atomic_write_text(store_path, payload)
        return store_path

    if use_lock:
        with GddRegistryLock():
            return _write()
    return _write()
