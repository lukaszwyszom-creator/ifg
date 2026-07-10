from __future__ import annotations

import platform
import shutil
import subprocess


def _normalize_for_compare(text: str) -> str:
    return text.replace("\r\n", "\n").rstrip()


def _verify_clipboard(expected: str) -> tuple[bool, str]:
    if shutil.which("pbpaste") is None:
        return False, "pbpaste nie jest dostępny — nie można zweryfikować schowka"
    proc = subprocess.run(
        ["pbpaste"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or f"pbpaste exit {proc.returncode}"
        return False, f"weryfikacja schowka nie powiodła się: {detail}"
    pasted = proc.stdout
    if _normalize_for_compare(pasted) == _normalize_for_compare(expected):
        return True, ""
    if len(pasted) != len(expected):
        return False, (
            f"niezgodna długość schowka (oczekiwano {len(expected)} znaków, "
            f"otrzymano {len(pasted)})"
        )
    return False, "zawartość schowka nie odpowiada wygenerowanemu handoff"


def _copy_via_pbcopy(content: str) -> tuple[bool, str]:
    if shutil.which("pbcopy") is None:
        return False, "pbcopy nie jest dostępny w PATH"
    proc = subprocess.run(
        ["pbcopy"],
        input=content,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or f"pbcopy exit {proc.returncode}"
        return False, detail
    return _verify_clipboard(content)


def copy_text_to_clipboard(content: str) -> tuple[bool, str]:
    """Copy text to the system clipboard and verify with round-trip read.

    Returns ``(success, reason)`` where ``reason`` is empty on success.
    """
    if platform.system() != "Darwin":
        return False, "automatyczne kopiowanie obsługiwane tylko na macOS"
    if not content:
        return False, "pusta zawartość handoff — pominięto kopiowanie"
    return _copy_via_pbcopy(content)
