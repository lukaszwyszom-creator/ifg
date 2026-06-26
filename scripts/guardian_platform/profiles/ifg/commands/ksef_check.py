from __future__ import annotations

import os
import urllib.error
import urllib.request
from pathlib import Path

from guardian_platform.core.runtime.context import CommandContext
from guardian_platform.profiles.ifg.checks.frontend import (
    check_frontend_dist_freshness,
    check_frontend_worktree_requires_build,
    check_ksef_connect_button_fix,
    dist_js_blobs,
)
from guardian_platform.profiles.ifg.config.defaults import COMPOSE_FILE, REPO_ROOT


def fetch_openapi_text() -> tuple[str | None, str]:
    for url in (
        os.environ.get("IFG_OPENAPI_URL", "http://127.0.0.1:8000/openapi.json"),
        str(REPO_ROOT / "openapi.json"),
    ):
        if url.startswith("http"):
            try:
                with urllib.request.urlopen(url, timeout=5) as resp:
                    return resp.read().decode("utf-8", errors="replace"), url
            except (urllib.error.URLError, TimeoutError, OSError):
                continue
        else:
            path = Path(url)
            if path.is_file():
                return path.read_text(encoding="utf-8", errors="replace"), str(path)
    return None, ""


def run_ksef_check(ctx: CommandContext) -> int:
    print("IFG Guardian KSeF Async Sync Check")
    print("=" * 40)

    has_error = False
    notes: list[str] = []

    components_dir = REPO_ROOT / "frontend-react" / "src" / "components"
    sync_hits: list[str] = []
    if components_dir.is_dir():
        for jsx in sorted(components_dir.rglob("*.jsx")):
            text = jsx.read_text(encoding="utf-8")
            if "syncPurchasesNow(" in text:
                sync_hits.append(jsx.relative_to(REPO_ROOT).as_posix())

    if sync_hits:
        has_error = True
        notes.append(f"❌ syncPurchasesNow( w komponentach: {', '.join(sync_hits)}")
    else:
        notes.append("✅ brak syncPurchasesNow( w frontend-react/src/components")

    ksef_api = REPO_ROOT / "frontend-react" / "src" / "api" / "ksef.js"
    if not ksef_api.is_file():
        has_error = True
        notes.append("❌ brak frontend-react/src/api/ksef.js")
    else:
        source = ksef_api.read_text(encoding="utf-8")
        if "runPurchaseSync" in source and "err.response?.status === 404" in source:
            notes.append("✅ ksef.js: runPurchaseSync + fallback tylko 404")
        else:
            has_error = True
            notes.append("❌ ksef.js: brak runPurchaseSync lub fallback 404")

    dist_blob = dist_js_blobs()
    if not dist_blob:
        has_error = True
        notes.append("⚠️  frontend-react/dist/assets/*.js — brak (uruchom npm run build)")
    elif "runPurchaseSync" in dist_blob:
        notes.append("✅ dist zawiera runPurchaseSync")
    else:
        has_error = True
        notes.append("❌ dist NIE zawiera runPurchaseSync")

    if dist_blob:
        if "syncPurchasesNow(!1" in dist_blob or "syncPurchasesNow(false" in dist_blob:
            has_error = True
            notes.append("❌ dist zawiera syncPurchasesNow(!1/false — stary fallback w bundle")
        else:
            notes.append("✅ dist NIE zawiera syncPurchasesNow(!1/false")

    dist_ok, dist_note = check_frontend_dist_freshness()
    if not dist_ok:
        has_error = True
    notes.append(dist_note)

    worktree_ok, worktree_note = check_frontend_worktree_requires_build()
    if not worktree_ok:
        has_error = True
    notes.append(worktree_note)

    connect_ok, connect_notes = check_ksef_connect_button_fix()
    if not connect_ok:
        has_error = True
    notes.extend(connect_notes)

    openapi_text, openapi_src = fetch_openapi_text()
    if openapi_text is None:
        has_error = True
        notes.append("⚠️  openapi.json niedostępny (API offline?)")
    elif "/api/v1/ksef-sessions/sync-purchase" in openapi_text:
        notes.append(f"✅ openapi zawiera /api/v1/ksef-sessions/sync-purchase ({openapi_src})")
    else:
        has_error = True
        notes.append(f"❌ openapi bez /api/v1/ksef-sessions/sync-purchase ({openapi_src})")

    print()
    for note in notes:
        print(note)

    print("\n" + "-" * 40)
    print("Obserwacja logów DS723+ (tylko odczyt):")
    print(f"  sudo docker compose -f {COMPOSE_FILE} logs -f api | grep KSEF_ASYNC_SYNC")
    print(f"  sudo docker compose -f {COMPOSE_FILE} logs -f worker | grep KSEF_ASYNC_SYNC")

    print("\n" + "=" * 40)
    if has_error:
        print("Status: ERROR")
        return 1
    print("Status: OK")
    return 0
