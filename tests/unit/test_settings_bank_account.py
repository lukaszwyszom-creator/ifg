"""Testy walidacji rachunku bankowego w ustawieniach."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.core.exceptions import ValidationError
from app.persistence.models.app_settings import AppSettingsORM
from app.services.settings_service import SettingsService

VALID_DIGITS = "12345678901234567890123456"
VALID_FORMATTED = "12 3456 7890 1234 5678 9012 3456"


@pytest.fixture
def settings_service() -> SettingsService:
    session = MagicMock()
    repository = MagicMock()
    return SettingsService(session, repository)


@pytest.mark.parametrize("raw", [VALID_DIGITS, VALID_FORMATTED])
def test_update_settings_normalizes_bank_account(
    settings_service: SettingsService,
    raw: str,
) -> None:
    row = AppSettingsORM(seller_bank_account=VALID_DIGITS)
    settings_service.repository.upsert.return_value = row

    result = settings_service.update_settings({"seller_bank_account": raw})

    settings_service.repository.upsert.assert_called_once()
    saved = settings_service.repository.upsert.call_args[0][0]
    assert saved["seller_bank_account"] == VALID_DIGITS
    assert result["seller_bank_account"] == VALID_DIGITS


@pytest.mark.parametrize(
    "raw",
    [
        "1234567890123456789012345",
        "123456789012345678901234567",
        "12-3456-7890-1234-5678-9012-3456",
    ],
)
def test_update_settings_rejects_invalid_bank_account(
    settings_service: SettingsService,
    raw: str,
) -> None:
    with pytest.raises(ValidationError, match="26 cyfr"):
        settings_service.update_settings({"seller_bank_account": raw})
