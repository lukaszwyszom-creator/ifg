from __future__ import annotations

import os
from pathlib import Path

from ifg_guardian.config import (
    FRONTEND_DIST_STALE_MSG,
    FRONTEND_SRC_PREFIX,
    KSEF_CONNECT_DIST_MARKERS,
    KSEF_CONNECT_JS_MARKERS,
    KSEF_CONNECT_TILE_MARKERS,
    ROOT,
)
from ifg_guardian.core.git import git, parse_porcelain_line
from ifg_guardian.core.ssh import remote_git, ssh


def dist_js_blobs() -> str:
    dist_assets = ROOT / "frontend-react" / "dist" / "assets"
    if not dist_assets.is_dir():
        return ""
    return "\n".join(
        js_file.read_text(encoding="utf-8", errors="replace")
        for js_file in sorted(dist_assets.glob("*.js"))
    )


def frontend_src_last_commit_epoch() -> int | None:
    try:
        return int(git("log", "-1", "--format=%ct", "--", FRONTEND_SRC_PREFIX))
    except RuntimeError:
        return None


def frontend_dist_newest_epoch() -> float | None:
    dist_assets = ROOT / "frontend-react" / "dist" / "assets"
    if not dist_assets.is_dir():
        return None
    js_files = list(dist_assets.glob("*.js"))
    if not js_files:
        return None
    return max(f.stat().st_mtime for f in js_files)


def frontend_src_dirty_max_mtime() -> float | None:
    try:
        porcelain = git("status", "--porcelain", "--", FRONTEND_SRC_PREFIX)
    except RuntimeError:
        return None
    max_mtime: float | None = None
    for line in porcelain.splitlines():
        if not line.strip():
            continue
        _, path_part = parse_porcelain_line(line)
        if not path_part:
            continue
        path = ROOT / path_part
        if path.is_file():
            max_mtime = max(max_mtime or 0.0, path.stat().st_mtime)
    return max_mtime


def check_frontend_worktree_requires_build(*, label: str = "lokalnie") -> tuple[bool, str]:
    dirty_mtime = frontend_src_dirty_max_mtime()
    if dirty_mtime is None:
        return True, f"✅ [{label}] brak niezcommitowanych zmian {FRONTEND_SRC_PREFIX}"
    dist_ts = frontend_dist_newest_epoch()
    if dist_ts is None:
        return False, (
            f"❌ [{label}] niezcommitowane zmiany {FRONTEND_SRC_PREFIX} — "
            f"brak dist (cd frontend-react && npm run build)"
        )
    if dist_ts < dirty_mtime:
        return False, (
            f"❌ [{label}] niezcommitowane zmiany {FRONTEND_SRC_PREFIX} — "
            f"dist nieaktualny (cd frontend-react && npm run build)"
        )
    return True, f"✅ [{label}] dist nowszy niż niezcommitowane zmiany src"


def check_ksef_connect_button_fix() -> tuple[bool, list[str]]:
    notes: list[str] = []
    ok = True
    ksef_js = ROOT / "frontend-react" / "src" / "api" / "ksef.js"
    tile = ROOT / "frontend-react" / "src" / "components" / "layout" / "KSeFConnectionTile.jsx"

    if not ksef_js.is_file():
        ok = False
        notes.append("❌ brak frontend-react/src/api/ksef.js")
    else:
        js_source = ksef_js.read_text(encoding="utf-8")
        if all(marker in js_source for marker in KSEF_CONNECT_JS_MARKERS):
            notes.append("✅ ksef.js: openSessionOnce + dedupe connect")
        else:
            ok = False
            notes.append("❌ ksef.js: brak openSessionOnce (KSEF_CONNECT_BUTTON_FIX)")

    if not tile.is_file():
        ok = False
        notes.append("❌ brak KSeFConnectionTile.jsx")
    else:
        tile_source = tile.read_text(encoding="utf-8")
        if all(marker in tile_source for marker in KSEF_CONNECT_TILE_MARKERS):
            notes.append("✅ KSeFConnectionTile: actionInFlightRef + obsługa 409")
        else:
            ok = False
            notes.append("❌ KSeFConnectionTile: brak guard/409 (KSEF_CONNECT_BUTTON_FIX)")

    dist_blob = dist_js_blobs()
    if not dist_blob:
        ok = False
        notes.append("❌ dist/assets/*.js — brak bundle (npm run build)")
    elif all(marker in dist_blob for marker in KSEF_CONNECT_DIST_MARKERS):
        notes.append("✅ dist zawiera markery connect fix (409 fallback + connect sync trigger)")
    else:
        ok = False
        notes.append("❌ dist NIE zawiera connect fix — wymagany: cd frontend-react && npm run build")

    return ok, notes


