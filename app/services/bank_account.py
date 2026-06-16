"""Normalizacja i formatowanie numeru rachunku bankowego (PL, 26 cyfr)."""
from __future__ import annotations

import re

_BANK_ACCOUNT_DIGITS_RE = re.compile(r"^\d{26}$")


def normalize_bank_account(value: str | None) -> str | None:
    """Usuwa spacje; zwraca 26 cyfr lub None gdy puste."""
    if value is None:
        return None
    digits = re.sub(r"\s+", "", str(value).strip())
    if not digits:
        return None
    return digits


def validate_bank_account(value: str | None) -> str | None:
    """Waliduje i normalizuje numer rachunku."""
    normalized = normalize_bank_account(value)
    if normalized is None:
        return None
    if not _BANK_ACCOUNT_DIGITS_RE.match(normalized):
        raise ValueError(
            "seller_bank_account musi składać się dokładnie z 26 cyfr (spacje są dozwolone przy wpisywaniu)"
        )
    return normalized


def format_bank_account_display(value: str | None) -> str:
    """Prezentacja: 12 3456 7890 1234 5678 9012 3456"""
    digits = normalize_bank_account(value)
    if not digits:
        return ""
    return (
        f"{digits[0:2]} {digits[2:6]} {digits[6:10]} {digits[10:14]} "
        f"{digits[14:18]} {digits[18:22]} {digits[22:26]}"
    )
