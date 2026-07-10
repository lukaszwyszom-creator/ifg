from __future__ import annotations

import json
from pathlib import Path

from ifg_guardian.config import ROOT
from ifg_guardian.core.deferred_decisions.models import DeferredDecisionStore

DEFAULT_STORE_PATH = ROOT / "docs" / "guardian" / "deferred_decisions.json"


def load_store(path: Path | None = None) -> DeferredDecisionStore:
    store_path = path or DEFAULT_STORE_PATH
    if not store_path.exists():
        return DeferredDecisionStore()
    try:
        payload = json.loads(store_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid GDD store: {store_path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"invalid GDD store root: {store_path}")
    return DeferredDecisionStore.from_dict(payload)


def save_store(store: DeferredDecisionStore, path: Path | None = None) -> Path:
    store_path = path or DEFAULT_STORE_PATH
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text(
        json.dumps(store.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return store_path
