"""Testy HTML/PDF faktury — układ, rachunek bankowy, formatowanie."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from app.schemas.invoice import InvoiceItemResponse, InvoiceResponse
from app.services.pdf_service import (
    render_invoice_html,
    resolve_seller_bank_account_for_render,
)

VALID_BANK = "12345678901234567890123456"
VALID_BANK_DISPLAY = "12 3456 7890 1234 5678 9012 3456"


def _sample_invoice(
    *,
    items: list[InvoiceItemResponse] | None = None,
    direction: str = "sale",
    seller_snapshot: dict | None = None,
) -> InvoiceResponse:
    now = datetime(2026, 5, 22, 12, 0, 0)
    default_items = [
        InvoiceItemResponse(
            id=uuid4(),
            name="Książka",
            quantity=Decimal("60"),
            unit="szt.",
            unit_price_net=Decimal("114.29"),
            vat_rate=Decimal("5"),
            net_total=Decimal("6857.14"),
            vat_total=Decimal("342.86"),
            gross_total=Decimal("7200.00"),
            sort_order=1,
        ),
    ]
    return InvoiceResponse(
        id=uuid4(),
        status="ready_for_submission",
        number_local="FV/1/2026",
        issue_date=date(2026, 5, 22),
        sale_date=date(2026, 5, 22),
        due_date=date(2026, 6, 5),
        payment_method="transfer",
        currency="PLN",
        seller_snapshot=seller_snapshot
        or {
            "name": "Ikona",
            "nip": "9670402857",
            "address": "ul. Kossaka 72",
            "city": "85-307 Bydgoszcz",
        },
        buyer_snapshot={
            "name": "Nabywca",
            "nip": "1234567890",
            "address": "ul. Testowa 1",
            "city": "00-001 Warszawa",
        },
        items=items or default_items,
        total_net=Decimal("6857.14"),
        total_vat=Decimal("342.86"),
        total_gross=Decimal("7200.00"),
        payment_status="unpaid",
        direction=direction,
        created_at=now,
        updated_at=now,
    )


def test_html_includes_formatted_bank_account() -> None:
    html = render_invoice_html(_sample_invoice(), seller_bank_account=VALID_BANK)
    assert f"Rachunek bankowy: {VALID_BANK_DISPLAY}" in html


def test_html_omits_bank_account_when_missing() -> None:
    html = render_invoice_html(_sample_invoice(), seller_bank_account=None)
    assert "Rachunek bankowy:" not in html


def test_purchase_omits_company_bank_even_when_configured() -> None:
    invoice = _sample_invoice(direction="purchase")
    bank = resolve_seller_bank_account_for_render(
        invoice,
        company_bank_account=VALID_BANK,
    )
    assert bank is None
    html = render_invoice_html(invoice, seller_bank_account=bank)
    assert "Rachunek bankowy:" not in html


def test_purchase_shows_seller_bank_from_snapshot() -> None:
    invoice = _sample_invoice(
        direction="purchase",
        seller_snapshot={
            "name": "Dostawca SA",
            "nip": "1112223344",
            "address": "ul. Dostawcza 1",
            "city": "00-002 Warszawa",
            "bank_account": VALID_BANK,
        },
    )
    bank = resolve_seller_bank_account_for_render(
        invoice,
        company_bank_account=VALID_BANK,
    )
    assert bank == VALID_BANK
    html = render_invoice_html(invoice, seller_bank_account=bank)
    assert f"Rachunek bankowy: {VALID_BANK_DISPLAY}" in html


def test_sale_uses_company_bank_account() -> None:
    invoice = _sample_invoice(direction="sale")
    bank = resolve_seller_bank_account_for_render(
        invoice,
        company_bank_account=VALID_BANK,
    )
    assert bank == VALID_BANK
    html = render_invoice_html(invoice, seller_bank_account=bank)
    assert f"Rachunek bankowy: {VALID_BANK_DISPLAY}" in html


def test_html_quantity_without_decimals() -> None:
    html = render_invoice_html(_sample_invoice())
    assert ">60<" in html
    assert ">60.00<" not in html


def test_html_vat_rate_as_integer_percent() -> None:
    html = render_invoice_html(_sample_invoice())
    assert ">5%<" in html
    assert ">5.00%<" not in html


def test_html_gross_unit_price_column() -> None:
    html = render_invoice_html(_sample_invoice())
    assert "Cena brutto" in html
    assert ">120.00<" in html


def test_html_net_mode_gross_unit_price_from_net_and_vat() -> None:
    item = InvoiceItemResponse(
        id=uuid4(),
        name="Towar",
        quantity=Decimal("2"),
        unit="szt.",
        unit_price_net=Decimal("100.00"),
        vat_rate=Decimal("23"),
        net_total=Decimal("200.00"),
        vat_total=Decimal("46.00"),
        gross_total=Decimal("246.00"),
        sort_order=1,
    )
    html = render_invoice_html(_sample_invoice(items=[item]))
    assert ">123.00<" in html


def test_html_forces_light_paper_against_dark_color_scheme() -> None:
    """Podgląd/PDF nie mogą dziedziczyć ciemnego motywu — biała kartka + ciemny tekst."""
    html = render_invoice_html(_sample_invoice())

    assert "color-scheme: light" in html
    assert "html {" in html or "html {" in html.replace("  ", " ")
    assert "background: #ffffff" in html
    assert "color: #111111" in html

    # Cały dokument (html/body), nie tylko sekcja płatności.
    assert "html {\n    color-scheme: light;\n    background: #ffffff;\n  }" in html
    assert "body {\n    font-family: -apple-system, Arial, sans-serif;\n    font-size: 13px;\n    color: #111111;\n    background: #ffffff;" in html

    # Komórki tabeli i podsumowanie też mają jawny ciemny tekst na jasnym tle.
    assert "th, td {" in html
    assert "color: #111111; background: #ffffff;" in html
    assert ".totals {" in html
    assert ".totals .total-gross {" in html
    assert "color: #111111;" in html

    # Druk / PDF zachowuje jasną kartkę.
    assert "@media print" in html
    assert "html, body {" in html
    assert "background: #ffffff !important;" in html
    assert "color: #111111 !important;" in html
    assert "print-color-adjust: exact;" in html

    # Sekcja płatności nadal czytelna (regresja istniejącego zachowania).
    assert ".payment-box {" in html
    assert "background: #fafafa;" in html
    assert "Płatność" in html
