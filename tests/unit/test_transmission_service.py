"""Testy TransmissionService — unit (mocki)."""
from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from datetime import UTC, datetime

import pytest

from app.core.exceptions import NotFoundError
from app.core.security import AuthenticatedUser
from app.domain.enums import InvoiceStatus, TransmissionStatus
from app.domain.exceptions import InvalidInvoiceError, InvalidStatusTransitionError
from app.services.transmission_service import TransmissionService


@pytest.fixture()
def service(mock_session: MagicMock) -> TransmissionService:
    settings_service = MagicMock()
    invoice_service = MagicMock()
    return TransmissionService(
        session=mock_session,
        transmission_repository=MagicMock(),
        invoice_repository=MagicMock(),
        job_repository=MagicMock(),
        audit_service=MagicMock(),
        settings_service=settings_service,
        invoice_service=invoice_service,
    )


class TestSubmitInvoice:
    def test_wrong_status_raises(self, service: TransmissionService, actor: AuthenticatedUser):
        invoice = MagicMock()
        invoice.status = InvoiceStatus.ACCEPTED
        invoice.can_transition_to = MagicMock(return_value=False)
        service._invoice_repo.lock_for_update.return_value = invoice

        with pytest.raises(InvalidStatusTransitionError, match="ready_for_submission"):
            service.submit_invoice(uuid4(), actor)

    def test_active_transmission_exists_raises(self, service: TransmissionService, actor: AuthenticatedUser):
        invoice = MagicMock()
        invoice.status = InvoiceStatus.READY_FOR_SUBMISSION
        invoice.can_transition_to = MagicMock(return_value=True)
        service._invoice_repo.lock_for_update.return_value = invoice
        service._transmission_repo.get_active_for_invoice.return_value = MagicMock(id=uuid4(), status="queued")

        with pytest.raises(InvalidInvoiceError, match="aktywną transmisję"):
            service.submit_invoice(uuid4(), actor)

    def test_success(self, service: TransmissionService, actor: AuthenticatedUser):
        invoice_id = uuid4()
        invoice = MagicMock()
        invoice.id = invoice_id
        invoice.status = InvoiceStatus.READY_FOR_SUBMISSION
        invoice.direction = "sale"
        invoice.number_local = "FV/01/2025/1"
        invoice.updated_at = datetime.now(UTC)
        invoice.can_transition_to = MagicMock(return_value=True)
        invoice.validate_for_ksef = MagicMock()
        invoice.validate_sale_formal_requirements = MagicMock()
        service._invoice_repo.lock_for_update.return_value = invoice
        service._invoice_repo.update.return_value = invoice
        service._settings_service.build_company_snapshot.return_value = {
            "name": "Firma",
            "nip": "1234567890",
        }
        service._settings_service.validate_company_snapshot.return_value = None
        service._transmission_repo.get_active_for_invoice.return_value = None
        service._transmission_repo.get_by_idempotency_key.return_value = None

        transmission = MagicMock()
        transmission.id = uuid4()
        transmission.invoice_id = invoice_id
        transmission.status = TransmissionStatus.QUEUED
        service._transmission_repo.add.return_value = transmission

        from unittest.mock import patch

        with patch('app.services.transmission_service.KSeFMapper') as mock_mapper:
            mock_mapper.invoice_to_xml.return_value = b'<xml/>'
            mock_mapper.xml_content_hash.return_value = 'hash-1'

            result = service.submit_invoice(invoice_id, actor)

        assert result == transmission
        service._job_repo.add.assert_called_once()
        assert service._audit_service.record.call_count == 2
        invoice.validate_sale_formal_requirements.assert_called_once_with(require_number_local=True)

    def test_submit_assigns_number_local_when_missing(self, service: TransmissionService, actor: AuthenticatedUser):
        invoice_id = uuid4()
        invoice = MagicMock()
        invoice.id = invoice_id
        invoice.status = InvoiceStatus.READY_FOR_SUBMISSION
        invoice.direction = "sale"
        invoice.number_local = None
        invoice.updated_at = datetime.now(UTC)
        invoice.can_transition_to = MagicMock(return_value=True)
        invoice.validate_for_ksef = MagicMock()
        invoice.validate_sale_formal_requirements = MagicMock()

        prepared = MagicMock()
        prepared.number_local = "FV/01/2025/1"
        prepared.direction = "sale"
        prepared.validate_for_ksef = MagicMock()
        prepared.validate_sale_formal_requirements = MagicMock()

        service._invoice_repo.lock_for_update.return_value = invoice
        service._invoice_repo.update.return_value = invoice
        service._settings_service.build_company_snapshot.return_value = {
            "name": "Firma",
            "nip": "1234567890",
        }
        service._settings_service.validate_company_snapshot.return_value = None
        service._invoice_service.ensure_number_local.return_value = prepared
        service._transmission_repo.get_active_for_invoice.return_value = None
        service._transmission_repo.get_by_idempotency_key.return_value = None

        transmission = MagicMock()
        transmission.id = uuid4()
        transmission.invoice_id = invoice_id
        transmission.status = TransmissionStatus.QUEUED
        service._transmission_repo.add.return_value = transmission

        from unittest.mock import patch

        with patch('app.services.transmission_service.KSeFMapper') as mock_mapper:
            mock_mapper.invoice_to_xml.return_value = b'<xml/>'
            mock_mapper.xml_content_hash.return_value = 'hash-1'

            result = service.submit_invoice(invoice_id, actor)

        assert result == transmission
        service._invoice_service.ensure_number_local.assert_called_once_with(
            invoice_id, invoice, actor
        )
        prepared.validate_sale_formal_requirements.assert_called_once_with(
            require_number_local=True
        )

    def test_submit_from_rejected_sale_creates_new_transmission(
        self, service: TransmissionService, actor: AuthenticatedUser
    ):
        invoice_id = uuid4()
        invoice = MagicMock()
        invoice.id = invoice_id
        invoice.status = InvoiceStatus.REJECTED
        invoice.direction = "sale"
        invoice.number_local = "FV/01/2025/1"
        invoice.updated_at = datetime.now(UTC)
        invoice.can_transition_to = MagicMock(return_value=False)
        invoice.validate_for_ksef = MagicMock()
        invoice.validate_sale_formal_requirements = MagicMock()
        invoice.validate_vat = MagicMock()
        service._invoice_repo.lock_for_update.return_value = invoice
        service._invoice_repo.update.return_value = invoice
        service._settings_service.build_company_snapshot.return_value = {
            "name": "Firma",
            "nip": "1234567890",
        }
        service._settings_service.validate_company_snapshot.return_value = None
        service._transmission_repo.get_active_for_invoice.return_value = None
        service._transmission_repo.get_by_idempotency_key.return_value = None

        transmission = MagicMock()
        transmission.id = uuid4()
        transmission.invoice_id = invoice_id
        transmission.status = TransmissionStatus.QUEUED
        service._transmission_repo.add.return_value = transmission

        from unittest.mock import patch

        with patch('app.services.transmission_service.KSeFMapper') as mock_mapper:
            mock_mapper.invoice_to_xml.return_value = b'<xml/>'
            mock_mapper.xml_content_hash.return_value = 'hash-retry'

            result = service.submit_invoice(invoice_id, actor)

        assert result == transmission
        assert invoice.status == InvoiceStatus.SENDING
        invoice.validate_for_ksef.assert_not_called()
        invoice.validate_sale_formal_requirements.assert_called_once_with(
            require_number_local=True
        )
        invoice.validate_vat.assert_called_once()
        service._invoice_service.ensure_number_local.assert_not_called()
        service._transmission_repo.add.assert_called_once()
        service._job_repo.add.assert_called_once()

    def test_submit_from_rejected_purchase_raises(
        self, service: TransmissionService, actor: AuthenticatedUser
    ):
        invoice = MagicMock()
        invoice.status = InvoiceStatus.REJECTED
        invoice.direction = "purchase"
        invoice.can_transition_to = MagicMock(return_value=False)
        service._invoice_repo.lock_for_update.return_value = invoice

        with pytest.raises(InvalidStatusTransitionError, match="ready_for_submission"):
            service.submit_invoice(uuid4(), actor)

    def test_submit_sale_with_incomplete_buyer_returns_friendly_error(
        self, service: TransmissionService, actor: AuthenticatedUser
    ):
        invoice_id = uuid4()
        invoice = MagicMock()
        invoice.id = invoice_id
        invoice.status = InvoiceStatus.READY_FOR_SUBMISSION
        invoice.direction = "sale"
        invoice.number_local = None
        invoice.can_transition_to = MagicMock(return_value=True)
        service._invoice_repo.lock_for_update.return_value = invoice
        service._invoice_repo.update.return_value = invoice
        service._settings_service.build_company_snapshot.return_value = {
            "name": "Firma",
            "nip": "1234567890",
        }
        service._settings_service.validate_company_snapshot.return_value = None
        service._transmission_repo.get_active_for_invoice.return_value = None
        service._invoice_service.ensure_number_local.side_effect = InvalidInvoiceError(
            "Niekompletny snapshot nabywcy: wymagane pole name."
        )

        with pytest.raises(InvalidInvoiceError) as exc_info:
            service.submit_invoice(invoice_id, actor)

        msg = exc_info.value.message
        assert msg == "Uzupełnij dane nabywcy na fakturze przed wysyłką do KSeF."
        assert "buyer_snapshot" not in msg
        assert "wymagane pole name" not in msg
        service._job_repo.add.assert_not_called()

    def test_purchase_does_not_run_sale_formal_guard(self, service: TransmissionService, actor: AuthenticatedUser):
        invoice_id = uuid4()
        invoice = MagicMock()
        invoice.status = InvoiceStatus.READY_FOR_SUBMISSION
        invoice.direction = "purchase"
        invoice.updated_at = datetime.now(UTC)
        invoice.can_transition_to = MagicMock(return_value=True)
        invoice.validate_for_ksef = MagicMock()
        invoice.validate_sale_formal_requirements = MagicMock()
        service._invoice_repo.lock_for_update.return_value = invoice
        service._transmission_repo.get_active_for_invoice.return_value = None
        service._transmission_repo.get_by_idempotency_key.return_value = None

        transmission = MagicMock()
        transmission.id = uuid4()
        transmission.invoice_id = invoice_id
        transmission.status = TransmissionStatus.QUEUED
        service._transmission_repo.add.return_value = transmission

        from unittest.mock import patch

        with patch('app.services.transmission_service.KSeFMapper') as mock_mapper:
            mock_mapper.invoice_to_xml.return_value = b'<xml/>'
            mock_mapper.xml_content_hash.return_value = 'hash-1'

            result = service.submit_invoice(invoice_id, actor)

        assert result == transmission
        invoice.validate_sale_formal_requirements.assert_not_called()

    def test_returns_existing_transmission_for_same_idempotency_key(self, service: TransmissionService, actor: AuthenticatedUser):
        invoice_id = uuid4()
        invoice = MagicMock()
        invoice.status = InvoiceStatus.SENDING
        invoice.updated_at = datetime.now(UTC)
        invoice.can_transition_to = MagicMock(return_value=False)
        service._invoice_repo.lock_for_update.return_value = invoice

        existing = MagicMock()
        existing.id = uuid4()
        existing.invoice_id = invoice_id
        existing.status = TransmissionStatus.SUBMITTED
        service._transmission_repo.get_by_idempotency_key.return_value = existing

        from unittest.mock import patch

        with patch('app.services.transmission_service.KSeFMapper') as mock_mapper:
            mock_mapper.invoice_to_xml.return_value = b'<xml/>'
            mock_mapper.xml_content_hash.return_value = 'hash-1'

            result = service.submit_invoice(invoice_id, actor)

        assert result == existing
        service._transmission_repo.add.assert_not_called()
        service._job_repo.add.assert_not_called()

    def test_does_not_reuse_failed_transmission_for_same_idempotency_key(self, service: TransmissionService, actor: AuthenticatedUser):
        invoice_id = uuid4()
        invoice = MagicMock()
        invoice.id = invoice_id
        invoice.status = InvoiceStatus.READY_FOR_SUBMISSION
        invoice.direction = "sale"
        invoice.number_local = "FV/01/2025/1"
        invoice.updated_at = datetime.now(UTC)
        invoice.can_transition_to = MagicMock(return_value=True)
        invoice.validate_for_ksef = MagicMock()
        invoice.validate_sale_formal_requirements = MagicMock()
        service._invoice_repo.lock_for_update.return_value = invoice
        service._invoice_repo.update.return_value = invoice
        service._settings_service.build_company_snapshot.return_value = {
            "name": "Firma",
            "nip": "1234567890",
        }
        service._settings_service.validate_company_snapshot.return_value = None
        service._transmission_repo.get_active_for_invoice.return_value = None

        failed = MagicMock()
        failed.status = TransmissionStatus.FAILED_RETRYABLE
        service._transmission_repo.get_by_idempotency_key.return_value = failed

        transmission = MagicMock()
        transmission.id = uuid4()
        transmission.invoice_id = invoice_id
        transmission.status = TransmissionStatus.QUEUED
        service._transmission_repo.add.return_value = transmission

        from unittest.mock import patch

        with patch('app.services.transmission_service.KSeFMapper') as mock_mapper:
            mock_mapper.invoice_to_xml.return_value = b'<xml/>'
            mock_mapper.xml_content_hash.return_value = 'hash-1'

            result = service.submit_invoice(invoice_id, actor)

        assert result == transmission
        service._transmission_repo.add.assert_called_once()


