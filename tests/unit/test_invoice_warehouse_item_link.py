"""GWO-IFG-STOCK-0002C — unit tests for InvoiceItem.warehouse_item_id round-trip."""
from __future__ import annotations

from datetime import date, datetime, UTC
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.domain.enums import InvoiceStatus
from app.domain.exceptions import InvalidInvoiceError
from app.domain.models.invoice import Invoice, InvoiceItem
from app.persistence.mappers.invoice_mapper import InvoiceMapper
from app.schemas.invoice import InvoiceItemInput, InvoiceItemResponse
from app.services.invoice_totals import InvoiceTotalsCalculator
from app.services.stock_service import StockService


def _domain_item(*, warehouse_item_id=None) -> InvoiceItem:
    return InvoiceItem(
        id=uuid4(),
        name="Książka",
        quantity=Decimal("2"),
        unit="szt.",
        unit_price_net=Decimal("10.00"),
        vat_rate=Decimal("5"),
        net_total=Decimal("20.00"),
        vat_total=Decimal("1.00"),
        gross_total=Decimal("21.00"),
        sort_order=1,
        isbn="978-83-000000-0-0",
        warehouse_item_id=warehouse_item_id,
    )


def _item_orm_from_domain(item: InvoiceItem):
    orm = MagicMock()
    orm.id = item.id
    orm.name = item.name
    orm.quantity = item.quantity
    orm.unit = item.unit
    orm.unit_price_net = item.unit_price_net
    orm.vat_rate = item.vat_rate
    orm.net_amount = item.net_total
    orm.vat_amount = item.vat_total
    orm.gross_amount = item.gross_total
    orm.sort_order = item.sort_order
    orm.vat_amount_pln = item.vat_amount_pln
    orm.isbn = item.isbn
    orm.warehouse_item_id = item.warehouse_item_id
    return orm


def _invoice_orm(items_domain: list[InvoiceItem]):
    orm = MagicMock()
    orm.id = uuid4()
    orm.number_local = "FV/1/08/2026"
    orm.status = "ready_for_submission"
    orm.issue_date = date(2026, 8, 4)
    orm.sale_date = date(2026, 8, 4)
    orm.delivery_date = None
    orm.due_date = date(2026, 8, 18)
    orm.payment_method = "transfer"
    orm.ksef_reference_number = None
    orm.currency = "PLN"
    orm.seller_snapshot_json = {"nip": "1000000035", "name": "S"}
    orm.buyer_snapshot_json = {"nip": "1000000070", "name": "B"}
    orm.totals_json = {
        "total_net": "20.00",
        "total_vat": "1.00",
        "total_gross": "21.00",
    }
    orm.created_by = uuid4()
    orm.created_at = datetime.now(UTC)
    orm.updated_at = datetime.now(UTC)
    orm.payment_status = "unpaid"
    orm.invoice_type = "VAT"
    orm.correction_of_invoice_id = None
    orm.correction_of_ksef_number = None
    orm.correction_reason = None
    orm.correction_type = None
    orm.use_split_payment = False
    orm.self_billing = False
    orm.reverse_charge = False
    orm.reverse_charge_art = False
    orm.reverse_charge_flag = False
    orm.cash_accounting_method = False
    orm.exchange_rate = None
    orm.exchange_rate_date = None
    orm.advance_amount = None
    orm.advance_links = []
    orm.direction = "sale"
    orm.items = [_item_orm_from_domain(i) for i in items_domain]
    return orm


