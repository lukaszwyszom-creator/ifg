"""Testy InvoiceService — unit (mocki repozytoriów)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, UTC
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.core.security import AuthenticatedUser
from app.domain.enums import InvoiceStatus, PaymentMethod
from app.domain.exceptions import InvalidInvoiceError, InvalidStatusTransitionError
from app.domain.models.invoice import Invoice, InvoiceItem
from app.services.invoice_service import InvoiceService
from app.services.invoice_totals import InvoiceTotalsCalculator


@pytest.fixture()
def service(mock_session: MagicMock) -> InvoiceService:
    return InvoiceService(
        session=mock_session,
        invoice_repository=MagicMock(),
        contractor_repository=MagicMock(),
        contractor_override_repository=MagicMock(),
        audit_service=MagicMock(),
    )


def _valid_create_data(buyer_id=None) -> dict:
    return {
        "buyer_id": buyer_id or uuid4(),
        "issue_date": date(2026, 4, 5),
        "sale_date": date(2026, 4, 5),
        "due_date": date(2026, 4, 19),
        "payment_method": "transfer",
        "currency": "PLN",
        "items": [
            {
                "name": "Usługa",
                "quantity": "10",
                "unit": "godz.",
                "unit_price_net": "200.00",
                "vat_rate": "23",
            }
        ],
    }


class TestCreateInvoice:
    def test_missing_buyer_id_raises(self, service: InvoiceService, actor: AuthenticatedUser):
        data = _valid_create_data()
        data["buyer_id"] = None
        with pytest.raises(InvalidInvoiceError, match="buyer_id"):
            service.create_invoice(data, actor)

    def test_empty_items_raises(self, service: InvoiceService, actor: AuthenticatedUser):
        data = _valid_create_data()
        data["items"] = []
        with pytest.raises(InvalidInvoiceError, match="co najmniej jedną pozycję"):
            service.create_invoice(data, actor)

    def test_fractional_quantity_raises(self):
        with pytest.raises(InvalidInvoiceError, match="liczbą całkowitą"):
            InvoiceTotalsCalculator.build_items([
                {
                    "name": "Książka",
                    "quantity": "2.5",
                    "unit": "szt.",
                    "unit_price_net": "100",
                    "vat_rate": "23",
                }
            ])

    def test_sale_date_after_issue_date_raises(self, service: InvoiceService, actor: AuthenticatedUser):
        data = _valid_create_data()
        data["issue_date"] = date(2026, 4, 1)
        data["sale_date"] = date(2026, 4, 5)
        with pytest.raises(InvalidInvoiceError, match="Data sprzedaży"):
            service.create_invoice(data, actor)

    @patch("app.services.invoice_service.settings")
    def test_create_success(self, mock_settings, service: InvoiceService, actor: AuthenticatedUser):
        mock_settings.seller_nip = "1234567890"
        mock_settings.seller_name = "Firma"
        mock_settings.seller_street = "ul. Testowa"
        mock_settings.seller_building_no = "1"
        mock_settings.seller_apartment_no = None
        mock_settings.seller_postal_code = "00-001"
        mock_settings.seller_city = "Warszawa"
        mock_settings.seller_country = "PL"

        buyer_id = uuid4()
        data = _valid_create_data(buyer_id)

        # Mock contractor repo
        contractor_mock = MagicMock()
        contractor_mock.nip = "0987654321"
        contractor_mock.name = "Nabywca"
        service.contractor_repository.get_by_id.return_value = contractor_mock
        service.contractor_override_repository.get_active_by_contractor_id.return_value = None

        # Mock invoice repo
        now = datetime.now(UTC)
        expected = Invoice(
            id=uuid4(),
            status=InvoiceStatus.READY_FOR_SUBMISSION,
            issue_date=data["issue_date"],
            sale_date=data["sale_date"],
            currency="PLN",
            seller_snapshot={},
            buyer_snapshot={},
            items=[],
            total_net=Decimal("2000.00"),
            total_vat=Decimal("460.00"),
            total_gross=Decimal("2460.00"),
            created_at=now,
            updated_at=now,
        )
        service.invoice_repository.add.return_value = expected

        result = service.create_invoice(data, actor)

        assert result == expected
        service.invoice_repository.add.assert_called_once()
        service.audit_service.record.assert_called_once()

    @patch("app.services.invoice_service.settings")
    def test_create_sale_uses_seller_from_company_buyer_from_contractor(
        self, mock_settings, service: InvoiceService, actor: AuthenticatedUser
    ):
        mock_settings.seller_nip = "1234567890"
        mock_settings.seller_name = "Nasza Firma"
        mock_settings.seller_street = "ul. Firmowa"
        mock_settings.seller_building_no = "1"
        mock_settings.seller_apartment_no = None
        mock_settings.seller_postal_code = "00-001"
        mock_settings.seller_city = "Warszawa"
        mock_settings.seller_country = "PL"

        buyer_id = uuid4()
        data = _valid_create_data(buyer_id)
        data["direction"] = "sale"

        contractor_mock = MagicMock()
        contractor_mock.nip = "0987654321"
        contractor_mock.name = "Kontrahent"
        contractor_mock.street = "ul. Klienta"
        contractor_mock.building_no = "5"
        contractor_mock.apartment_no = None
        contractor_mock.postal_code = "30-001"
        contractor_mock.city = "Kraków"
        contractor_mock.voivodeship = None
        contractor_mock.county = None
        contractor_mock.commune = None
        contractor_mock.country = "PL"
        contractor_mock.krs = None
        contractor_mock.legal_form = None
        contractor_mock.regon = None
        service.contractor_repository.get_by_id.return_value = contractor_mock
        service.contractor_override_repository.get_active_by_contractor_id.return_value = None

        expected = MagicMock()
        service.invoice_repository.add.return_value = expected

        service.create_invoice(data, actor)

        created_invoice = service.invoice_repository.add.call_args.args[0]
        assert created_invoice.direction == "sale"
        assert created_invoice.seller_snapshot["name"] == "Nasza Firma"
        assert created_invoice.seller_snapshot["nip"] == "1234567890"
        assert created_invoice.buyer_snapshot["name"] == "Kontrahent"
        assert created_invoice.buyer_snapshot["nip"] == "0987654321"

    @patch("app.services.invoice_service.settings")
    def test_create_purchase_uses_seller_from_contractor_buyer_from_company(
        self, mock_settings, service: InvoiceService, actor: AuthenticatedUser
    ):
        mock_settings.seller_nip = "1234567890"
        mock_settings.seller_name = "Nasza Firma"
        mock_settings.seller_street = "ul. Firmowa"
        mock_settings.seller_building_no = "1"
        mock_settings.seller_apartment_no = None
        mock_settings.seller_postal_code = "00-001"
        mock_settings.seller_city = "Warszawa"
        mock_settings.seller_country = "PL"

        buyer_id = uuid4()
        data = _valid_create_data(buyer_id)
        data["direction"] = "purchase"

        contractor_mock = MagicMock()
        contractor_mock.nip = "0987654321"
        contractor_mock.name = "Dostawca"
        contractor_mock.street = "ul. Dostawcy"
        contractor_mock.building_no = "5"
        contractor_mock.apartment_no = None
        contractor_mock.postal_code = "30-001"
        contractor_mock.city = "Kraków"
        contractor_mock.voivodeship = None
        contractor_mock.county = None
        contractor_mock.commune = None
        contractor_mock.country = "PL"
        contractor_mock.krs = None
        contractor_mock.legal_form = None
        contractor_mock.regon = None
        service.contractor_repository.get_by_id.return_value = contractor_mock
        service.contractor_override_repository.get_active_by_contractor_id.return_value = None

        expected = MagicMock()
        service.invoice_repository.add.return_value = expected

        service.create_invoice(data, actor)

        created_invoice = service.invoice_repository.add.call_args.args[0]
        assert created_invoice.direction == "purchase"
        assert created_invoice.seller_snapshot["name"] == "Dostawca"
        assert created_invoice.seller_snapshot["nip"] == "0987654321"
        assert created_invoice.buyer_snapshot["name"] == "Nasza Firma"
        assert created_invoice.buyer_snapshot["nip"] == "1234567890"

    @patch("app.services.invoice_service.settings")
    def test_create_rejects_missing_company_name_or_nip(
        self, mock_settings, service: InvoiceService, actor: AuthenticatedUser
    ):
        mock_settings.seller_nip = ""
        mock_settings.seller_name = ""
        mock_settings.seller_street = "ul. Firmowa"
        mock_settings.seller_building_no = "1"
        mock_settings.seller_apartment_no = None
        mock_settings.seller_postal_code = "00-001"
        mock_settings.seller_city = "Warszawa"
        mock_settings.seller_country = "PL"

        buyer_id = uuid4()
        data = _valid_create_data(buyer_id)
        service.contractor_repository.get_by_id.return_value = MagicMock()
        service.contractor_override_repository.get_active_by_contractor_id.return_value = None

        with pytest.raises(InvalidInvoiceError, match="Uzupełnij dane sprzedawcy"):
            service.create_invoice(data, actor)

    def test_item_negative_quantity_raises(self, service: InvoiceService, actor: AuthenticatedUser):
        data = _valid_create_data()
        data["items"][0]["quantity"] = "-1"

        # Need contractor mock for _resolve_buyer_snapshot
        service.contractor_repository.get_by_id.return_value = MagicMock()
        service.contractor_override_repository.get_active_by_contractor_id.return_value = None

        with pytest.raises(InvalidInvoiceError, match="ilość"):
            with patch("app.services.invoice_service.settings") as mock_s:
                mock_s.seller_nip = "1234567890"
                mock_s.seller_name = "F"
                mock_s.seller_street = "S"
                mock_s.seller_building_no = "1"
                mock_s.seller_apartment_no = None
                mock_s.seller_postal_code = "00-001"
                mock_s.seller_city = "W"
                mock_s.seller_country = "PL"
                service.create_invoice(data, actor)

    def test_item_empty_name_raises(self, service: InvoiceService, actor: AuthenticatedUser):
        data = _valid_create_data()
        data["items"][0]["name"] = "   "

        service.contractor_repository.get_by_id.return_value = MagicMock()
        service.contractor_override_repository.get_active_by_contractor_id.return_value = None

        with pytest.raises(InvalidInvoiceError, match="nazwa"):
            with patch("app.services.invoice_service.settings") as mock_s:
                mock_s.seller_nip = "X"
                mock_s.seller_name = "F"
                mock_s.seller_street = "S"
                mock_s.seller_building_no = "1"
                mock_s.seller_apartment_no = None
                mock_s.seller_postal_code = "00-001"
                mock_s.seller_city = "W"
                mock_s.seller_country = "PL"
                service.create_invoice(data, actor)

    def test_item_vat_over_100_raises(self, service: InvoiceService, actor: AuthenticatedUser):
        data = _valid_create_data()
        data["items"][0]["vat_rate"] = "101"

        service.contractor_repository.get_by_id.return_value = MagicMock()
        service.contractor_override_repository.get_active_by_contractor_id.return_value = None

        with pytest.raises(InvalidInvoiceError, match="VAT"):
            with patch("app.services.invoice_service.settings") as mock_s:
                mock_s.seller_nip = "X"
                mock_s.seller_name = "F"
                mock_s.seller_street = "S"
                mock_s.seller_building_no = "1"
                mock_s.seller_apartment_no = None
                mock_s.seller_postal_code = "00-001"
                mock_s.seller_city = "W"
                mock_s.seller_country = "PL"
                service.create_invoice(data, actor)


class TestGetInvoice:
    def test_found(self, service: InvoiceService, sample_invoice: Invoice):
        service.invoice_repository.get_by_id.return_value = sample_invoice
        result = service.get_invoice(sample_invoice.id)
        assert result.id == sample_invoice.id

    def test_not_found_raises(self, service: InvoiceService):
        service.invoice_repository.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            service.get_invoice(uuid4())


class TestCreateInvoiceFA3Fields:
    """Testy pola delivery_date w create_invoice."""

    @patch("app.services.invoice_service.settings")
    def test_delivery_date_passed_through(self, mock_settings, service: InvoiceService, actor: AuthenticatedUser):
        mock_settings.seller_nip = "1234567890"
        mock_settings.seller_name = "Firma"
        mock_settings.seller_street = "ul. Testowa"
        mock_settings.seller_building_no = "1"
        mock_settings.seller_apartment_no = None
        mock_settings.seller_postal_code = "00-001"
        mock_settings.seller_city = "Warszawa"
        mock_settings.seller_country = "PL"

        data = _valid_create_data()
        data["delivery_date"] = date(2026, 4, 3)

        service.contractor_repository.get_by_id.return_value = MagicMock()
        service.contractor_override_repository.get_active_by_contractor_id.return_value = None

        now = datetime.now(UTC)
        captured = Invoice(
            id=uuid4(),
            status=InvoiceStatus.READY_FOR_SUBMISSION,
            issue_date=data["issue_date"],
            sale_date=data["sale_date"],
            delivery_date=date(2026, 4, 3),
            currency="PLN",
            seller_snapshot={},
            buyer_snapshot={},
            items=[],
            total_net=Decimal("0"),
            total_vat=Decimal("0"),
            total_gross=Decimal("0"),
            created_at=now,
            updated_at=now,
        )
        service.invoice_repository.add.return_value = captured

        result = service.create_invoice(data, actor)

        assert result.delivery_date == date(2026, 4, 3)

    @patch("app.services.invoice_service.settings")
    def test_delivery_date_none_when_not_provided(self, mock_settings, service: InvoiceService, actor: AuthenticatedUser):
        mock_settings.seller_nip = "1234567890"
        mock_settings.seller_name = "Firma"
        mock_settings.seller_street = "ul. Testowa"
        mock_settings.seller_building_no = "1"
        mock_settings.seller_apartment_no = None
        mock_settings.seller_postal_code = "00-001"
        mock_settings.seller_city = "Warszawa"
        mock_settings.seller_country = "PL"

        data = _valid_create_data()  # brak delivery_date

        service.contractor_repository.get_by_id.return_value = MagicMock()
        service.contractor_override_repository.get_active_by_contractor_id.return_value = None

        now = datetime.now(UTC)
        returned = Invoice(
            id=uuid4(),
            status=InvoiceStatus.READY_FOR_SUBMISSION,
            issue_date=data["issue_date"],
            sale_date=data["sale_date"],
            delivery_date=None,
            currency="PLN",
            seller_snapshot={},
            buyer_snapshot={},
            items=[],
            total_net=Decimal("0"),
            total_vat=Decimal("0"),
            total_gross=Decimal("0"),
            created_at=now,
            updated_at=now,
        )
        service.invoice_repository.add.return_value = returned

        result = service.create_invoice(data, actor)

        assert result.delivery_date is None


class TestPaymentFields:
    def test_validate_due_date_rejects_more_than_59_days(self):
        issue = date(2026, 4, 5)
        with pytest.raises(InvalidInvoiceError, match="59"):
            InvoiceService._validate_due_date(issue, issue + timedelta(days=60))

    def test_validate_due_date_rejects_before_issue(self):
        issue = date(2026, 4, 5)
        with pytest.raises(InvalidInvoiceError, match="wcześniejszy"):
            InvoiceService._validate_due_date(issue, date(2026, 4, 4))

    def test_normalize_payment_method_rejects_unknown(self):
        with pytest.raises(InvalidInvoiceError, match="Sposób płatności"):
            InvoiceService._normalize_payment_method("card")

    def test_normalize_payment_method_requires_value_when_required(self):
        with pytest.raises(InvalidInvoiceError, match="wymagany"):
            InvoiceService._normalize_payment_method(None, required=True)

    def test_create_invoice_requires_due_date_for_sale(
        self, service: InvoiceService, actor: AuthenticatedUser
    ):
        data = _valid_create_data()
        data.pop("due_date")
        with pytest.raises(InvalidInvoiceError, match="Termin płatności"):
            service.create_invoice(data, actor)

    def test_create_invoice_requires_payment_method_for_sale(
        self, service: InvoiceService, actor: AuthenticatedUser
    ):
        data = _valid_create_data()
        data.pop("payment_method")
        with pytest.raises(InvalidInvoiceError, match="Sposób płatności"):
            service.create_invoice(data, actor)

    @patch("app.services.invoice_service.settings")
    def test_create_invoice_passes_payment_fields(
        self, mock_settings, service: InvoiceService, actor: AuthenticatedUser
    ):
        mock_settings.seller_nip = "1234567890"
        mock_settings.seller_name = "Firma"
        mock_settings.seller_street = "ul. Testowa"
        mock_settings.seller_building_no = "1"
        mock_settings.seller_apartment_no = None
        mock_settings.seller_postal_code = "00-001"
        mock_settings.seller_city = "Warszawa"
        mock_settings.seller_country = "PL"

        data = _valid_create_data()
        data["due_date"] = date(2026, 4, 19)
        data["payment_method"] = "cash"

        service.contractor_repository.get_by_id.return_value = MagicMock()
        service.contractor_override_repository.get_active_by_contractor_id.return_value = None

        now = datetime.now(UTC)
        captured = Invoice(
            id=uuid4(),
            status=InvoiceStatus.READY_FOR_SUBMISSION,
            issue_date=data["issue_date"],
            sale_date=data["sale_date"],
            due_date=date(2026, 4, 19),
            currency="PLN",
            seller_snapshot={},
            buyer_snapshot={},
            items=[],
            total_net=Decimal("0"),
            total_vat=Decimal("0"),
            total_gross=Decimal("0"),
            created_at=now,
            updated_at=now,
        )
        service.invoice_repository.add.side_effect = lambda inv: inv

        result = service.create_invoice(data, actor)

        assert result.due_date == date(2026, 4, 19)
        assert result.payment_method == PaymentMethod.CASH


class TestListInvoices:
    def test_returns_tuple(self, service: InvoiceService, sample_invoice: Invoice):
        service.invoice_repository.list_paginated.return_value = ([sample_invoice], 1)
        items, total = service.list_invoices(page=1, size=20)
        assert total == 1
        assert len(items) == 1

    def test_open_view_filters_by_payment_status_and_orders_by_due_date(
        self, service: InvoiceService, sample_invoice: Invoice
    ):
        service.invoice_repository.list_paginated.return_value = ([sample_invoice], 1)

        service.list_invoices(view="open")

        kwargs = service.invoice_repository.list_paginated.call_args.kwargs
        assert kwargs["payment_status_in"] == ("unpaid", "partially_paid")
        assert kwargs["order_by_due_date"] is True

    def test_open_view_ignores_date_filters(
        self, service: InvoiceService, sample_invoice: Invoice
    ):
        from datetime import date as _date

        service.invoice_repository.list_paginated.return_value = ([sample_invoice], 1)

        service.list_invoices(
            view="open",
            issue_date_from=_date(2026, 1, 1),
            issue_date_before=_date(2026, 2, 1),
        )

        kwargs = service.invoice_repository.list_paginated.call_args.kwargs
        assert kwargs["issue_date_from"] is None
        assert kwargs["issue_date_to"] is None
        assert kwargs["issue_date_before"] is None

    def test_month_view_does_not_apply_open_filters(
        self, service: InvoiceService, sample_invoice: Invoice
    ):
        service.invoice_repository.list_paginated.return_value = ([sample_invoice], 1)

        service.list_invoices(view="month")

        kwargs = service.invoice_repository.list_paginated.call_args.kwargs
        assert kwargs["payment_status_in"] is None
        assert kwargs["order_by_due_date"] is False


class TestComputeRemainingAmounts:
    def _service_with_alloc(self, mock_session, alloc_repo) -> InvoiceService:
        return InvoiceService(
            session=mock_session,
            invoice_repository=MagicMock(),
            contractor_repository=MagicMock(),
            contractor_override_repository=MagicMock(),
            audit_service=MagicMock(),
            payment_allocation_repository=alloc_repo,
        )

    def test_partially_paid_returns_positive_remaining(
        self, mock_session, sample_invoice: Invoice
    ):
        # Faktura: total_gross = 2460.00, zapłacono 1000.00 → pozostało 1460.00
        sample_invoice.payment_status = "partially_paid"
        alloc_repo = MagicMock()
        alloc_repo.sum_allocated_for_invoices.return_value = {
            sample_invoice.id: Decimal("1000.00")
        }
        svc = self._service_with_alloc(mock_session, alloc_repo)

        result = svc.compute_remaining_amounts([sample_invoice])

        assert result[sample_invoice.id] == Decimal("1460.00")
        assert result[sample_invoice.id] > Decimal("0")
        # Optymalizacja: dokładnie jedno wywołanie batch zamiast N pojedynczych.
        assert alloc_repo.sum_allocated_for_invoices.call_count == 1

    def test_unpaid_no_allocations_equals_total_gross(
        self, mock_session, sample_invoice: Invoice
    ):
        alloc_repo = MagicMock()
        # Brak wpisu w mapie = brak alokacji = pełna kwota do zapłaty.
        alloc_repo.sum_allocated_for_invoices.return_value = {}
        svc = self._service_with_alloc(mock_session, alloc_repo)

        result = svc.compute_remaining_amounts([sample_invoice])

        assert result[sample_invoice.id] == Decimal("2460.00")

    def test_paid_in_full_returns_zero(
        self, mock_session, sample_invoice: Invoice
    ):
        alloc_repo = MagicMock()
        alloc_repo.sum_allocated_for_invoices.return_value = {
            sample_invoice.id: Decimal("2460.00")
        }
        svc = self._service_with_alloc(mock_session, alloc_repo)

        result = svc.compute_remaining_amounts([sample_invoice])

        assert result[sample_invoice.id] == Decimal("0.00")

    def test_batch_query_for_multiple_invoices(
        self, mock_session, sample_invoice: Invoice, sample_invoice_item
    ):
        # Druga faktura z innym id, bez alokacji.
        from datetime import datetime as _dt, UTC as _UTC
        from uuid import uuid4 as _uuid4
        from app.domain.enums import InvoiceStatus as _Status
        now = _dt.now(_UTC)
        other = Invoice(
            id=_uuid4(),
            number_local="FV/2/04/2026",
            status=_Status.READY_FOR_SUBMISSION,
            issue_date=sample_invoice.issue_date,
            sale_date=sample_invoice.sale_date,
            currency="PLN",
            seller_snapshot={},
            buyer_snapshot={},
            items=[sample_invoice_item],
            total_net=Decimal("100.00"),
            total_vat=Decimal("23.00"),
            total_gross=Decimal("123.00"),
            created_at=now,
            updated_at=now,
        )
        alloc_repo = MagicMock()
        alloc_repo.sum_allocated_for_invoices.return_value = {
            sample_invoice.id: Decimal("500.00"),
        }
        svc = self._service_with_alloc(mock_session, alloc_repo)

        result = svc.compute_remaining_amounts([sample_invoice, other])

        # Jedna kwerenda dla obu faktur.
        assert alloc_repo.sum_allocated_for_invoices.call_count == 1
        called_ids = alloc_repo.sum_allocated_for_invoices.call_args.args[0]
        assert set(called_ids) == {sample_invoice.id, other.id}
        assert result[sample_invoice.id] == Decimal("1960.00")
        assert result[other.id] == Decimal("123.00")

    def test_no_repo_returns_empty_map(
        self, mock_session, sample_invoice: Invoice
    ):
        svc = InvoiceService(
            session=mock_session,
            invoice_repository=MagicMock(),
            contractor_repository=MagicMock(),
            contractor_override_repository=MagicMock(),
            audit_service=MagicMock(),
        )

        assert svc.compute_remaining_amounts([sample_invoice]) == {}


class TestMarkAsReady:
    def test_ready_for_submission_without_number_assigns_number(
        self,
        service: InvoiceService,
        actor: AuthenticatedUser,
        sample_invoice: Invoice,
    ):
        sample_invoice.status = InvoiceStatus.READY_FOR_SUBMISSION
        sample_invoice.number_local = None
        service.invoice_repository.lock_for_update.return_value = sample_invoice
        service.invoice_repository.get_next_sequence_number.return_value = 1
        service.invoice_repository.exists_by_number.return_value = False
        service.invoice_repository.update.return_value = sample_invoice

        result = service.mark_as_ready(sample_invoice.id, actor)

        assert result.number_local is not None
        service.invoice_repository.get_next_sequence_number.assert_called_once()
        service.invoice_repository.update.assert_called_once()
        service.audit_service.record.assert_called_once()

    def test_ready_for_submission_with_number_is_idempotent(
        self,
        service: InvoiceService,
        actor: AuthenticatedUser,
        sample_invoice: Invoice,
    ):
        sample_invoice.status = InvoiceStatus.READY_FOR_SUBMISSION
        sample_invoice.number_local = "FV/2026/04/001"
        service.invoice_repository.lock_for_update.return_value = sample_invoice

        result = service.mark_as_ready(sample_invoice.id, actor)

        assert result.number_local == "FV/2026/04/001"
        service.invoice_repository.get_next_sequence_number.assert_not_called()
        service.invoice_repository.update.assert_not_called()
        service.audit_service.record.assert_not_called()

    @pytest.mark.parametrize(
        "status",
        [InvoiceStatus.SENDING, InvoiceStatus.ACCEPTED, InvoiceStatus.REJECTED],
    )
    def test_non_ready_statuses_raise_invalid_transition(
        self,
        service: InvoiceService,
        actor: AuthenticatedUser,
        sample_invoice: Invoice,
        status: InvoiceStatus,
    ):
        sample_invoice.status = status
        service.invoice_repository.lock_for_update.return_value = sample_invoice

        with pytest.raises(InvalidStatusTransitionError):
            service.mark_as_ready(sample_invoice.id, actor)

    def test_mark_as_ready_rejects_incomplete_seller_snapshot(
        self,
        service: InvoiceService,
        actor: AuthenticatedUser,
        sample_invoice: Invoice,
    ):
        sample_invoice.status = InvoiceStatus.READY_FOR_SUBMISSION
        sample_invoice.number_local = None
        sample_invoice.seller_snapshot = {"name": "", "nip": ""}
        sample_invoice.buyer_snapshot = {
            "name": "Nabywca",
            "nip": "1000000070",
            "street": "ul. Nabywcy",
            "building_no": "2",
            "postal_code": "30-001",
            "city": "Krakow",
        }
        service.invoice_repository.lock_for_update.return_value = sample_invoice

        with pytest.raises(InvalidInvoiceError, match="snapshot sprzedawcy"):
            service.mark_as_ready(sample_invoice.id, actor)

    def test_mark_as_ready_rejects_incomplete_buyer_snapshot(
        self,
        service: InvoiceService,
        actor: AuthenticatedUser,
        sample_invoice: Invoice,
    ):
        sample_invoice.status = InvoiceStatus.READY_FOR_SUBMISSION
        sample_invoice.number_local = None
        sample_invoice.seller_snapshot = {
            "name": "Sprzedawca",
            "nip": "1000000035",
            "street": "ul. Sprzedawcy",
            "building_no": "1",
            "postal_code": "00-001",
            "city": "Warszawa",
        }
        sample_invoice.buyer_snapshot = {"name": "", "nip": ""}
        service.invoice_repository.lock_for_update.return_value = sample_invoice

        with pytest.raises(InvalidInvoiceError, match="snapshot nabywcy"):
            service.mark_as_ready(sample_invoice.id, actor)

    def test_mark_as_ready_purchase_does_not_apply_sale_formal_guard(
        self,
        service: InvoiceService,
        actor: AuthenticatedUser,
        sample_invoice: Invoice,
    ):
        sample_invoice.status = InvoiceStatus.READY_FOR_SUBMISSION
        sample_invoice.direction = "purchase"
        sample_invoice.number_local = None
        sample_invoice.seller_snapshot = {"name": "", "nip": ""}
        sample_invoice.buyer_snapshot = {"name": "", "nip": ""}
        service.invoice_repository.lock_for_update.return_value = sample_invoice
        service.invoice_repository.get_next_sequence_number.return_value = 1
        service.invoice_repository.exists_by_number.return_value = False
        service.invoice_repository.update.return_value = sample_invoice

        result = service.mark_as_ready(sample_invoice.id, actor)

        assert result.number_local is not None


class TestIsInvoiceEditable:
    """Testy logiki edytowalności faktury."""

    def test_ready_for_submission_is_editable(self):
        """READY_FOR_SUBMISSION (gotowa do wysyłki) - edytowalna."""
        assert InvoiceService.is_invoice_editable(InvoiceStatus.READY_FOR_SUBMISSION) is True
        assert InvoiceService.is_invoice_editable("ready_for_submission") is True

    def test_rejected_is_editable(self):
        """REJECTED (odrzucona, wymaga poprawy) - edytowalna."""
        assert InvoiceService.is_invoice_editable(InvoiceStatus.REJECTED) is True
        assert InvoiceService.is_invoice_editable("rejected") is True

    def test_sending_is_not_editable(self):
        """SENDING (analiza w KSeF) - nieedytowalna."""
        assert InvoiceService.is_invoice_editable(InvoiceStatus.SENDING) is False
        assert InvoiceService.is_invoice_editable("sending") is False

    def test_accepted_is_not_editable(self):
        """ACCEPTED (zaakceptowana) - nieedytowalna."""
        assert InvoiceService.is_invoice_editable(InvoiceStatus.ACCEPTED) is False
        assert InvoiceService.is_invoice_editable("accepted") is False

    def test_invalid_status_raises(self):
        """Próba użycia nieistniejącego statusu rzuca błąd."""
        with pytest.raises(ValueError):
            InvoiceService.is_invoice_editable("invalid_status")

    def test_draft_status_raises(self):
        """Próba użycia usuniętego statusu draft rzuca błąd."""
        with pytest.raises(ValueError):
            InvoiceService.is_invoice_editable("draft")
