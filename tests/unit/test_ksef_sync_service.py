from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import ExternalServiceError
from app.integrations.ksef.client import KSeFClientError
from app.services.ksef_session_service import KSeFSessionService
from app.services.ksef_sync_service import KSeFSyncService


class _FakeInvoiceRepository:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str | None]] = []
        self.add_calls = 0

    def exists_by_ksef_number(self, ksef_reference_number: str) -> bool:
        return any(ref == ksef_reference_number for ref, _ in self.rows)

    def add(self, invoice, source_system: str | None = None):
        self.rows.append((invoice.ksef_reference_number, source_system))
        self.add_calls += 1
        return invoice


def _make_ksef_service_with_repo(repo: _FakeInvoiceRepository) -> KSeFSessionService:
    svc = KSeFSessionService(
        session=MagicMock(),
        auth_provider=MagicMock(),
        ksef_client=MagicMock(),
        audit_service=MagicMock(),
        invoice_repository=repo,
    )
    svc.get_session_context = MagicMock(
        return_value=SimpleNamespace(
            access_token="tok",
            session_reference="sess-ref",
            symmetric_key=b"k" * 32,
            initialization_vector=b"i" * 16,
        )
    )
    return svc


def test_sync_received_invoices_does_not_delete_existing_data_on_error() -> None:
    repo = _FakeInvoiceRepository()
    repo.rows.append(("KSEF-EXISTING", "ksef_import"))

    service = _make_ksef_service_with_repo(repo)
    service.ksef_client.query_received_invoices.side_effect = KSeFClientError(
        "KSeF odpowiedział statusem 404",
        status_code=404,
    )

    with pytest.raises(ExternalServiceError):
        service.sync_received_invoices(
            nip="1234567890",
            date_from=date(2026, 5, 1),
            date_to=date(2026, 5, 10),
        )

    assert repo.rows == [("KSEF-EXISTING", "ksef_import")]
    assert repo.add_calls == 0


def test_sync_received_invoices_reimport_does_not_duplicate_existing_invoice() -> None:
    repo = _FakeInvoiceRepository()
    repo.rows.append(("KSEF-1", "ksef_import"))

    service = _make_ksef_service_with_repo(repo)
    service.ksef_client.query_received_invoices.return_value = [
        SimpleNamespace(ksef_reference_number="KSEF-1", xml_bytes=b"<xml/>")
    ]

    counts = service.sync_received_invoices(
        nip="1234567890",
        date_from=date(2026, 5, 1),
        date_to=date(2026, 5, 10),
    )

    assert counts["received"] == 1
    assert counts["saved"] == 0
    assert counts["skipped_existing"] == 1
    assert counts["skipped_parse"] == 0
    assert repo.rows == [("KSEF-1", "ksef_import")]


def test_ksef_sync_service_marks_running_success_and_returns_status() -> None:
    sync_state_repo = MagicMock()
    settings_repo = MagicMock()
    ksef_session_service = MagicMock()

    sync_state_repo.mark_running.return_value = SimpleNamespace(state_json={"last_date_to": "2026-05-01"})
    sync_state_repo.mark_success.return_value = SimpleNamespace(
        scope="purchase_invoices",
        status="success",
        last_success_at=None,
        last_attempt_at=None,
        last_error=None,
        state_json={"last_date_to": "2026-05-10"},
    )
    settings_repo.get.return_value = SimpleNamespace(seller_nip="1234567890")
    ksef_session_service.sync_received_invoices.return_value = {
        "received": 2,
        "saved": 1,
        "skipped_existing": 1,
        "skipped_parse": 0,
    }

    service = KSeFSyncService(
        session=MagicMock(),
        sync_state_repository=sync_state_repo,
        settings_repository=settings_repo,
        ksef_session_service=ksef_session_service,
    )

    result = service.sync_purchase_invoices(force=False)

    assert result["counts"]["saved"] == 1
    assert result["status"]["status"] == "success"
    sync_state_repo.mark_running.assert_called_once_with("purchase_invoices")
    sync_state_repo.mark_success.assert_called_once()


def test_ksef_sync_service_uses_requested_nip_when_settings_are_empty() -> None:
    sync_state_repo = MagicMock()
    settings_repo = MagicMock()
    ksef_session_service = MagicMock()

    sync_state_repo.mark_running.return_value = SimpleNamespace(state_json=None)
    sync_state_repo.mark_success.return_value = SimpleNamespace(
        scope="purchase_invoices",
        status="success",
        last_success_at=None,
        last_attempt_at=None,
        last_error=None,
        state_json={},
    )
    settings_repo.get.return_value = None
    ksef_session_service.sync_received_invoices.return_value = {
        "received": 0,
        "saved": 0,
        "skipped_existing": 0,
        "skipped_parse": 0,
    }

    service = KSeFSyncService(
        session=MagicMock(),
        sync_state_repository=sync_state_repo,
        settings_repository=settings_repo,
        ksef_session_service=ksef_session_service,
    )

    service.sync_purchase_invoices(force=False, nip="9670402857")

    ksef_session_service.sync_received_invoices.assert_called_once()
    assert ksef_session_service.sync_received_invoices.call_args.kwargs["nip"] == "9670402857"
    settings_repo.get.assert_not_called()


def test_ksef_sync_service_uses_configured_owner_nip_when_settings_are_empty() -> None:
    sync_state_repo = MagicMock()
    settings_repo = MagicMock()
    ksef_session_service = MagicMock()

    sync_state_repo.mark_running.return_value = SimpleNamespace(state_json=None)
    sync_state_repo.mark_success.return_value = SimpleNamespace(
        scope="purchase_invoices",
        status="success",
        last_success_at=None,
        last_attempt_at=None,
        last_error=None,
        state_json={},
    )
    settings_repo.get.return_value = None
    ksef_session_service.sync_received_invoices.return_value = {
        "received": 0,
        "saved": 0,
        "skipped_existing": 0,
        "skipped_parse": 0,
    }

    service = KSeFSyncService(
        session=MagicMock(),
        sync_state_repository=sync_state_repo,
        settings_repository=settings_repo,
        ksef_session_service=ksef_session_service,
    )

    service.sync_purchase_invoices(force=False)

    ksef_session_service.sync_received_invoices.assert_called_once()
    assert ksef_session_service.sync_received_invoices.call_args.kwargs["nip"] == "9670402857"
