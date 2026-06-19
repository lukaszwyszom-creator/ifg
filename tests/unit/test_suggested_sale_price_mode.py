"""Semantyka suggested_sale_price_mode — net (historyczne) vs gross (PZ)."""
from __future__ import annotations

from decimal import Decimal

from app.persistence.models.warehouse_item import WarehouseItemORM
from tests.unit.test_warehouse_documents import ITEM_ID, _make_service, _pz_body


class TestPzPostSuggestedSalePriceMode:
    def test_post_pz_sets_catalog_mode_gross_for_normative_price(self):
        svc, _, _ = _make_service()
        catalog_item = WarehouseItemORM(
            id=ITEM_ID,
            name="Książka",
            item_type="goods",
            vat_rate=Decimal("23"),
            default_price_net=None,
            suggested_sale_price=None,
            suggested_sale_price_mode="net",
            unit="szt.",
            is_warehouse_active=True,
            is_active=True,
        )
        svc.session.get.return_value = catalog_item

        body = _pz_body()
        body["items"][0]["suggested_sale_price"] = "123.00"
        body["items"][0]["suggested_sale_price_mode"] = "gross"

        doc = svc.create_document(body)
        svc.post_document(doc.id)

        assert catalog_item.suggested_sale_price == Decimal("123.0000")
        assert catalog_item.suggested_sale_price_mode == "gross"
        assert catalog_item.default_price_net == Decimal("20.00")

    def test_post_pz_without_normative_price_keeps_catalog_mode(self):
        svc, _, _ = _make_service()
        catalog_item = WarehouseItemORM(
            id=ITEM_ID,
            name="Książka",
            item_type="goods",
            vat_rate=Decimal("23"),
            default_price_net=Decimal("15.00"),
            suggested_sale_price=Decimal("99.00"),
            suggested_sale_price_mode="net",
            unit="szt.",
            is_warehouse_active=True,
            is_active=True,
        )
        svc.session.get.return_value = catalog_item

        doc = svc.create_document(_pz_body())
        svc.post_document(doc.id)

        assert catalog_item.suggested_sale_price == Decimal("99.00")
        assert catalog_item.suggested_sale_price_mode == "net"

    def test_post_pz_defaults_doc_item_mode_to_gross_when_price_set(self):
        svc, _, _ = _make_service()
        svc.session.get.return_value = WarehouseItemORM(
            id=ITEM_ID,
            name="Książka",
            item_type="goods",
            vat_rate=None,
            default_price_net=None,
            suggested_sale_price_mode="net",
            unit="szt.",
            is_warehouse_active=True,
            is_active=True,
        )

        body = _pz_body()
        body["items"][0]["suggested_sale_price"] = "50.00"

        doc = svc.create_document(body)

        assert doc.doc_items[0].suggested_sale_price_mode == "gross"