class TestRetryTransmission:
    def test_not_found_raises(self, service: TransmissionService, actor: AuthenticatedUser):
        service._transmission_repo.lock_for_update.return_value = None
        with pytest.raises(NotFoundError):
            service.retry_transmission(uuid4(), actor)

    def test_wrong_status_raises(self, service: TransmissionService, actor: AuthenticatedUser):
        t = MagicMock()
        t.status = TransmissionStatus.SUCCESS
        service._transmission_repo.lock_for_update.return_value = t

        with pytest.raises(InvalidInvoiceError, match="retry"):
            service.retry_transmission(uuid4(), actor)

    def test_max_attempts_raises(self, service: TransmissionService, actor: AuthenticatedUser):
        t = MagicMock()
        t.status = TransmissionStatus.FAILED_RETRYABLE
        t.attempt_no = 5
        service._transmission_repo.lock_for_update.return_value = t

        with pytest.raises(InvalidInvoiceError, match="Przekroczono"):
            service.retry_transmission(uuid4(), actor)

    def test_retry_sale_without_number_local_is_rejected(self, service: TransmissionService, actor: AuthenticatedUser):
        t = MagicMock()
        t.id = uuid4()
        t.status = TransmissionStatus.FAILED_RETRYABLE
        t.attempt_no = 1
        t.invoice_id = uuid4()
        service._transmission_repo.lock_for_update.return_value = t

        invoice = MagicMock()
        invoice.id = t.invoice_id
        invoice.direction = "sale"
        invoice.number_local = None
        invoice.seller_snapshot = {"name": "Firma", "nip": "1234567890"}
        service._invoice_repo.lock_for_update.return_value = invoice
        service._invoice_repo.update.return_value = invoice
        service._settings_service.build_company_snapshot.return_value = invoice.seller_snapshot
        service._settings_service.validate_company_snapshot.return_value = None
        service._invoice_service.ensure_number_local.side_effect = InvalidInvoiceError(
            "Faktura sprzedaży nie ma numeru lokalnego. "
            "Zapisz fakturę ponownie przed wysyłką do KSeF."
        )
        service._transmission_repo.get_active_for_invoice.return_value = None

        with pytest.raises(InvalidInvoiceError, match="numeru lokalnego"):
            service.retry_transmission(t.id, actor)

        service._job_repo.add.assert_not_called()

    def test_retry_sale_with_incomplete_snapshot_is_rejected(self, service: TransmissionService, actor: AuthenticatedUser):
        t = MagicMock()
        t.id = uuid4()
        t.status = TransmissionStatus.FAILED_RETRYABLE
        t.attempt_no = 1
        t.invoice_id = uuid4()
        service._transmission_repo.lock_for_update.return_value = t

        invoice = MagicMock()
        invoice.id = t.invoice_id
        invoice.direction = "sale"
        invoice.number_local = "FV/01/2025/1"
        service._invoice_repo.lock_for_update.return_value = invoice
        service._invoice_repo.update.return_value = invoice
        service._settings_service.build_company_snapshot.return_value = {"name": ""}
        from app.core.exceptions import ValidationError
        from app.services.settings_service import SettingsService

        service._settings_service.validate_company_snapshot.side_effect = ValidationError(
            SettingsService.COMPANY_SETTINGS_MSG
        )
        service._transmission_repo.get_active_for_invoice.return_value = None

        with pytest.raises(InvalidInvoiceError, match="Uzupełnij dane sprzedawcy"):
            service.retry_transmission(t.id, actor)

        service._job_repo.add.assert_not_called()

    def test_retry_purchase_is_not_blocked_by_sale_guard(self, service: TransmissionService, actor: AuthenticatedUser):
        t = MagicMock()
        t.id = uuid4()
        t.status = TransmissionStatus.FAILED_RETRYABLE
        t.attempt_no = 1
        t.invoice_id = uuid4()
        service._transmission_repo.lock_for_update.return_value = t

        invoice = MagicMock()
        invoice.direction = "purchase"
        invoice.validate_for_ksef = MagicMock()
        invoice.validate_sale_formal_requirements = MagicMock()
        service._invoice_repo.lock_for_update.return_value = invoice
        service._transmission_repo.get_active_for_invoice.return_value = None

        result = service.retry_transmission(t.id, actor)

        assert result == t
        invoice.validate_for_ksef.assert_not_called()
        invoice.validate_sale_formal_requirements.assert_not_called()
        service._job_repo.add.assert_called_once()


