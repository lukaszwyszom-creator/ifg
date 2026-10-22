"""GWO-0015O: production bind of locked sale renderer via InvoiceResponse."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from app.schemas.invoice import InvoiceItemResponse, InvoiceResponse
from app.services.invoice_items_paginator import PageKind
from app.services.pdf_service import render_invoice_html, render_invoice_pdf
from app.services.sale_invoice_locked_bind import (
    adapt_invoice_response_to_locked,
    render_sale_locked_bind,
)


def _item(
    *,
    name: str,
    quantity: str = "1",
    unit: str = "szt.",
    unit_price_net: str = "100.00",
    vat_rate: str = "5",
    net_total: str = "100.00",
    vat_total: str = "5.00",
    gross_total: str = "105.00",
    sort_order: int = 1,
    isbn: str | None = None,
) -> InvoiceItemResponse:
    return InvoiceItemResponse(
        id=uuid4(),
        name=name,
        quantity=Decimal(quantity),
        unit=unit,
        unit_price_net=Decimal(unit_price_net),
        vat_rate=Decimal(vat_rate),
        net_total=Decimal(net_total),
        vat_total=Decimal(vat_total),
        gross_total=Decimal(gross_total),
        sort_order=sort_order,
        isbn=isbn,
    )


def _realistic_invoice(
    *,
    n_items: int = 1,
    remaining: Decimal | None = Decimal("105.00"),
    ksef_ref: str | None = None,
) -> InvoiceResponse:
    items = []
    for i in range(1, n_items + 1):
        if i % 7 == 0:
            name = (
                f"Mszał Rzymski — tom {i}: dłuższy opis liturgiczny z polskimi znakami "
                f"(ĆćĘęŁłŃńÓóŚśŹźŻż) wymagający zawinięcia wiersza"
            )
            isbn = f"978-83-{i:07d}"
            qty = "2"
            net = Decimal("240.00")
            vat = Decimal("12.00")
            gross = Decimal("252.00")
            unit_net = Decimal("120.00")
        elif i % 5 == 0:
            name = f"Brewiarz kapłański — wydanie jubileuszowe {i}"
            isbn = None
            qty = "1"
            net = Decimal("180.00")
            vat = Decimal("9.00")
            gross = Decimal("189.00")
            unit_net = Decimal("180.00")
        else:
            name = f"Katechizm dla dorosłych — pozycja {i}"
            isbn = f"978-{i:010d}" if i % 3 == 0 else None
            qty = "1"
            net = Decimal("100.00")
            vat = Decimal("5.00")
            gross = Decimal("105.00")
            unit_net = Decimal("100.00")
        items.append(
            _item(
                name=name,
                quantity=qty,
                unit_price_net=str(unit_net),
                net_total=str(net),
                vat_total=str(vat),
                gross_total=str(gross),
                sort_order=i,
                isbn=isbn,
            )
        )
    total_net = sum((it.net_total for it in items), Decimal("0"))
    total_vat = sum((it.vat_total for it in items), Decimal("0"))
    total_gross = sum((it.gross_total for it in items), Decimal("0"))
    if remaining is None:
        rem = None
    elif remaining == 0:
        rem = Decimal("0")
    elif n_items == 1:
        rem = remaining
    else:
        rem = remaining
    return InvoiceResponse(
        id=uuid4(),
        status="ready_for_submission",
        number_local=f"FV/26/{n_items:04d}",
        issue_date=date(2026, 10, 2),
        sale_date=date(2026, 10, 2),
        due_date=date(2026, 10, 16),
        payment_method="transfer",
        currency="PLN",
        seller_snapshot={
            "name": "Wydawnictwo Ikona Sp. z o.o.",
            "nip": "9670402857",
            "address": "ul. Dominika 11",
            "postal_code": "83-130",
            "city": "Pelplin",
        },
        buyer_snapshot={
            "name": "Parafia pw. św. Jana Chrzciciela w Przykładowie",
            "nip": "5250000000",
            "street": "ul. Kościelna",
            "building_no": "3",
            "postal_code": "00-001",
            "city": "Warszawa",
        },
        items=items,
        total_net=total_net,
        total_vat=total_vat,
        total_gross=total_gross,
        payment_status="unpaid",
        invoice_type="VAT",
        direction="sale",
        created_at=datetime(2026, 10, 2, 12, 0, 0),
        updated_at=datetime(2026, 10, 2, 12, 0, 0),
        remaining_amount=rem,
        ksef_reference_number=ksef_ref,
    )


def test_one_item_single_page_bound() -> None:
    inv = _realistic_invoice(n_items=1, remaining=Decimal("105.00"))
    bound = render_sale_locked_bind(inv, seller_bank_account="12345678901234567890123456")
    assert bound.plan.page_count == 1
    assert bound.summary_count == 1
    assert bound.payable_count == 1
    assert 'data-invoice-template="sale-locked"' in bound.html
    assert 'data-ifg-bound="yes"' in bound.html
    assert "105,00 PLN" in bound.html
    assert "Katechizm" in bound.html


def test_remaining_zero_shows_zero() -> None:
    inv = _realistic_invoice(n_items=1, remaining=Decimal("0"))
    html = render_invoice_html(inv)
    assert "0,00 PLN" in html
    due = html.split('data-visual-text="amount_due"')[1].split("</div>")[0]
    assert "0,00 PLN" in due
    assert "105,00 PLN" not in due


def _short_items_invoice(n: int, *, remaining: Decimal | None) -> InvoiceResponse:
    """Pagination-reference fixture mirroring sale_invoice_locked_poc.build_fixture names."""
    items = []
    for i in range(1, n + 1):
        if i % 7 == 0:
            name = (
                f"Pozycja {i}: Kościoły Archidiecezji Częstochowskiej — "
                f"dłuższy opis towaru wymagający zawinięcia wiersza ({i})"
            )
            isbn = f"978-83-{i:07d}"
        elif i % 5 == 0:
            name = f"Pozycja {i}: Nazwa średniej długości produktu IFG"
            isbn = None
        else:
            name = f"Pozycja {i}"
            isbn = f"978-{i:010d}" if i % 3 == 0 else None
        items.append(_item(name=name, sort_order=i, isbn=isbn))
    total_gross = sum((it.gross_total for it in items), Decimal("0"))
    return InvoiceResponse(
        id=uuid4(),
        status="ready_for_submission",
        number_local=f"FV/26/{n:04d}",
        issue_date=date(2026, 10, 2),
        sale_date=date(2026, 10, 2),
        due_date=date(2026, 10, 16),
        payment_method="transfer",
        currency="PLN",
        seller_snapshot={"name": "Ikona", "nip": "9670402857", "address": "Pelplin"},
        buyer_snapshot={"name": "Nabywca", "nip": "5250000000", "address": "Warszawa"},
        items=items,
        total_net=sum((it.net_total for it in items), Decimal("0")),
        total_vat=sum((it.vat_total for it in items), Decimal("0")),
        total_gross=total_gross,
        payment_status="unpaid",
        invoice_type="VAT",
        direction="sale",
        created_at=datetime(2026, 10, 2),
        updated_at=datetime(2026, 10, 2),
        remaining_amount=remaining,
    )


def test_eight_items_one_page() -> None:
    # Uniform short rows (no ISBN / no wrap) fit FIRST_FINAL.
    items = [_item(name=f"Pozycja {i}", sort_order=i) for i in range(1, 9)]
    inv = InvoiceResponse(
        id=uuid4(),
        status="ready_for_submission",
        number_local="FV/26/0008",
        issue_date=date(2026, 10, 2),
        sale_date=date(2026, 10, 2),
        due_date=date(2026, 10, 16),
        payment_method="transfer",
        currency="PLN",
        seller_snapshot={"name": "Ikona", "nip": "9670402857", "address": "Pelplin"},
        buyer_snapshot={"name": "Nabywca", "nip": "5250000000", "address": "Warszawa"},
        items=items,
        total_net=Decimal("800"),
        total_vat=Decimal("40"),
        total_gross=Decimal("840"),
        payment_status="unpaid",
        invoice_type="VAT",
        direction="sale",
        created_at=datetime(2026, 10, 2),
        updated_at=datetime(2026, 10, 2),
        remaining_amount=Decimal("400"),
    )
    bound = render_sale_locked_bind(inv)
    assert bound.plan.page_count == 1
    assert [r.lp for r in bound.plan.pages[0].rows] == list(range(1, 9))


def test_nine_items_anti_orphan() -> None:
    bound = render_sale_locked_bind(_short_items_invoice(9, remaining=Decimal("400")))
    assert bound.plan.page_count == 2
    assert [r.lp for r in bound.plan.pages[0].rows] == list(range(1, 8))
    assert [r.lp for r in bound.plan.pages[1].rows] == [8, 9]
    assert bound.plan.pages[-1].page_kind == PageKind.FINAL_CONTINUATION


def test_ten_items_two_pages() -> None:
    bound = render_sale_locked_bind(_short_items_invoice(10, remaining=Decimal("400")))
    assert bound.plan.page_count == 2
    assert [r.lp for r in bound.plan.pages[0].rows] == list(range(1, 9))
    assert [r.lp for r in bound.plan.pages[1].rows] == [9, 10]


def test_fifty_items_multipage_no_loss() -> None:
    bound = render_sale_locked_bind(_short_items_invoice(50, remaining=None))
    assert bound.plan.page_count >= 3
    seen = [r.lp for p in bound.plan.pages for r in p.rows]
    assert seen == list(range(1, 51))
    assert len(seen) == len(set(seen))
    assert [r.lp for r in bound.plan.pages[0].rows] == list(range(1, 11))
    assert [r.lp for r in bound.plan.pages[-1].rows] == list(range(42, 51))


def test_long_description_no_row_split() -> None:
    inv = _realistic_invoice(n_items=7, remaining=Decimal("100"))
    bound = render_sale_locked_bind(inv)
    for page in bound.plan.pages:
        lps = [r.lp for r in page.rows]
        assert lps == list(range(lps[0], lps[0] + len(lps)))


def test_ksef_complete_real_qr() -> None:
    xml = b'<?xml version="1.0"?><Faktura>prod-bind-qr</Faktura>'
    inv = _realistic_invoice(n_items=1, remaining=Decimal("105"), ksef_ref="9670402857-20261002-TEST00000001-11")
    bound = render_sale_locked_bind(inv, ksef_xml_bytes=xml, ksef_environment="test")
    assert bound.qr_status == "ok"
    assert bound.qr_count == 1
    assert 'data-qr-status="ok"' in bound.html
    assert "data-qr-url=" in bound.html
    assert "<img" in bound.html.split('data-slot="ksef_qr"')[1].split("</div>")[0]


def test_ksef_incomplete_no_fake_qr() -> None:
    inv = _realistic_invoice(n_items=1, remaining=Decimal("105"), ksef_ref="9670402857-20261002-TEST00000001-11")
    bound = render_sale_locked_bind(inv, ksef_xml_bytes=None)
    assert bound.qr_status == "INCOMPLETE"
    assert bound.qr_count == 0
    qr = bound.html.split('data-slot="ksef_qr"')[1].split("</div>")[0]
    assert "<img" not in qr


def test_adapter_maps_polish_parties_and_bank() -> None:
    inv = _realistic_invoice(n_items=1)
    model = adapt_invoice_response_to_locked(
        inv, seller_bank_account="12345678901234567890123456"
    )
    assert "Pelplin" in model.seller_address
    assert "Kościelna" in model.buyer_address
    assert model.payment_method == "Przelew"
    assert "12 3456" in model.bank_account
    assert model.production_bound is True


def test_preview_pdf_same_locked_template() -> None:
    inv = _realistic_invoice(n_items=1)
    html = render_invoice_html(inv, seller_bank_account="12345678901234567890123456")
    pdf = render_invoice_pdf(inv, seller_bank_account="12345678901234567890123456")
    assert 'data-invoice-template="sale-locked"' in html
    assert pdf.startswith(b"%PDF")