def check_frontend_dist_freshness(*, label: str = "lokalnie") -> tuple[bool, str]:
    commit_ts = frontend_src_last_commit_epoch()
    dist_ts = frontend_dist_newest_epoch()
    if dist_ts is None:
        return False, f"❌ [{label}] {FRONTEND_DIST_STALE_MSG}"
    try:
        src_head = git("log", "-1", "--format=%H", "--", FRONTEND_SRC_PREFIX)
        dist_head = git("log", "-1", "--format=%H", "--", "frontend-react/dist")
        if src_head == dist_head:
            return True, f"✅ [{label}] dist i src w tym samym commicie ({src_head[:7]})"
    except RuntimeError:
        pass
    if commit_ts is None:
        return True, f"✅ [{label}] brak historii commitów {FRONTEND_SRC_PREFIX} (pominięto)"
    if dist_ts < commit_ts:
        try:
            commit_ref = git("log", "-1", "--format=%h", "--", FRONTEND_SRC_PREFIX)
        except RuntimeError:
            commit_ref = "?"
        return False, (
            f"❌ [{label}] {FRONTEND_DIST_STALE_MSG} "
            f"(dist starszy niż commit {commit_ref} w {FRONTEND_SRC_PREFIX})"
        )
    return True, f"✅ [{label}] frontend-react/dist aktualny względem ostatniego commita src"


def remote_frontend_dist_newest_epoch(host: str, repo_path: str) -> float | None:
    quoted_path = repo_path.replace("'", "'\"'\"'")
    raw = ssh(
        host,
        "cd '" + quoted_path + "' && "
        "ls frontend-react/dist/assets/*.js 2>/dev/null | "
        "xargs stat -c %Y 2>/dev/null | sort -n | tail -1",
    )
    if not raw:
        return None
    try:
        return float(raw.splitlines()[-1].strip())
    except ValueError:
        return None


def check_remote_frontend_dist_freshness(host: str, repo_path: str) -> tuple[bool, str]:
    try:
        src_head = remote_git(host, repo_path, f"log -1 --format=%H -- {FRONTEND_SRC_PREFIX}")
        dist_head = remote_git(host, repo_path, "log -1 --format=%H -- frontend-react/dist")
        if src_head == dist_head:
            return True, f"✅ [DS723+] dist i src w tym samym commicie ({src_head[:7]})"
        commit_ts = int(
            remote_git(host, repo_path, f"log -1 --format=%ct -- {FRONTEND_SRC_PREFIX}")
        )
    except RuntimeError as exc:
        return False, f"❌ [DS723+] nie udało się odczytać commita src: {exc}"
    dist_ts = remote_frontend_dist_newest_epoch(host, repo_path)
    if dist_ts is None:
        return False, f"❌ [DS723+] {FRONTEND_DIST_STALE_MSG}"
    if dist_ts < commit_ts:
        try:
            commit_ref = remote_git(host, repo_path, f"log -1 --format=%h -- {FRONTEND_SRC_PREFIX}")
        except RuntimeError:
            commit_ref = "?"
        return False, (
            f"❌ [DS723+] {FRONTEND_DIST_STALE_MSG} "
            f"(dist starszy niż commit {commit_ref} w {FRONTEND_SRC_PREFIX})"
        )
    return True, "✅ [DS723+] frontend-react/dist aktualny względem ostatniego commita src"


def run_frontend_check() -> int:
    print("IFG Guardian — frontend check")
    print("=" * 40)
    has_error = False
    notes: list[str] = []

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

    for note in notes:
        print(note)

    print("\n" + "=" * 40)
    if has_error:
        print("Status: ERROR")
        return 1
    print("Status: OK")
    return 0