class TestGetTransmission:
    def test_not_found_raises(self, service: TransmissionService):
        service._transmission_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            service.get_transmission(uuid4())

    def test_found(self, service: TransmissionService):
        t = MagicMock()
        t.id = uuid4()
        service._transmission_repo.get_by_id.return_value = t
        assert service.get_transmission(t.id) == t


class TestActiveStatusesPropagation:
    """Commit 07: get_active_for_invoice musi otrzymac _ACTIVE_STATUSES."""

    def test_submit_passes_active_statuses_to_repo(self, service: TransmissionService, actor):
        from app.services.transmission_service import _ACTIVE_STATUSES
        invoice_id = uuid4()
        invoice = MagicMock()
        invoice.id = invoice_id
        invoice.status = InvoiceStatus.READY_FOR_SUBMISSION
        invoice.direction = "sale"
        invoice.number_local = "FV/01/2025/1"
        invoice.updated_at = datetime.now(UTC)
        invoice.can_transition_to = MagicMock(return_value=True)
        invoice.validate_for_ksef = MagicMock()
        invoice.validate_sale_formal_requirements = MagicMock()
        service._invoice_repo.lock_for_update.return_value = invoice
        service._invoice_repo.update.return_value = invoice
        service._settings_service.build_company_snapshot.return_value = {
            "name": "Firma",
            "nip": "1234567890",
        }
        service._settings_service.validate_company_snapshot.return_value = None
        service._transmission_repo.get_active_for_invoice.return_value = None
        service._transmission_repo.get_by_idempotency_key.return_value = None
        service._transmission_repo.add.return_value = MagicMock(id=uuid4(), invoice_id=invoice_id)

        from unittest.mock import patch

        with patch('app.services.transmission_service.KSeFMapper') as mock_mapper:
            mock_mapper.invoice_to_xml.return_value = b'<xml/>'
            mock_mapper.xml_content_hash.return_value = 'hash-1'
            service.submit_invoice(invoice_id, actor)

        service._transmission_repo.get_active_for_invoice.assert_called_once_with(
            invoice_id, _ACTIVE_STATUSES
        )

    def test_active_statuses_contains_queued_processing_submitted_waiting(self, service):
        from app.services.transmission_service import _ACTIVE_STATUSES
        assert TransmissionStatus.QUEUED in _ACTIVE_STATUSES
        assert TransmissionStatus.PROCESSING in _ACTIVE_STATUSES
        assert TransmissionStatus.SUBMITTED in _ACTIVE_STATUSES
        assert TransmissionStatus.WAITING_STATUS in _ACTIVE_STATUSES

    def test_success_not_in_active_statuses(self, service):
        from app.services.transmission_service import _ACTIVE_STATUSES
        assert TransmissionStatus.SUCCESS not in _ACTIVE_STATUSES
        assert TransmissionStatus.FAILED_PERMANENT not in _ACTIVE_STATUSES
        assert TransmissionStatus.FAILED_RETRYABLE not in _ACTIVE_STATUSES


