"""Resume sync zakupów KSeF przy HTTP 429."""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

if not hasattr(SQLiteTypeCompiler, "visit_JSONB"):
    SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "JSON"  # type: ignore[attr-defined]
if not hasattr(SQLiteTypeCompiler, "visit_UUID"):
    SQLiteTypeCompiler.visit_UUID = lambda self, type_, **kw: "CHAR(36)"  # type: ignore[attr-defined]

from app.integrations.ksef.client import KSeFRateLimitDeferredError
from app.persistence.base import Base
from app.persistence.models import (  # noqa: F401
    AuditLog,
    BackgroundJob,
    BankTransactionORM,
    ContractorORM,
    ContractorOverrideORM,
    IdempotencyKeyORM,
    InvoiceItemORM,
    InvoiceORM,
    KSeFSessionORM,
    PaymentAllocationORM,
    TransmissionORM,
    UserORM,
)
from app.services.ksef_session_service import KSeFSessionService
from app.worker.job_handlers.sync_purchase_invoices import (
    JobRateLimitDeferredError,
    SyncPurchaseInvoicesJobHandler,
)


def _minimal_purchase_xml(number: str) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
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
    <P_2>{number}</P_2>
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


def _make_incremental_service(repo: _FakeInvoiceRepository) -> KSeFSessionService:
    session = MagicMock()
    svc = KSeFSessionService(
        session=session,
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
    svc.ksef_client.defer_purchase_rate_limit = True
    return svc


def _refs(count: int, prefix: str = "KSEF-REF") -> list[str]:
    return [f"{prefix}-{idx:03d}" for idx in range(count)]


def test_incremental_sync_saves_before_429_and_returns_resume_state() -> None:
    repo = _FakeInvoiceRepository()
    service = _make_incremental_service(repo)
    refs = _refs(16)
    service.ksef_client.query_purchase_metadata_refs.return_value = refs

    def _download(_token: str, ref: str) -> bytes:
        idx = refs.index(ref)
        if idx >= 15:
            raise KSeFRateLimitDeferredError(
                f"429 for {ref}",
                retry_after_seconds=180.0,
            )
        return _minimal_purchase_xml(ref)

    service.ksef_client.get_purchase_invoice_xml.side_effect = _download

    counts = service.sync_received_invoices(
        nip="1234567890",
        date_from=date(2026, 5, 1),
        date_to=date(2026, 5, 10),
    )

    assert counts["saved"] == 15
    assert counts["rate_limit_deferred"] is True
    assert counts["retry_after_seconds"] == 180.0
    resume = counts["resume_state"]
    assert resume["current_offset"] == 15
    assert resume["current_reference"] == refs[15]
    assert resume["downloaded_count"] == 15
    assert resume["invoice_refs"] == refs
    assert repo.add_calls == 15
    service.session.flush.assert_called()


def test_incremental_sync_resumes_from_saved_offset_without_re_metadata() -> None:
    repo = _FakeInvoiceRepository()
    service = _make_incremental_service(repo)
    refs = _refs(16)
    resume_state = {
        "invoice_refs": refs,
        "current_offset": 15,
        "current_reference": refs[15],
        "downloaded_count": 15,
        "subject_type": "subject2",
        "saved_accumulated": 15,
        "skipped_existing_accumulated": 0,
        "skipped_parse_accumulated": 0,
        "error_samples": [],
    }

    service.ksef_client.get_purchase_invoice_xml.return_value = _minimal_purchase_xml(
        refs[15]
    )

    counts = service.sync_received_invoices(
        nip="1234567890",
        date_from=date(2026, 5, 1),
        date_to=date(2026, 5, 10),
        resume_state=resume_state,
    )

    service.ksef_client.query_purchase_metadata_refs.assert_not_called()
    service.ksef_client.get_purchase_invoice_xml.assert_called_once_with("tok", refs[15])
    assert counts["saved"] == 16
    assert counts.get("rate_limit_deferred") is False
    assert repo.add_calls == 1


def test_incremental_sync_resume_continues_from_current_offset_in_full_list() -> None:
    repo = _FakeInvoiceRepository()
    service = _make_incremental_service(repo)
    refs = _refs(70)
    for ref in refs[:50]:
        repo.rows.append((ref, "ksef_import"))

    resume_state = {
        "invoice_refs": refs,
        "current_offset": 50,
        "current_reference": refs[50],
        "downloaded_count": 50,
        "subject_type": "subject2",
        "saved_accumulated": 0,
        "skipped_existing_accumulated": 50,
        "skipped_parse_accumulated": 0,
        "error_samples": [],
    }

    service.ksef_client.get_purchase_invoice_xml.side_effect = (
        lambda _token, ref: _minimal_purchase_xml(ref)
    )

    counts = service.sync_received_invoices(
        nip="1234567890",
        date_from=date(2026, 3, 23),
        date_to=date(2026, 6, 21),
        resume_state=resume_state,
    )

    service.ksef_client.query_purchase_metadata_refs.assert_not_called()
    assert service.ksef_client.get_purchase_invoice_xml.call_count == 20
    downloaded = [c.args[1] for c in service.ksef_client.get_purchase_invoice_xml.call_args_list]
    assert downloaded == refs[50:]
    assert counts["saved"] == 20
    assert counts["skipped_existing"] == 50


def test_incremental_sync_resume_does_not_duplicate_existing_refs() -> None:
    repo = _FakeInvoiceRepository()
    refs = _refs(16)
    for ref in refs[:15]:
        repo.rows.append((ref, "ksef_import"))

    service = _make_incremental_service(repo)
    resume_state = {
        "invoice_refs": refs,
        "current_offset": 15,
        "current_reference": refs[15],
        "downloaded_count": 15,
        "subject_type": "subject2",
        "saved_accumulated": 15,
        "skipped_existing_accumulated": 0,
        "skipped_parse_accumulated": 0,
        "error_samples": [],
    }

    service.ksef_client.get_purchase_invoice_xml.return_value = _minimal_purchase_xml(
        refs[15]
    )

    counts = service.sync_received_invoices(
        nip="1234567890",
        date_from=date(2026, 5, 1),
        date_to=date(2026, 5, 10),
        resume_state=resume_state,
    )

    service.ksef_client.get_purchase_invoice_xml.assert_called_once_with("tok", refs[15])
    assert counts["saved"] == 16
    assert counts["skipped_existing"] == 0
    assert repo.add_calls == 1
    assert sum(1 for ref, _ in repo.rows if ref == refs[15]) == 1


def test_handler_defer_carries_resume_state() -> None:
    ksef_session_service = MagicMock()
    ksef_session_service.ksef_client = MagicMock()
    resume = {
        "invoice_refs": _refs(3),
        "current_offset": 2,
        "current_reference": "KSEF-REF-002",
        "downloaded_count": 2,
    }
    ksef_session_service.sync_purchase_invoices.return_value = {
        "status": "deferred",
        "created": 2,
        "ksef_returned": 3,
        "skipped_existing": 0,
        "errors": 0,
        "rate_limited": True,
        "rate_limit_deferred": True,
        "retry_after_seconds": 90.0,
        "resume_state": resume,
        "warning": "429",
    }

    handler = SyncPurchaseInvoicesJobHandler(
        session=MagicMock(),
        invoice_repository=MagicMock(),
        job_repository=MagicMock(),
        ksef_session_service=ksef_session_service,
    )

    with pytest.raises(JobRateLimitDeferredError) as exc_info:
        handler.handle(
            {
                "job_id": "job-1",
                "nip": "1234567890",
                "date_from": "2026-05-01",
                "date_to": "2026-05-10",
            }
        )

    assert exc_info.value.retry_after_seconds == 90.0
    assert exc_info.value.resume == resume
    assert exc_info.value.partial_result["saved"] == 2


@pytest.fixture(scope="module")
def sqlite_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db(sqlite_engine):
    connection = sqlite_engine.connect()
    trans = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    trans.rollback()
    connection.close()


def test_enqueue_blocks_second_sync_job_for_same_nip(db: Session) -> None:
    """Ten sam NIP: istniejący pending/processing job blokuje kolejny enqueue (logika API)."""
    nip = "9670402857"
    first_id = uuid.uuid4()
    first = BackgroundJob(
        id=first_id,
        job_type="sync_purchase_invoices",
        payload_json={
            "job_id": str(first_id),
            "nip": nip,
            "date_from": "2026-05-01",
            "date_to": "2026-05-22",
        },
        status="pending",
        available_at=datetime.now(UTC),
        attempts=0,
        max_attempts=1,
    )
    db.add(first)
    db.flush()

    existing = db.execute(
        select(BackgroundJob)
        .where(
            BackgroundJob.job_type == "sync_purchase_invoices",
            BackgroundJob.status.in_(["pending", "processing"]),
            BackgroundJob.payload_json["nip"].astext == nip,
        )
        .limit(1)
    ).scalar_one_or_none()

    assert existing is not None
    assert existing.id == first_id

    processing_id = uuid.uuid4()
    processing = BackgroundJob(
        id=processing_id,
        job_type="sync_purchase_invoices",
        payload_json={"job_id": str(processing_id), "nip": "1111111111"},
        status="processing",
    )
    db.add(processing)
    db.flush()

    blocked = db.execute(
        select(BackgroundJob)
        .where(
            BackgroundJob.job_type == "sync_purchase_invoices",
            BackgroundJob.status.in_(["pending", "processing"]),
            BackgroundJob.payload_json["nip"].astext == nip,
        )
        .limit(1)
    ).scalar_one_or_none()
    assert blocked is not None
    assert blocked.id == first_id