class TestWarehouseItemIdMapperRoundTrip:
    def test_null_warehouse_item_id_round_trip(self):
        item = _domain_item(warehouse_item_id=None)
        orm_invoice = InvoiceMapper.to_orm(
            Invoice(
                id=uuid4(),
                status=InvoiceStatus.READY_FOR_SUBMISSION,
                issue_date=date(2026, 8, 4),
                sale_date=date(2026, 8, 4),
                currency="PLN",
                seller_snapshot={"nip": "1000000035", "name": "S"},
                buyer_snapshot={"nip": "1000000070", "name": "B"},
                items=[item],
                total_net=Decimal("20.00"),
                total_vat=Decimal("1.00"),
                total_gross=Decimal("21.00"),
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        assert orm_invoice.items[0].warehouse_item_id is None

        back = InvoiceMapper.to_domain(_invoice_orm([item]))
        assert back.items[0].warehouse_item_id is None

    def test_set_warehouse_item_id_round_trip(self):
        wid = uuid4()
        item = _domain_item(warehouse_item_id=wid)
        orm_invoice = InvoiceMapper.to_orm(
            Invoice(
                id=uuid4(),
                status=InvoiceStatus.READY_FOR_SUBMISSION,
                issue_date=date(2026, 8, 4),
                sale_date=date(2026, 8, 4),
                currency="PLN",
                seller_snapshot={"nip": "1000000035", "name": "S"},
                buyer_snapshot={"nip": "1000000070", "name": "B"},
                items=[item],
                total_net=Decimal("20.00"),
                total_vat=Decimal("1.00"),
                total_gross=Decimal("21.00"),
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        assert orm_invoice.items[0].warehouse_item_id == wid

        back = InvoiceMapper.to_domain(_invoice_orm([item]))
        assert back.items[0].warehouse_item_id == wid

    def test_legacy_invoice_without_fk_readable(self):
        """Stara faktura bez warehouse_item_id (NULL) pozostaje odczytywalna."""
        item = _domain_item(warehouse_item_id=None)
        domain = InvoiceMapper.to_domain(_invoice_orm([item]))
        assert domain.items[0].warehouse_item_id is None
        assert domain.items[0].name == "Książka"


class TestApiSchemaWarehouseItemId:
    def test_input_accepts_warehouse_item_id(self):
        wid = uuid4()
        parsed = InvoiceItemInput(
            name="X",
            quantity=Decimal("1"),
            unit="szt.",
            unit_price_net=Decimal("1.00"),
            vat_rate=Decimal("23"),
            warehouse_item_id=wid,
        )
        assert parsed.warehouse_item_id == wid

    def test_input_accepts_null(self):
        parsed = InvoiceItemInput(
            name="Usługa",
            quantity=Decimal("1"),
            unit="szt.",
            unit_price_net=Decimal("100.00"),
            vat_rate=Decimal("23"),
            warehouse_item_id=None,
        )
        assert parsed.warehouse_item_id is None

    def test_response_returns_warehouse_item_id(self):
        wid = uuid4()
        resp = InvoiceItemResponse.from_domain(_domain_item(warehouse_item_id=wid))
        assert resp.warehouse_item_id == wid


class TestTotalsBuildItemsWarehouseItemId:
    def test_build_items_preserves_warehouse_item_id(self):
        wid = uuid4()
        items = InvoiceTotalsCalculator.build_items(
            [
                {
                    "name": "Towar",
                    "quantity": 1,
                    "unit": "szt.",
                    "unit_price_net": "10.00",
                    "vat_rate": "23",
                    "warehouse_item_id": str(wid),
                }
            ]
        )
        assert items[0].warehouse_item_id == wid

    def test_build_items_null_ok(self):
        items = InvoiceTotalsCalculator.build_items(
            [
                {
                    "name": "Usługa",
                    "quantity": 1,
                    "unit": "godz.",
                    "unit_price_net": "50.00",
                    "vat_rate": "23",
                }
            ]
        )
        assert items[0].warehouse_item_id is None


class TestDeadStockHookDisconnected:
    def test_invoice_item_has_no_product_id(self):
        item = _domain_item()
        assert not hasattr(item, "product_id")

    def test_create_invoice_does_not_call_stock_hook(self):
        """Regression: martwy tor stock nie jest wywoływany przy create_invoice."""
        from app.core.security import AuthenticatedUser
        from app.services.invoice_service import InvoiceService

        session = MagicMock()
        session.get.return_value = None
        invoice_repo = MagicMock()
        saved = MagicMock()
        saved.id = uuid4()
        saved.status = InvoiceStatus.READY_FOR_SUBMISSION
        saved.direction = "sale"
        saved.total_gross = Decimal("21.00")
        saved.number_local = "FV/1/08/2026"
        saved.items = [_domain_item()]
        invoice_repo.add.return_value = saved
        invoice_repo.get_by_id.return_value = saved

        contractor_repo = MagicMock()
        contractor = MagicMock()
        contractor.id = uuid4()
        contractor_repo.get_by_id.return_value = contractor
        override_repo = MagicMock()
        override_repo.get_active_by_contractor_id.return_value = None
        audit = MagicMock()

        with patch.object(
            InvoiceService,
            "_allocate_number_local",
            return_value="FV/1/08/2026",
        ), patch.object(
            InvoiceService,
            "_build_company_snapshot",
            return_value={
                "nip": "1000000035",
                "name": "S",
                "street": "ul.",
                "building_no": "1",
                "postal_code": "00-001",
                "city": "Wawa",
            },
        ), patch(
            "app.persistence.mappers.invoice_mapper.InvoiceMapper.build_contractor_snapshot",
            return_value={
                "nip": "1000000070",
                "name": "B",
                "street": "ul.",
                "building_no": "2",
                "postal_code": "30-001",
                "city": "Krk",
            },
        ):
            svc = InvoiceService(
                session=session,
                invoice_repository=invoice_repo,
                contractor_repository=contractor_repo,
                contractor_override_repository=override_repo,
                audit_service=audit,
            )
            # Celowo nie przekazujemy stock_service — parametr usunięty.
            assert not hasattr(svc, "stock_service")

            with patch.object(StockService, "handle_invoice_created") as stock_hook:
                result = svc.create_invoice(
                    {
                        "buyer_id": contractor.id,
                        "issue_date": date(2026, 8, 4),
                        "sale_date": date(2026, 8, 4),
                        "due_date": date(2026, 8, 18),
                        "payment_method": "transfer",
                        "direction": "sale",
                        "items": [
                            {
                                "name": "Książka",
                                "quantity": 2,
                                "unit": "szt.",
                                "unit_price_net": "10.00",
                                "vat_rate": "5",
                            }
                        ],
                    },
                    AuthenticatedUser(
                        user_id=str(uuid4()),
                        username="t",
                        role="administrator",
                    ),
                )
                stock_hook.assert_not_called()
                assert result is saved

    def test_missing_warehouse_item_rejected(self):
        from app.services.invoice_service import InvoiceService

        session = MagicMock()
        session.get.return_value = None
        svc = InvoiceService(
            session=session,
            invoice_repository=MagicMock(),
            contractor_repository=MagicMock(),
            contractor_override_repository=MagicMock(),
            audit_service=MagicMock(),
        )
        with pytest.raises(InvalidInvoiceError, match="nie istnieje"):
            svc._validate_warehouse_item_refs(
                [_domain_item(warehouse_item_id=uuid4())]
            )
