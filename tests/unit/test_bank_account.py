"""Testy normalizacji i formatowania rachunku bankowego."""
from __future__ import annotations

import pytest

from app.services.bank_account import (
    format_bank_account_display,
    normalize_bank_account,
    validate_bank_account,
)

VALID_DIGITS = "12345678901234567890123456"
VALID_FORMATTED = "12 3456 7890 1234 5678 9012 3456"


@pytest.mark.parametrize(
    "raw,expected",
    [
        (VALID_DIGITS, VALID_DIGITS),
        (VALID_FORMATTED, VALID_DIGITS),
        (" 12 3456 7890 1234 5678 9012 3456 ", VALID_DIGITS),
        (None, None),
        ("", None),
        ("   ", None),
    ],
)
def test_normalize_bank_account(raw: str | None, expected: str | None) -> None:
    assert normalize_bank_account(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        (VALID_DIGITS, VALID_DIGITS),
        (VALID_FORMATTED, VALID_DIGITS),
    ],
)
def test_validate_bank_account_accepts_valid_input(raw: str, expected: str) -> None:
    assert validate_bank_account(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "1234567890123456789012345",
        "123456789012345678901234567",
        "1234567890123456789012345X",
        "12-3456-7890-1234-5678-9012-3456",
        "abc",
    ],
)
def test_validate_bank_account_rejects_invalid_input(raw: str) -> None:
    with pytest.raises(ValueError, match="26 cyfr"):
        validate_bank_account(raw)


def test_format_bank_account_display() -> None:
    assert format_bank_account_display(VALID_DIGITS) == VALID_FORMATTED
    assert format_bank_account_display(VALID_FORMATTED) == VALID_FORMATTED
    assert format_bank_account_display(None) == ""
    assert format_bank_account_display("") == ""
