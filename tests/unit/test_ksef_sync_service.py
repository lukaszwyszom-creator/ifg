from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
import uuid

import pytest

from app.core.exceptions import ExternalServiceError
from app.integrations.ksef.client import KSeFClientError, ReceivedInvoiceResult
from app.services.ksef_session_service import KSeFSessionService
from app.services.ksef_sync_service import KSeFSyncService


class _FakeInvoiceRepository:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str | None]] = []
        self.invoices: list = []
        self.add_calls = 0

    def exists_by_ksef_number(self, ksef_reference_number: str) -> bool:
        return any(ref == ksef_reference_number for ref, _ in self.rows)

    def add(self, invoice, source_system: str | None = None):
        self.rows.append((invoice.ksef_reference_number, source_system))
        self.invoices.append(invoice)
        self.add_calls += 1
        return invoice

    def list_ksef_purchase_refs_in_issue_range(
        self,
        date_from: date,
        date_to: date,
        *,
        buyer_nip: str | None = None,
    ) -> list[str]:
        return [ref for ref, _ in self.rows]


def _make_ksef_service_with_repo(repo: _FakeInvoiceRepository) -> KSeFSessionService:
    svc = KSeFSessionService(
        session=MagicMock(),
        auth_provider=MagicMock(),
        ksef_client=MagicMock(),
        audit_service=MagicMock(),
        invoice_repository=repo,
    )
    svc.purchase_auth.ensure_purchase_auth = MagicMock(
        return_value=SimpleNamespace(
            access_token="tok",
            nip="1234567890",
            expires_at=None,
            record_id=uuid.uuid4(),
        )
    )
    svc.ksef_client.defer_purchase_rate_limit = True
    return svc


def _setup_incremental_metadata_and_xml(
    service: KSeFSessionService,
    refs_xml: dict[str, bytes],
) -> None:
    service.ksef_client.query_purchase_metadata_refs.return_value = list(refs_xml.keys())
    service.ksef_client.get_purchase_invoice_xml.side_effect = (
        lambda _token, ref: refs_xml[ref]
    )


def test_sync_received_invoices_does_not_delete_existing_data_on_error() -> None:
    repo = _FakeInvoiceRepository()
    repo.rows.append(("KSEF-EXISTING", "ksef_import"))

    service = _make_ksef_service_with_repo(repo)
    service.ksef_client.query_purchase_metadata_refs.side_effect = KSeFClientError(
        "KSeF odpowiedział statusem 404",
        status_code=404,
    )

    with pytest.raises(KSeFClientError):
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
    service.ksef_client.query_purchase_metadata_refs.return_value = ["KSEF-1"]

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
    service.ksef_client.get_purchase_invoice_xml.assert_not_called()


def test_sync_received_invoices_stores_vendor_number_from_xml_not_ifg_sequence() -> None:
    repo = _FakeInvoiceRepository()
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Faktura xmlns="http://crd.gov.pl/wzor/2025/06/25/13775/">
  <Podmiot1>
    <DaneIdentyfikacyjne>
      <NIP>1112223344</NIP>
      <Nazwa>Sprzedawca SA</Nazwa>
    </DaneIdentyfikacyjne>
  </Podmiot1>
  <Podmiot2>
    <DaneIdentyfikacyjne>
      <NIP>9670402857</NIP>
      <Nazwa>Nabywca Sp. z o.o.</Nazwa>
    </DaneIdentyfikacyjne>
  </Podmiot2>
  <Fa>
    <KodWaluty>PLN</KodWaluty>
    <P_1>2026-05-10</P_1>
    <P_2>FV/DOSTAWCA/42</P_2>
    <P_13_1>100.00</P_13_1>
    <P_14_1>23.00</P_14_1>
    <P_15>123.00</P_15>
    <RodzajFaktury>VAT</RodzajFaktury>
    <FaWiersz>
      <P_7>Usługa testowa</P_7>
      <P_8B>1</P_8B>
      <P_9A>100.00</P_9A>
      <P_11>100.00</P_11>
      <P_12>23</P_12>
    </FaWiersz>
  </Fa>
