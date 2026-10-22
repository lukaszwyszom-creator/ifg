"""GWO-0015O-A: dynamic document title + remaining_amount semantics."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from app.schemas.invoice import InvoiceItemResponse, InvoiceResponse
from app.services.pdf_service import render_invoice_html
from app.services.sale_invoice_locked_bind import adapt_invoice_response_to_locked


def _item() -> InvoiceItemResponse:
    return InvoiceItemResponse(
        id=uuid4(),
        name="Katechizm",
        quantity=Decimal("1"),
        unit="szt.",
        unit_price_net=Decimal("1000.00"),
        vat_rate=Decimal("5"),
        net_total=Decimal("1000.00"),
        vat_total=Decimal("50.00"),
        gross_total=Decimal("1050.00"),
        sort_order=1,
    )


def _inv(
    *,
    invoice_type: str = "VAT",
    remaining: Decimal | None,
    total_gross: Decimal = Decimal("1050.00"),
) -> InvoiceResponse:
    return InvoiceResponse(
        id=uuid4(),
        status="ready_for_submission",
        number_local="FV/26/0010",
        issue_date=date(2026, 10, 2),
        sale_date=date(2026, 10, 2),
        due_date=date(2026, 10, 16),
        payment_method="transfer",
        currency="PLN",
        seller_snapshot={"name": "Ikona", "nip": "9670402857", "address": "Pelplin"},
        buyer_snapshot={"name": "Nabywca", "nip": "5250000000", "address": "Warszawa"},
        items=[_item()],
        total_net=Decimal("1000.00"),
        total_vat=Decimal("50.00"),
        total_gross=total_gross,
        payment_status="unpaid",
        invoice_type=invoice_type,
        direction="sale",
        created_at=datetime(2026, 10, 2),
        updated_at=datetime(2026, 10, 2),
        remaining_amount=remaining,
        correction_reason="korekta" if invoice_type == "KOR" else None,
    )


def test_normal_title_is_faktura_vat() -> None:
    html = render_invoice_html(_inv(remaining=None, total_gross=Decimal("1050.00")))
    title = html.split('data-visual-text="document_title"')[1].split("</div>")[0]
    assert "FAKTURA VAT" in title
    assert "FAKTURA KORYGUJĄCA" not in title
    assert 'data-slot="document_title_mask"' in html
    assert 'data-slot="document_title"' in html


def test_kor_title_is_faktura_korygujaca() -> None:
    html = render_invoice_html(
        _inv(invoice_type="KOR", remaining=None, total_gross=Decimal("1050.00"))
    )
    title = html.split('data-visual-text="document_title"')[1].split("</div>")[0]
    assert "FAKTURA KORYGUJĄCA" in title
    assert "FAKTURA VAT" not in title
    assert 'data-slot="document_title"' in html
    assert 'data-slot="document_title_mask"' in html


def test_remaining_explicit_400_not_gross() -> None:
    """0015O REAL-10 case: remaining_amount=400 with gross 1050 → DO ZAPŁATY 400,00."""
    inv = _inv(remaining=Decimal("400.00"), total_gross=Decimal("1050.00"))
    model = adapt_invoice_response_to_locked(inv)
    assert model.remaining_amount == Decimal("400.00")
    assert model.total_gross == Decimal("1050.00")
    html = render_invoice_html(inv)
    due = html.split('data-visual-text="amount_due"')[1].split("</div>")[0]
    assert "400,00 PLN" in due
    assert "1 050,00 PLN" not in due


def test_remaining_fallback_to_total_gross() -> None:
    inv = _inv(remaining=None, total_gross=Decimal("1050.00"))
    model = adapt_invoice_response_to_locked(inv)
    assert model.remaining_amount is None
    assert model.total_gross == Decimal("1050.00")
    html = render_invoice_html(inv)
    due = html.split('data-visual-text="amount_due"')[1].split("</div>")[0]
    assert "1 050,00 PLN" in due
