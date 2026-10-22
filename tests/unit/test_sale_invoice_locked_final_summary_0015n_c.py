"""GWO-0015N-C: continuation-final paints full summary chrome; first stays underlay-only."""
from __future__ import annotations

from decimal import Decimal

from app.services.invoice_items_paginator import PageKind
from app.services.sale_invoice_locked_poc import build_fixture, render_locked_invoice


def test_continuation_final_paints_summary_chrome() -> None:
    bound = render_locked_invoice(build_fixture(10, remaining=Decimal("400")))
    assert bound.plan.page_count == 2
    assert bound.plan.pages[-1].page_kind == PageKind.FINAL_CONTINUATION
    last = bound.html.split('data-page="2"')[1]
    # 0015N-D: chrome is underlay crop + shared values overlay (not hand-painted HTML)
    assert 'data-slot="summary_payable_chrome"' in last
    assert 'data-summary-chrome="underlay-crop"' in last
    assert 'data-dynamic-vat-values="1"' in last
    assert "PLN" in last
    first = bound.html.split('data-page="1"')[1].split('data-page="2"')[0]
    assert 'data-slot="vat_summary"' not in first


def test_single_page_keeps_underlay_only_summary() -> None:
    bound = render_locked_invoice(build_fixture(1, remaining=Decimal("105")))
    assert bound.plan.page_count == 1
    assert bound.plan.pages[0].page_kind == PageKind.FIRST
    vat = bound.html.split('data-slot="vat_summary"')[1].split("data-slot=")[0]
    due = bound.html.split('data-slot="amount_due"')[1].split("data-slot=")[0]
    assert 'data-summary-chrome="underlay"' in vat
    assert "<thead>" not in vat
    assert "DO ZAPŁATY" not in due
    assert "PLN" in due


def test_distribution_unchanged() -> None:
    b10 = render_locked_invoice(build_fixture(10, remaining=Decimal("400")))
    assert [r.lp for r in b10.plan.pages[0].rows] == list(range(1, 9))
    assert [r.lp for r in b10.plan.pages[1].rows] == [9, 10]
    b50 = render_locked_invoice(build_fixture(50, remaining=None))
    assert [r.lp for r in b50.plan.pages[0].rows] == list(range(1, 11))
    assert [r.lp for r in b50.plan.pages[-1].rows] == list(range(42, 51))