</Faktura>
""".encode("utf-8")
    service = _make_ksef_service_with_repo(repo)
    _setup_incremental_metadata_and_xml(service, {"KSEF-NEW": xml})

    counts = service.sync_received_invoices(
        nip="1234567890",
        date_from=date(2026, 5, 1),
        date_to=date(2026, 5, 10),
    )

    assert counts["saved"] == 1
    assert len(repo.invoices) == 1
    saved = repo.invoices[0]
    assert saved.number_local == "FV/DOSTAWCA/42"
    assert saved.direction == "purchase"
    assert saved.ksef_reference_number == "KSEF-NEW"


def test_sync_received_invoices_skips_zero_line_items_when_totals_nonzero() -> None:
    repo = _FakeInvoiceRepository()
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Faktura xmlns="http://crd.gov.pl/wzor/2025/06/25/13775/">
  <Podmiot1>
    <DaneIdentyfikacyjne>
      <NIP>1112223344</NIP>
      <Nazwa>Sprzedawca SA</Nazwa>
    </DaneIdentyfikacyjne>
  </Podmiot1>
  <Podmiot2>
    <DaneIdentyfikacyjne>
      <NIP>9670402857</NIP>
      <Nazwa>Nabywca Sp. z o.o.</Nazwa>
    </DaneIdentyfikacyjne>
  </Podmiot2>
  <Fa>
    <KodWaluty>PLN</KodWaluty>
    <P_1>2026-05-10</P_1>
    <P_2>FV/ZERO/1</P_2>
    <P_13_1>219.51</P_13_1>
    <P_14_1>50.49</P_14_1>
    <P_15>270.00</P_15>
    <RodzajFaktury>VAT</RodzajFaktury>
    <FaWiersz>
      <P_7>Usługi księgowe</P_7>
      <P_8B>1</P_8B>
      <P_12>23</P_12>
    </FaWiersz>
  </Fa>
</Faktura>
""".encode("utf-8")
    service = _make_ksef_service_with_repo(repo)
    _setup_incremental_metadata_and_xml(service, {"KSEF-ZERO-LINES": xml})

    counts = service.sync_received_invoices(
        nip="1234567890",
        date_from=date(2026, 5, 1),
        date_to=date(2026, 5, 10),
    )

    assert counts["saved"] == 0
    assert counts["skipped_parse"] == 1
    assert repo.add_calls == 0
    assert repo.invoices == []


def test_sync_received_invoices_persists_gross_line_variant_p11a() -> None:
    repo = _FakeInvoiceRepository()
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Faktura xmlns="http://crd.gov.pl/wzor/2025/06/25/13775/">
  <Podmiot1>
    <DaneIdentyfikacyjne>
      <NIP>1112223344</NIP>
      <Nazwa>Biuro Rachunkowe</Nazwa>
    </DaneIdentyfikacyjne>
  </Podmiot1>
  <Podmiot2>
    <DaneIdentyfikacyjne>
      <NIP>9670402857</NIP>
      <Nazwa>Nabywca</Nazwa>
    </DaneIdentyfikacyjne>
  </Podmiot2>
  <Fa>
    <KodWaluty>PLN</KodWaluty>
    <P_1>2026-05-01</P_1>
    <P_2>FV/KS/42</P_2>
    <P_13_1>219.51</P_13_1>
    <P_14_1>50.49</P_14_1>
    <P_15>270.00</P_15>
    <RodzajFaktury>VAT</RodzajFaktury>
    <FaWiersz>
      <P_7>Usługi księgowe</P_7>
      <P_8A>mies</P_8A>
      <P_8B>1</P_8B>
      <P_11A>270.00</P_11A>
      <P_12>23</P_12>
    </FaWiersz>
  </Fa>
</Faktura>
""".encode("utf-8")
    service = _make_ksef_service_with_repo(repo)
    _setup_incremental_metadata_and_xml(service, {"KSEF-P11A": xml})

    counts = service.sync_received_invoices(
        nip="1234567890",
        date_from=date(2026, 5, 1),
        date_to=date(2026, 5, 10),
    )

    assert counts["saved"] == 1
    saved = repo.invoices[0]
    assert len(saved.items) == 1
    item = saved.items[0]
    assert item.name == "Usługi księgowe"
    assert item.net_total == Decimal("219.51")
    assert item.vat_total == Decimal("50.49")
    assert item.gross_total == Decimal("270.00")


def test_sync_received_invoices_defers_on_429_instead_of_skipped_error() -> None:
    from app.integrations.ksef.client import KSeFRateLimitDeferredError

    repo = _FakeInvoiceRepository()
    service = _make_ksef_service_with_repo(repo)
    refs = [f"KSEF-REF-{idx:03d}" for idx in range(3)]
    service.ksef_client.query_purchase_metadata_refs.return_value = refs
    service.ksef_client.get_purchase_invoice_xml.side_effect = KSeFRateLimitDeferredError(
        "429",
        retry_after_seconds=90.0,
    )

    counts = service.sync_received_invoices(
        nip="1234567890",
        date_from=date(2026, 5, 1),
        date_to=date(2026, 5, 10),
    )

    assert counts["rate_limit_deferred"] is True
    assert counts["rate_limited"] is True
    assert counts["resume_state"]["current_offset"] == 0
    assert counts["skipped_parse"] == 0


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