class TestTransmissionStatusSemantics:
    """Commit 07: enum statusow ma spójne znaczenia."""

    def test_all_statuses_are_strings(self):
        for status in TransmissionStatus:
            assert isinstance(status.value, str)

    def test_terminal_statuses(self):
        terminal = {
            TransmissionStatus.SUCCESS,
            TransmissionStatus.FAILED_PERMANENT,
        }
        non_terminal = {
            TransmissionStatus.QUEUED,
            TransmissionStatus.PROCESSING,
            TransmissionStatus.SUBMITTED,
            TransmissionStatus.WAITING_STATUS,
            TransmissionStatus.FAILED_RETRYABLE,
        }
        assert terminal & non_terminal == set()

    def test_retryable_is_not_terminal(self):
        # FAILED_RETRYABLE nie jest ani sukcesem ani permanentnym bledem —
        # serwis moze wykonac retry
        assert TransmissionStatus.FAILED_RETRYABLE != TransmissionStatus.FAILED_PERMANENT
        assert TransmissionStatus.FAILED_RETRYABLE != TransmissionStatus.SUCCESS


class TestSyncInvoiceTerminalStatus:
    def test_failed_permanent_rejects_sending_invoice(self):
        from datetime import date
        from decimal import Decimal
        from app.domain.models.invoice import Invoice, InvoiceItem

        invoice_id = uuid4()
        now = datetime.now(UTC)
        invoice = Invoice(
            id=invoice_id,
            number_local=None,
            status=InvoiceStatus.SENDING,
            issue_date=date(2026, 1, 15),
            sale_date=date(2026, 1, 15),
            currency="PLN",
            seller_snapshot={"nip": "1000000035", "name": "Sprzedawca"},
            buyer_snapshot={"name": "", "nip": ""},
            items=[
                InvoiceItem(
                    name="Usluga",
                    quantity=Decimal("1"),
                    unit="szt.",
                    unit_price_net=Decimal("100"),
                    vat_rate=Decimal("23"),
                    net_total=Decimal("100"),
                    vat_total=Decimal("23"),
                    gross_total=Decimal("123"),
                    sort_order=1,
                )
            ],
            total_net=Decimal("100"),
            total_vat=Decimal("23"),
            total_gross=Decimal("123"),
            created_at=now,
            updated_at=now,
        )
        repo = MagicMock()
        repo.lock_for_update.return_value = invoice
        repo.update.return_value = invoice

        TransmissionService.sync_invoice_from_terminal_transmission(
            repo,
            invoice_id=invoice_id,
            transmission_status=TransmissionStatus.FAILED_PERMANENT,
        )

        assert invoice.status == InvoiceStatus.REJECTED
        repo.update.assert_called_once()

    def test_success_accepts_sending_invoice(self):
        from datetime import date
        from decimal import Decimal
        from app.domain.models.invoice import Invoice, InvoiceItem

        invoice_id = uuid4()
        now = datetime.now(UTC)
        invoice = Invoice(
            id=invoice_id,
            number_local="FV/1/01/2026",
            status=InvoiceStatus.SENDING,
            issue_date=date(2026, 1, 15),
            sale_date=date(2026, 1, 15),
            currency="PLN",
            seller_snapshot={
                "nip": "1000000035",
                "name": "Sprzedawca",
                "street": "ul. Sprzedawcy",
                "building_no": "1",
                "postal_code": "00-001",
                "city": "Warszawa",
            },
            buyer_snapshot={
                "nip": "1000000070",
                "name": "Nabywca",
                "street": "ul. Nabywcy",
                "building_no": "2",
                "postal_code": "30-001",
                "city": "Krakow",
            },
            items=[
                InvoiceItem(
                    name="Usluga",
                    quantity=Decimal("1"),
                    unit="szt.",
                    unit_price_net=Decimal("100"),
                    vat_rate=Decimal("23"),
                    net_total=Decimal("100"),
                    vat_total=Decimal("23"),
                    gross_total=Decimal("123"),
                    sort_order=1,
                )
            ],
            total_net=Decimal("100"),
            total_vat=Decimal("23"),
            total_gross=Decimal("123"),
            created_at=now,
            updated_at=now,
        )
        repo = MagicMock()
        repo.lock_for_update.return_value = invoice
        repo.update.return_value = invoice

        TransmissionService.sync_invoice_from_terminal_transmission(
            repo,
            invoice_id=invoice_id,
            transmission_status=TransmissionStatus.SUCCESS,
            ksef_reference_number="KSeF/001/2026/04",
        )

        assert invoice.status == InvoiceStatus.ACCEPTED
        assert invoice.ksef_reference_number == "KSeF/001/2026/04"
        repo.update.assert_called_once()
