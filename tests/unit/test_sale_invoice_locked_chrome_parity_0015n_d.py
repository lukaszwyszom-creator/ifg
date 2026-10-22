"""GWO-0015N-D: continuation final uses underlay-cropped chrome + shared values overlay."""
from __future__ import annotations

from decimal import Decimal

from app.services.invoice_items_paginator import PageKind
from app.services.sale_invoice_locked_poc import build_fixture, render_locked_invoice


def test_continuation_uses_underlay_chrome_crop() -> None:
    bound = render_locked_invoice(build_fixture(10, remaining=Decimal("400")))
    assert bound.plan.pages[-1].page_kind == PageKind.FINAL_CONTINUATION
    last = bound.html.split('data-page="2"')[1]
    assert 'data-slot="summary_payable_chrome"' in last
    assert 'data-summary-chrome="underlay-crop"' in last
    assert 'data-dynamic-vat-values="1"' in last
    # No hand-painted title/headers in HTML (pixels come from underlay crop)
    assert "PODSUMOWANIE VAT" not in last
    assert "STAWKA VAT" not in last
    assert "DO ZAPŁATY" not in last


def test_single_page_unchanged_underlay_mode() -> None:
    bound = render_locked_invoice(build_fixture(1, remaining=Decimal("105")))
    assert 'data-slot="summary_payable_chrome"' not in bound.html
    vat = bound.html.split('data-slot="vat_summary"')[1].split("data-slot=")[0]
    due = bound.html.split('data-slot="amount_due"')[1].split("data-slot=")[0]
    assert 'data-summary-chrome="underlay"' in vat
    assert "<thead>" not in vat
    assert "DO ZAPŁATY" not in due


def test_distribution_frozen() -> None:
    b10 = render_locked_invoice(build_fixture(10, remaining=Decimal("400")))
    assert [r.lp for r in b10.plan.pages[0].rows] == list(range(1, 9))
    assert [r.lp for r in b10.plan.pages[1].rows] == [9, 10]
    b50 = render_locked_invoice(build_fixture(50, remaining=None))
    assert [r.lp for r in b50.plan.pages[0].rows] == list(range(1, 11))
    assert [r.lp for r in b50.plan.pages[-1].rows] == list(range(42, 51))
