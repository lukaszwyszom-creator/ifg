"""Testy kalkulacji pozycji faktury."""
from __future__ import annotations

from decimal import Decimal

from app.services.invoice_totals import InvoiceTotalsCalculator


def test_gross_price_mode_line_amounts_regression() -> None:
    """unit_price_gross=120, qty=60, VAT 5% → gross 7200.00, net 6857.14, vat 342.86."""
    unit_net, net, vat, gross = InvoiceTotalsCalculator.calculate_line_amounts(
        quantity=Decimal("60"),
        vat_rate=Decimal("5"),
        price_mode="gross",
        unit_price_gross=Decimal("120.00"),
    )

    assert gross == Decimal("7200.00")
    assert net == Decimal("6857.14")
    assert vat == Decimal("342.86")
    assert unit_net == Decimal("114.29")


def test_net_price_mode_unchanged() -> None:
    unit_net, net, vat, gross = InvoiceTotalsCalculator.calculate_line_amounts(
        quantity=Decimal("10"),
        vat_rate=Decimal("23"),
        price_mode="net",
        unit_price_net=Decimal("200.00"),
    )

    assert unit_net == Decimal("200.00")
    assert net == Decimal("2000.00")
    assert vat == Decimal("460.00")
    assert gross == Decimal("2460.00")


def test_build_items_gross_mode_persists_line_amounts() -> None:
    items = InvoiceTotalsCalculator.build_items([
        {
            "name": "Usługa",
            "quantity": "60",
            "unit": "szt.",
            "price_mode": "gross",
            "unit_price_net": "0",
            "unit_price_gross": "120.00",
            "vat_rate": "5",
        }
    ])

    assert len(items) == 1
    item = items[0]
    assert item.net_total == Decimal("6857.14")
    assert item.vat_total == Decimal("342.86")
    assert item.gross_total == Decimal("7200.00")


def test_calculate_totals_sums_line_amounts() -> None:
    items = InvoiceTotalsCalculator.build_items([
        {
            "name": "A",
            "quantity": "60",
            "unit": "szt.",
            "price_mode": "gross",
            "unit_price_gross": "120.00",
            "unit_price_net": "0",
            "vat_rate": "5",
        }
    ])
    total_net, total_vat, total_gross = InvoiceTotalsCalculator.calculate_totals(items)

    assert total_net == Decimal("6857.14")
    assert total_vat == Decimal("342.86")
    assert total_gross == Decimal("7200.00")
