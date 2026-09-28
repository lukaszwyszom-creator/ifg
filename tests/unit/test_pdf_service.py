"""Testy HTML/PDF faktury — modern A4 template, bank, formatowanie, escape."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from app.schemas.invoice import InvoiceItemResponse, InvoiceResponse
from app.services.pdf_service import (
    render_invoice_html,
    render_invoice_pdf,
    resolve_seller_bank_account_for_render,
)

VALID_BANK = "12345678901234567890123456"
VALID_BANK_DISPLAY = "12 3456 7890 1234 5678 9012 3456"


def _item(
    *,
    name: str = "Książka",
    quantity: str = "60",
    unit_price_net: str = "114.29",
    vat_rate: str = "5",
    net_total: str = "6857.14",
    vat_total: str = "342.86",
    gross_total: str = "7200.00",
    sort_order: int = 1,
    isbn: str | None = None,
) -> InvoiceItemResponse:
    return InvoiceItemResponse(
        id=uuid4(),
        name=name,
        quantity=Decimal(quantity),
        unit="szt.",
        unit_price_net=Decimal(unit_price_net),
        vat_rate=Decimal(vat_rate),
        net_total=Decimal(net_total),
        vat_total=Decimal(vat_total),
        gross_total=Decimal(gross_total),
        sort_order=sort_order,
        isbn=isbn,
    )


def _sample_invoice(
    *,
    items: list[InvoiceItemResponse] | None = None,
    direction: str = "sale",
    seller_snapshot: dict | None = None,
    buyer_snapshot: dict | None = None,
    invoice_type: str = "VAT",
    correction_reason: str | None = None,
    number_local: str = "FV/1/2026",
    status: str = "ready_for_submission",
) -> InvoiceResponse:
    now = datetime(2026, 5, 22, 12, 0, 0)
    default_items = [_item()]
    resolved_items = items or default_items
    total_net = sum((i.net_total for i in resolved_items), Decimal("0"))
    total_vat = sum((i.vat_total for i in resolved_items), Decimal("0"))
    total_gross = sum((i.gross_total for i in resolved_items), Decimal("0"))
    return InvoiceResponse(
        id=uuid4(),
        status=status,
        number_local=number_local,
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
        buyer_snapshot=buyer_snapshot
        or {
            "name": "Nabywca",
            "nip": "1234567890",
            "address": "ul. Testowa 1",
            "city": "00-001 Warszawa",
        },
        items=resolved_items,
        total_net=total_net,
        total_vat=total_vat,
        total_gross=total_gross,
        payment_status="unpaid",
        invoice_type=invoice_type,
        correction_reason=correction_reason,
        direction=direction,
        created_at=now,
        updated_at=now,
    )


def test_html_basic_modern_invoice() -> None:
    html = render_invoice_html(_sample_invoice(), seller_bank_account=VALID_BANK)
    assert "FAKTURA VAT" in html
    assert "FV/1/2026" in html
    assert "Ikona" in html
    assert "Nabywca" in html
    assert "Do zapłaty" in html
    assert "7200.00 PLN" in html


def test_html_hides_ifg_status_badge() -> None:
    html = render_invoice_html(_sample_invoice(status="ready_for_submission"))
    assert "Gotowa do wysyłki" not in html
    assert "badge-ready_for_submission" not in html
    assert "badge-accepted" not in html
    assert "Status:" not in html


def test_html_line_numbers() -> None:
    items = [
        _item(name="A", quantity="1", unit_price_net="10", vat_rate="23",
              net_total="10.00", vat_total="2.30", gross_total="12.30", sort_order=1),
        _item(name="B", quantity="2", unit_price_net="20", vat_rate="23",
              net_total="40.00", vat_total="9.20", gross_total="49.20", sort_order=2),
    ]
    html = render_invoice_html(_sample_invoice(items=items))
    assert '<td class="num lp">1</td>' in html
    assert '<td class="num lp">2</td>' in html


def test_html_seller_buyer_present() -> None:
    html = render_invoice_html(_sample_invoice())
    assert "Sprzedawca" in html
    assert "Nabywca" in html
    assert "NIP: 9670402857" in html
    assert "NIP: 1234567890" in html


def test_html_partial_address_no_none_litter() -> None:
    html = render_invoice_html(
        _sample_invoice(
            buyer_snapshot={
                "name": "Wieś Sp. z o.o.",
                "nip": "5250000000",
                "street": None,
                "building_no": "10",
                "postal_code": "98-331",
                "city": "Prusicko",
                "address": None,
            }
        )
    )
    assert "None" not in html
    assert "null" not in html
    assert "Prusicko 10" in html
    assert "98-331 Prusicko" in html
    assert "<p></p>" not in html


def test_html_structured_address_without_freeform() -> None:
    html = render_invoice_html(
        _sample_invoice(
            seller_snapshot={
                "name": "Firma",
                "nip": "1111111111",
                "street": "ul. Prosta",
                "building_no": "18",
                "apartment_no": "2",
                "postal_code": "00-105",
                "city": "Warszawa",
            }
        )
    )
    assert "ul. Prosta 18 m. 2" in html
    assert "00-105 Warszawa" in html


def test_html_main_totals() -> None:
    html = render_invoice_html(_sample_invoice())
    assert "6857.14 PLN" in html
    assert "342.86 PLN" in html
    assert "7200.00 PLN" in html


def test_html_due_to_pay_block() -> None:
    html = render_invoice_html(_sample_invoice(), seller_bank_account=VALID_BANK)
    assert 'class="due-box"' in html
    assert "Do zapłaty" in html
    assert f"Rachunek bankowy" in html
    assert VALID_BANK_DISPLAY in html
    assert "2026-06-05" in html
    assert "Przelew" in html


def _due_amount_from_html(html: str) -> str:
    marker = '<div class="due-amount">'
    start = html.index(marker) + len(marker)
    end = html.index("</div>", start)
    return html[start:end].strip()


def test_do_zaplaty_unpaid_remaining_equals_gross() -> None:
    invoice = _sample_invoice()
    invoice.total_gross = Decimal("1000.00")
    invoice.remaining_amount = Decimal("1000.00")
    html = render_invoice_html(invoice)
    assert _due_amount_from_html(html) == "1000.00 PLN"


def test_do_zaplaty_partially_paid_uses_remaining() -> None:
    invoice = _sample_invoice()
    invoice.total_gross = Decimal("1000.00")
    invoice.remaining_amount = Decimal("400.00")
    html = render_invoice_html(invoice)
    assert _due_amount_from_html(html) == "400.00 PLN"
    # Brutto totals still show full gross; due box must not reuse it blindly.
    assert "1000.00 PLN" in html
    assert _due_amount_from_html(html) != "1000.00 PLN"


def test_do_zaplaty_paid_remaining_zero() -> None:
    invoice = _sample_invoice()
    invoice.total_gross = Decimal("1000.00")
    invoice.remaining_amount = Decimal("0.00")
    html = render_invoice_html(invoice)
    assert _due_amount_from_html(html) == "0.00 PLN"


def test_do_zaplaty_fallback_when_remaining_none() -> None:
    invoice = _sample_invoice()
    invoice.total_gross = Decimal("1000.00")
    invoice.remaining_amount = None
    html = render_invoice_html(invoice)
    assert _due_amount_from_html(html) == "1000.00 PLN"


def test_html_vat_summary_by_rate() -> None:
    items = [
        _item(name="A", quantity="1", unit_price_net="100", vat_rate="23",
              net_total="100.00", vat_total="23.00", gross_total="123.00", sort_order=1),
        _item(name="B", quantity="1", unit_price_net="100", vat_rate="5",
              net_total="100.00", vat_total="5.00", gross_total="105.00", sort_order=2),
        _item(name="C", quantity="1", unit_price_net="50", vat_rate="0",
              net_total="50.00", vat_total="0.00", gross_total="50.00", sort_order=3),
    ]
    html = render_invoice_html(_sample_invoice(items=items))
    assert "Stawka VAT" in html
    assert ">23%<" in html
    assert ">5%<" in html
    assert ">0%<" in html


def test_html_correction_reason_only_for_correction() -> None:
    plain = render_invoice_html(
        _sample_invoice(invoice_type="VAT", correction_reason="Nie powinno się pokazać")
    )
    assert "Przyczyna korekty" not in plain
    assert "Nie powinno się pokazać" not in plain

    kor = render_invoice_html(
        _sample_invoice(
            invoice_type="KOR",
            correction_reason='Błąd stawki <script>alert(1)</script>',
        )
    )
    assert "FAKTURA KORYGUJĄCA" in kor
    assert "Przyczyna korekty" in kor
    assert "Błąd stawki" in kor
    assert "<script>" not in kor
    assert "&lt;script&gt;" in kor


def test_html_a4_and_multipage_css() -> None:
    html = render_invoice_html(_sample_invoice())
    assert "@page" in html
    assert "size: A4" in html
    assert "display: table-header-group" in html
    assert "break-inside: avoid" in html
    assert "page-break-inside: avoid" in html
    assert "@media print" in html
    assert "print-color-adjust: exact" in html


def test_html_no_unit_gross_price_column() -> None:
    html = render_invoice_html(_sample_invoice())
    assert "Cena brutto" not in html
    assert "Cena netto" in html
    assert "VAT kwota" in html


def test_html_escapes_names_and_addresses() -> None:
    html = render_invoice_html(
        _sample_invoice(
            seller_snapshot={
                "name": 'Firma <b>X</b> & "Y"',
                "nip": "111",
                "address": '<img src=x onerror=alert(1)>',
                "city": "00-001 Warszawa",
            },
            items=[
                _item(
                    name='Pozycja <script>evil()</script>',
                    quantity="1",
                    unit_price_net="10",
                    vat_rate="23",
                    net_total="10.00",
                    vat_total="2.30",
                    gross_total="12.30",
                )
            ],
        )
    )
    assert "<script>" not in html
    assert "<img" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;b&gt;" in html
    assert "&amp;" in html


def test_html_includes_formatted_bank_account() -> None:
    html = render_invoice_html(_sample_invoice(), seller_bank_account=VALID_BANK)
    assert f"Rachunek bankowy" in html
    assert VALID_BANK_DISPLAY in html


def test_html_omits_bank_account_when_missing() -> None:
    html = render_invoice_html(_sample_invoice(), seller_bank_account=None)
    assert "Rachunek bankowy" not in html


def test_purchase_omits_company_bank_even_when_configured() -> None:
    invoice = _sample_invoice(direction="purchase")
    bank = resolve_seller_bank_account_for_render(
        invoice,
        company_bank_account=VALID_BANK,
    )
    assert bank is None
    html = render_invoice_html(invoice, seller_bank_account=bank)
    assert "Rachunek bankowy" not in html


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
    assert VALID_BANK_DISPLAY in html


def test_sale_uses_company_bank_account() -> None:
    invoice = _sample_invoice(direction="sale")
    bank = resolve_seller_bank_account_for_render(
        invoice,
        company_bank_account=VALID_BANK,
    )
    assert bank == VALID_BANK
    html = render_invoice_html(invoice, seller_bank_account=bank)
    assert VALID_BANK_DISPLAY in html


def test_html_quantity_without_decimals() -> None:
    html = render_invoice_html(_sample_invoice())
    assert ">60<" in html
    assert ">60.00<" not in html


def test_html_vat_rate_as_integer_percent() -> None:
    html = render_invoice_html(_sample_invoice())
    assert ">5%<" in html
    assert ">5.00%<" not in html


def test_html_forces_light_paper_against_dark_color_scheme() -> None:
    html = render_invoice_html(_sample_invoice())
    assert "color-scheme: light" in html
    assert "background: #ffffff" in html
    assert "color: #111111" in html
    assert "@media print" in html
    assert "background: #ffffff !important;" in html
    assert "print-color-adjust: exact;" in html
    assert 'class="due-box"' in html


def test_html_many_items_still_has_repeated_thead_css() -> None:
    items = [
        _item(
            name=f"Pozycja {i} " + ("długa " * 8),
            quantity="1",
            unit_price_net="10",
            vat_rate="23" if i % 2 == 0 else "8",
            net_total="10.00",
            vat_total="2.30" if i % 2 == 0 else "0.80",
            gross_total="12.30" if i % 2 == 0 else "10.80",
            sort_order=i,
        )
        for i in range(1, 55)
    ]
    html = render_invoice_html(_sample_invoice(items=items))
    assert '<td class="num lp">1</td>' in html
    assert '<td class="num lp">54</td>' in html
    assert "display: table-header-group" in html
    assert "break-inside: avoid" in html


def test_preview_and_pdf_share_same_template() -> None:
    invoice = _sample_invoice()
    html = render_invoice_html(invoice, seller_bank_account=VALID_BANK)
    assert "FAKTURA VAT" in html
    assert "@page" in html
    pdf = render_invoice_pdf(invoice, seller_bank_account=VALID_BANK)
    assert pdf.startswith(b"%PDF")
    assert b"%%EOF" in pdf[-1024:]


def test_single_item_invoice_fits_one_pdf_page() -> None:
    """WeasyPrint must keep a short invoice on one A4 page (no grid blow-up)."""
    from weasyprint import HTML

    html = render_invoice_html(_sample_invoice(), seller_bank_account=VALID_BANK)
    pages = HTML(string=html).render().pages
    assert len(pages) == 1


def test_vat_summary_renders_distinguishable_decimal_rates_only() -> None:
    """InvoiceItemResponse.vat_rate is Decimal — 0% is rendered; zw./np. are not distinguishable."""
    items = [
        _item(name="Zero", quantity="1", unit_price_net="100", vat_rate="0",
              net_total="100.00", vat_total="0.00", gross_total="100.00", sort_order=1),
    ]
    html = render_invoice_html(_sample_invoice(items=items))
    assert ">0%<" in html
    assert ">zw.<" not in html
    assert ">zw<" not in html
    assert ">np.<" not in html
    assert ">np<" not in html
