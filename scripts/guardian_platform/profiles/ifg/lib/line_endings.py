from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from guardian_platform.profiles.ifg.config.defaults import REPO_ROOT


class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class LineEndingCategory(str, Enum):
    CRLF_ONLY = "CRLF_ONLY"
    UNKNOWN_LINE_ENDINGS = "UNKNOWN_LINE_ENDINGS"
    NOT_LINE_ENDING = "NOT_LINE_ENDING"


@dataclass
class LineEndingAnalysis:
    category: LineEndingCategory
    confidence: Confidence
    restore_would_help: bool
    verification: list[str] = field(default_factory=list)
    note: str = ""


def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _run_git_bytes(args: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    )


def _normalize_newlines(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _read_index(path: str) -> bytes | None:
    result = _run_git_bytes(["show", f":{path}"])
    if result.returncode != 0:
        return None
    return result.stdout


def _read_head(path: str) -> bytes | None:
    result = _run_git_bytes(["show", f"HEAD:{path}"])
    if result.returncode != 0:
        return None
    return result.stdout


def _read_worktree(path: str) -> bytes | None:
    file_path = REPO_ROOT / path
    if not file_path.is_file():
        return None
    return file_path.read_bytes()


def _checkmark(passed: bool) -> str:
    return "✓" if passed else "✗"


def analyze_line_endings(path: str) -> LineEndingAnalysis:
    verification: list[str] = []

    head = _read_head(path)
    index_bytes = _read_index(path)
    worktree = _read_worktree(path)

    if head is None or index_bytes is None or worktree is None:
        verification.append("✗ blob read (HEAD / index / worktree)")
        return LineEndingAnalysis(
            category=LineEndingCategory.UNKNOWN_LINE_ENDINGS,
            confidence=Confidence.LOW,
            restore_would_help=False,
            verification=verification,
            note="Nie udało się odczytać HEAD, index lub worktree",
        )

    norm_head = _normalize_newlines(head)
    norm_index = _normalize_newlines(index_bytes)
    norm_worktree = _normalize_newlines(worktree)

    norms_equal = norm_head == norm_index == norm_worktree
    verification.append(
        f"{_checkmark(norms_equal)} HEAD vs index vs working tree (normalized LF)"
    )

    raw_head_index = head == index_bytes
    raw_index_worktree = index_bytes == worktree
    raw_head_worktree = head == worktree
    verification.append(f"{_checkmark(raw_head_worktree)} HEAD vs working tree (raw bytes)")
    verification.append(f"{_checkmark(raw_head_index)} HEAD vs index (raw bytes)")
    verification.append(f"{_checkmark(raw_index_worktree)} index vs working tree (raw bytes)")

    diff_ignore_cr = _run_git(["diff", "--ignore-cr-at-eol", "--quiet", "--", path])
    ignore_cr_clean = diff_ignore_cr.returncode == 0
    verification.append(f"{_checkmark(ignore_cr_clean)} git diff --ignore-cr-at-eol")

    diff_w = _run_git(["diff", "-w", "--quiet", "--", path])
    diff_w_clean = diff_w.returncode == 0
    verification.append(f"{_checkmark(diff_w_clean)} git diff -w")

    eol_info = _run_git(["ls-files", "--eol", "--", path])
    if eol_info.returncode == 0 and eol_info.stdout.strip():
        eol_tail = eol_info.stdout.strip().split("\t")[-1]
        verification.append(f"✓ git ls-files --eol ({eol_tail})")
    else:
        verification.append("✗ git ls-files --eol")

    file_path = REPO_ROOT / path
    if shutil.which("file"):
        file_result = subprocess.run(
            ["file", "-b", "--", str(file_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if file_result.returncode == 0 and file_result.stdout.strip():
            verification.append(f"✓ file ({file_result.stdout.strip()[:60]})")
        else:
            verification.append("✗ file")
    else:
        verification.append("✗ file (command not available)")

    restore_would_help = index_bytes != worktree
    verification.append(
        f"{_checkmark(restore_would_help)} restore simulation (index raw ≠ worktree raw)"
    )

    if not norms_equal:
        return LineEndingAnalysis(
            category=LineEndingCategory.NOT_LINE_ENDING,
            confidence=Confidence.HIGH,
            restore_would_help=restore_would_help,
            verification=verification,
            note="Znormalizowana treść różni się — zmiana merytoryczna",
        )

    if raw_head_index and raw_index_worktree and raw_head_worktree:
        return LineEndingAnalysis(
            category=LineEndingCategory.UNKNOWN_LINE_ENDINGS,
            confidence=Confidence.LOW,
            restore_would_help=False,
            verification=verification,
            note=(
                "HEAD, index i worktree identyczne bajt-po-bajcie, lecz git status "
                "pokazuje M — prawdopodobnie fałszywy alarm (attr eol=lf / filtry). "
                "git restore nic nie zmieni."
            ),
        )

    if not ignore_cr_clean or not diff_w_clean:
        return LineEndingAnalysis(
            category=LineEndingCategory.UNKNOWN_LINE_ENDINGS,
            confidence=Confidence.LOW,
            restore_would_help=False,
            verification=verification,
            note="Różnice niespójne między testami git diff — wymaga ręcznej analizy",
        )

    if not restore_would_help:
        return LineEndingAnalysis(
            category=LineEndingCategory.UNKNOWN_LINE_ENDINGS,
            confidence=Confidence.MEDIUM,
            restore_would_help=False,
            verification=verification,
            note=(
                "Treść znormalizowana identyczna, ale index == worktree (raw) — "
                "restore nie zmieni pliku"
            ),
        )

    return LineEndingAnalysis(
        category=LineEndingCategory.CRLF_ONLY,
        confidence=Confidence.HIGH,
        restore_would_help=True,
        verification=verification,
        note="Różnią się wyłącznie końce linii (HEAD/index/worktree); restore może pomóc",
    )
