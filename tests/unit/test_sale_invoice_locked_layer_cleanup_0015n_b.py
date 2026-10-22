"""GWO-0015N-B: payable/VAT layer cleanup + tight KSeF mask."""
from __future__ import annotations

from decimal import Decimal

from app.services.sale_invoice_locked_poc import (
    _KSEF_LABEL_RECT,
    _KSEF_LINE_Y_PX,
    _QR_MASK_RECT,
    build_fixture,
    render_locked_invoice,
)


def test_payable_dynamic_is_amount_only() -> None:
    bound = render_locked_invoice(build_fixture(1, remaining=Decimal("105")))
    due = bound.html.split('data-slot="amount_due"')[1].split("data-slot=")[0]
    assert "Do zapłaty" not in due
    assert "border:none" in due
    assert 'data-visual-text="amount_due"' in due
    assert "PLN" in due


def test_vat_title_not_emitted_dynamically_and_items_capped() -> None:
    bound = render_locked_invoice(build_fixture(1, remaining=Decimal("105")))
    assert "Podsumowanie VAT" not in bound.html
    assert 'data-dynamic-vat-values="1"' in bound.html
    vat = bound.html.split('data-slot="vat_summary"')[1].split("data-slot=")[0]
    assert "<thead>" not in vat
    assert "5%" in vat
    assert 'data-slot="items"' in bound.html


def test_ksef_mask_rects_below_separator() -> None:
    assert _KSEF_LABEL_RECT[1] > _KSEF_LINE_Y_PX
    assert _QR_MASK_RECT[1] > _KSEF_LINE_Y_PX
    bound = render_locked_invoice(build_fixture(10, remaining=Decimal("400")))
    first = bound.html.split('data-page="1"')[1].split('data-page="2"')[0]
    assert 'data-slot="ksef_label_mask"' in first
    assert 'data-slot="ksef_qr_mask"' in first
