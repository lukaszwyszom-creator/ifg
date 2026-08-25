"""Immutable commit snapshot for IFG Guardian deploy builds.

Creates a filesystem tree directly from Git objects via ``git archive``,
so build/deploy never depends on a checkout working tree that may look
dirty solely due to historical CRLF blobs vs ``.gitattributes eol=lf``.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


META_DIR_NAME = ".ifg_guardian_snapshot"
MANIFEST_NAME = "manifest.json"
META_NAME = "meta.json"
COMMIT_NAME = "COMMIT"


class SnapshotError(RuntimeError):
    """Immutable snapshot creation or verification failed."""


@dataclass(frozen=True)
class ManifestEntry:
    path: str
    sha256: str
    mode: str  # e.g. "100644", "100755", "120000"
    size: int


@dataclass
class BuildSnapshot:
    commit_sha: str
    snapshot_root: Path
    tree_dir: Path
    meta_dir: Path
    manifest_path: Path
    manifest_sha256: str
    source_root: Path
    source_wip_detected: bool
    source_wip_paths: list[str] = field(default_factory=list)
    source_wip_excluded: bool = True
    file_count: int = 0
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "commit_sha": self.commit_sha,
            "snapshot_root": str(self.snapshot_root),
            "tree_dir": str(self.tree_dir),
            "meta_dir": str(self.meta_dir),
            "manifest_path": str(self.manifest_path),
            "manifest_sha256": self.manifest_sha256,
            "source_root": str(self.source_root),
            "source_wip_detected": self.source_wip_detected,
            "source_wip_paths": list(self.source_wip_paths),
            "source_wip_excluded": self.source_wip_excluded,
            "file_count": self.file_count,
            "created_at": self.created_at,
            "build_source": "git_archive",
        }


def resolve_commit_sha(repo_root: Path, commit: str) -> str:
    """Return full SHA for ``commit`` or raise SnapshotError."""
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--verify", f"{commit}^{{commit}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise SnapshotError(f"invalid or unknown commit {commit!r}: {detail or 'rev-parse failed'}")
    return result.stdout.strip()


def detect_source_wip(repo_root: Path) -> list[str]:
    """Return porcelain paths from the source repo (informational; not copied)."""
    result = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain", "-uall"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    paths: list[str] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip() if len(line) > 3 else ""
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path:
            paths.append(path)
    return paths


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_ls_tree(repo_root: Path, commit_sha: str) -> dict[str, tuple[str, str]]:
    """Map path -> (mode, blob_sha) for the commit tree (blobs only + symlinks)."""
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-tree", "-r", commit_sha],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SnapshotError((result.stderr or result.stdout or "ls-tree failed").strip())
    entries: dict[str, tuple[str, str]] = {}
    for line in result.stdout.splitlines():
        # mode SP type SP sha TAB path
        meta, _, path = line.partition("\t")
        if not path:
            continue
        parts = meta.split()
        if len(parts) < 3:
            continue
        mode, obj_type, blob_sha = parts[0], parts[1], parts[2]
        if obj_type not in ("blob",):
            continue
        entries[path] = (mode, blob_sha)
    return entries


def _cat_blob(repo_root: Path, blob_sha: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "cat-file", "blob", blob_sha],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise SnapshotError(f"cannot read blob {blob_sha}")
    return result.stdout


def _file_git_mode(path: Path) -> str:
    if path.is_symlink():
        return "120000"
    mode = path.stat().st_mode
    if mode & stat.S_IXUSR:
        return "100755"
    return "100644"


def _iter_tree_files(tree_dir: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(tree_dir, followlinks=False):
        # Do not descend into meta if misplaced
        dirnames[:] = [d for d in dirnames if d != META_DIR_NAME]
        base = Path(dirpath)
        for name in filenames:
            yield base / name
        # include symlink files that os.walk may list as filenames
        for name in list(dirnames):
            candidate = base / name
            if candidate.is_symlink():
                yield candidate


def build_manifest_from_tree(tree_dir: Path) -> list[ManifestEntry]:
    entries: list[ManifestEntry] = []
    for path in sorted(_iter_tree_files(tree_dir), key=lambda p: str(p.relative_to(tree_dir))):
        rel = path.relative_to(tree_dir).as_posix()
        if path.is_symlink():
            target = os.readlink(path)
            digest = _sha256_bytes(target.encode("utf-8", errors="surrogateescape"))
            size = len(target.encode("utf-8", errors="surrogateescape"))
            mode = "120000"
        else:
            digest = _sha256_file(path)
            size = path.stat().st_size
            mode = _file_git_mode(path)
        entries.append(ManifestEntry(path=rel, sha256=digest, mode=mode, size=size))
    return entries


def _manifest_document(entries: list[ManifestEntry], commit_sha: str) -> dict[str, Any]:
    return {
        "commit_sha": commit_sha,
        "files": [asdict(e) for e in entries],
    }


def _manifest_sha256(doc: dict[str, Any]) -> str:
    payload = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(payload)


def extract_git_archive(*, repo_root: Path, commit_sha: str, dest: Path) -> None:
    """Extract ``git archive <commit>`` into ``dest`` (must exist and be empty-ish)."""
    dest.mkdir(parents=True, exist_ok=True)
    archive = subprocess.Popen(
        ["git", "-C", str(repo_root), "archive", "--format=tar", commit_sha],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert archive.stdout is not None
    extract = subprocess.run(
        ["tar", "-x", "-C", str(dest)],
        stdin=archive.stdout,
        capture_output=True,
        check=False,
    )
    archive.stdout.close()
    archive_rc = archive.wait()
    if archive_rc != 0:
        err = (archive.stderr.read() if archive.stderr else b"").decode("utf-8", errors="replace")
        raise SnapshotError(f"git archive failed for {commit_sha}: {err.strip()}")
    if extract.returncode != 0:
        # Some environments cannot write restricted paths (e.g. .cursor); treat as hard fail
        # only when no tracked content was extracted.
        err = (extract.stderr or extract.stdout or b"").decode("utf-8", errors="replace")
        tracked = list(dest.rglob("*"))
        if not any(p.is_file() or p.is_symlink() for p in tracked):
            raise SnapshotError(f"tar extract failed: {err.strip()}")
        # Partial extract with warnings — still require verification against ls-tree.


def verify_snapshot_against_commit(
    *,
    repo_root: Path,
    commit_sha: str,
    tree_dir: Path,
    entries: list[ManifestEntry] | None = None,
) -> None:
    """Fail if snapshot tree does not match commit blobs/modes exactly."""
    tree_map = _git_ls_tree(repo_root, commit_sha)
    if entries is None:
        entries = build_manifest_from_tree(tree_dir)
    snap_map = {e.path: e for e in entries}

    missing = sorted(set(tree_map) - set(snap_map))
    extra = sorted(set(snap_map) - set(tree_map))
    if missing:
        raise SnapshotError(f"snapshot missing {len(missing)} path(s), e.g. {missing[:3]}")
    if extra:
        raise SnapshotError(f"snapshot has unexpected path(s): {extra[:5]}")

    mismatches: list[str] = []
    for path, (mode, blob_sha) in tree_map.items():
        entry = snap_map[path]
        blob = _cat_blob(repo_root, blob_sha)
        if mode == "120000":
            expected_digest = _sha256_bytes(blob)
            expected_mode = "120000"
        else:
            expected_digest = _sha256_bytes(blob)
            expected_mode = mode
        if entry.sha256 != expected_digest:
            mismatches.append(f"{path}: content hash mismatch")
        # Executable bit: compare owner-exec intent (100755 vs 100644)
        if expected_mode in ("100644", "100755") and entry.mode in ("100644", "100755"):
            if entry.mode != expected_mode:
                mismatches.append(f"{path}: mode {entry.mode} != {expected_mode}")
        elif expected_mode == "120000" and entry.mode != "120000":
            mismatches.append(f"{path}: expected symlink")
        if len(mismatches) >= 10:
            break
    if mismatches:
        raise SnapshotError("snapshot verification failed: " + "; ".join(mismatches))


def create_immutable_commit_snapshot(
    *,
    repo_root: Path,
    commit: str = "HEAD",
    base_temp_dir: Path | None = None,
    prefix: str = "ifg-deploy-snap-",
) -> BuildSnapshot:
    """Create a verified immutable snapshot of ``commit`` under a temp directory.

    The snapshot tree contains only tracked objects from the commit. Any WIP in
    ``repo_root`` is detected for reporting and explicitly excluded.
    """
    repo_root = repo_root.resolve()
    commit_sha = resolve_commit_sha(repo_root, commit)
    short = commit_sha[:7]
    wip_paths = detect_source_wip(repo_root)

    parent = Path(base_temp_dir) if base_temp_dir else Path(tempfile.gettempdir())
    parent.mkdir(parents=True, exist_ok=True)
    snapshot_root = Path(tempfile.mkdtemp(prefix=f"{prefix}{short}-", dir=str(parent)))
    tree_dir = snapshot_root / "tree"
    meta_dir = snapshot_root / META_DIR_NAME
    tree_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    try:
        extract_git_archive(repo_root=repo_root, commit_sha=commit_sha, dest=tree_dir)
        entries = build_manifest_from_tree(tree_dir)
        verify_snapshot_against_commit(
            repo_root=repo_root,
            commit_sha=commit_sha,
            tree_dir=tree_dir,
            entries=entries,
        )
        doc = _manifest_document(entries, commit_sha)
        manifest_path = meta_dir / MANIFEST_NAME
        manifest_path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        manifest_digest = _manifest_sha256(doc)
        (meta_dir / "manifest.sha256").write_text(manifest_digest + "\n", encoding="utf-8")
        (meta_dir / COMMIT_NAME).write_text(commit_sha + "\n", encoding="utf-8")

        created_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        snapshot = BuildSnapshot(
            commit_sha=commit_sha,
            snapshot_root=snapshot_root,
            tree_dir=tree_dir,
            meta_dir=meta_dir,
            manifest_path=manifest_path,
            manifest_sha256=manifest_digest,
            source_root=repo_root,
            source_wip_detected=bool(wip_paths),
            source_wip_paths=wip_paths[:50],
            source_wip_excluded=True,
            file_count=len(entries),
            created_at=created_at,
        )
        (meta_dir / META_NAME).write_text(
            json.dumps(snapshot.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return snapshot
    except Exception:
        shutil.rmtree(snapshot_root, ignore_errors=True)
        raise


def reverify_snapshot(snapshot: BuildSnapshot, *, repo_root: Path | None = None) -> None:
    """Re-read tree + manifest and verify against the recorded commit (tamper gate)."""
    root = repo_root or snapshot.source_root
    if not snapshot.tree_dir.is_dir():
        raise SnapshotError(f"snapshot tree missing: {snapshot.tree_dir}")
    recorded = (snapshot.meta_dir / COMMIT_NAME).read_text(encoding="utf-8").strip()
    if recorded != snapshot.commit_sha:
        raise SnapshotError("COMMIT marker mismatch")
    entries = build_manifest_from_tree(snapshot.tree_dir)
    doc = _manifest_document(entries, snapshot.commit_sha)
    digest = _manifest_sha256(doc)
    expected = (snapshot.meta_dir / "manifest.sha256").read_text(encoding="utf-8").strip()
    if digest != expected:
        raise SnapshotError("manifest hash mismatch — snapshot tree was modified after creation")
    verify_snapshot_against_commit(
        repo_root=root,
        commit_sha=snapshot.commit_sha,
        tree_dir=snapshot.tree_dir,
        entries=entries,
    )


def cleanup_snapshot(snapshot: BuildSnapshot | Path | None) -> None:
    if snapshot is None:
        return
    root = snapshot.snapshot_root if isinstance(snapshot, BuildSnapshot) else Path(snapshot)
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
