from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.core.amount_formatting import EXCEL_NUMBER_FORMAT, EXCEL_PLN_NUMBER_FORMAT
from scripts.export_invoices_xlsx import build_workbook


def _make_item() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        sort_order=1,
        name="Pozycja",
        quantity="1",
        unit="szt.",
        unit_price_net="100.00",
        net_amount="100.00",
        vat_rate="23",
        vat_amount="23.00",
        gross_amount="123.00",
    )


def _make_invoice(currency: str, total_gross: str) -> SimpleNamespace:
    now = datetime(2026, 4, 1, 10, 0, 0)
    return SimpleNamespace(
        id=uuid4(),
        direction="sale",
        status="issued",
        payment_status="unpaid",
        issue_date=date(2026, 4, 1),
        number_local=f"FV/{currency}",
        seller_snapshot_json={"name": "Sprzedawca", "nip": "123", "street": "A", "building_no": "1"},
        buyer_snapshot_json={"name": "Nabywca", "nip": "456", "street": "B", "building_no": "2"},
        sale_date=date(2026, 4, 1),
        due_date=date(2026, 4, 15),
        currency=currency,
        totals_json={"total_net": "100.00", "total_vat": "23.00", "total_gross": total_gross},
        ksef_reference_number=None,
        created_at=now,
        items=[_make_item()],
    )


def test_build_workbook_applies_currency_conditional_number_formats() -> None:
    inv_pln = _make_invoice("PLN", "123.00")
    inv_eur = _make_invoice("EUR", "223.00")

    wb, errors, _ = build_workbook([inv_pln, inv_eur], payment_map={})

    assert errors == []

    ws_inv = wb["invoices"]
    ws_items = wb["invoice_items"]

    # invoices.total_gross column index = 19
    pln_gross = ws_inv.cell(row=2, column=19)
    eur_gross = ws_inv.cell(row=3, column=19)
    assert isinstance(pln_gross.value, float)
    assert isinstance(eur_gross.value, float)
    assert pln_gross.number_format == EXCEL_PLN_NUMBER_FORMAT
    assert eur_gross.number_format == EXCEL_NUMBER_FORMAT

    # invoice_items.gross_amount column index = 12
    pln_item_gross = ws_items.cell(row=2, column=12)
    eur_item_gross = ws_items.cell(row=3, column=12)
    assert isinstance(pln_item_gross.value, float)
    assert isinstance(eur_item_gross.value, float)
    assert pln_item_gross.number_format == EXCEL_PLN_NUMBER_FORMAT
    assert eur_item_gross.number_format == EXCEL_NUMBER_FORMAT
