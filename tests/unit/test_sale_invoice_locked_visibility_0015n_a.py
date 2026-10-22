"""GWO-0015N-A: visual paint assertions for summary/payable + KSeF mask."""
from __future__ import annotations

from decimal import Decimal

from app.services.sale_invoice_locked_poc import build_fixture, render_locked_invoice


def test_single_page_summary_markup_not_clipped() -> None:
    bound = render_locked_invoice(build_fixture(1, remaining=Decimal("105")))
    assert bound.plan.page_count == 1
    assert 'data-slot="vat_summary"' in bound.html
    assert 'data-slot="amount_due"' in bound.html
    vat_block = bound.html.split('data-slot="vat_summary"')[1].split("data-slot=")[0]
    assert "overflow:hidden" not in vat_block
    assert "overflow:visible" in vat_block
    assert "z-index:45" in bound.html
    # 0015N-B: VAT values only (no dynamic thead); payable amount only
    vat = bound.html.split('data-slot="vat_summary"')[1].split("data-slot=")[0]
    assert "5%" in vat
    assert "<thead>" not in vat
    due = bound.html.split('data-slot="amount_due"')[1].split("data-slot=")[0]
    assert "Do zapłaty" not in due
    assert "PLN" in due


def test_multipage_first_has_ksef_mask_not_on_final() -> None:
    bound = render_locked_invoice(build_fixture(10, remaining=Decimal("400")))
    assert bound.plan.page_count == 2
    first = bound.html.split('data-page="1"')[1].split('data-page="2"')[0]
    last = bound.html.split('data-page="2"')[1]
    assert 'data-slot="ksef_label_mask"' in first
    assert 'data-slot="ksef_qr_mask"' in first
    assert 'data-slot="ksef_qr"' in last
    assert 'data-slot="ksef_label_mask"' not in last


def test_distribution_unchanged_vs_0015n() -> None:
    b10 = render_locked_invoice(build_fixture(10, remaining=Decimal("400")))
    assert [r.lp for r in b10.plan.pages[0].rows] == list(range(1, 9))
    assert [r.lp for r in b10.plan.pages[1].rows] == [9, 10]
    b50 = render_locked_invoice(build_fixture(50, remaining=None))
    assert [r.lp for r in b50.plan.pages[0].rows] == list(range(1, 11))
    assert [r.lp for r in b50.plan.pages[-1].rows] == list(range(42, 51))
