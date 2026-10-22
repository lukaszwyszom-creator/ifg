"""Production bind: InvoiceResponse → locked underlay renderer (GWO-0015O).

Maps real IFG invoice schema into the locked-layout render model.
Does not redesign geometry. Does not touch purchase template.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.schemas.invoice import InvoiceItemResponse, InvoiceResponse
from app.services.bank_account import format_bank_account_display
from app.services.pdf_service import (
    _PAYMENT_METHOD_LABELS,
    _amount_due_for_display,
    _as_decimal,
    _document_title,
    _format_quantity,
    _format_vat_rate,
    _party_address_lines,
    _strip_display,
    _vat_summary_rows,
)
from app.services.sale_invoice_locked_poc import (
    LockedBindResult,
    PocInvoiceFixture,
    _money,
    render_locked_invoice,
)
from app.services.pdf_sale_elegant import _unit_price_gross


def _fmt_date(value: date | None) -> str:
    if value is None:
        return ""
    return value.strftime("%d.%m.%Y")


def _party_name(snapshot: dict | None) -> str:
    snap = snapshot or {}
    return _strip_display(snap.get("name")) or ""


def _party_nip(snapshot: dict | None) -> str:
    snap = snapshot or {}
    return _strip_display(snap.get("nip")) or ""


def _party_address(snapshot: dict | None) -> str:
    lines = _party_address_lines(snapshot)
    return ", ".join(lines)


def _payment_label(raw: str | None) -> str:
    key = _strip_display(raw) or ""
    return _PAYMENT_METHOD_LABELS.get(key, key) if key else ""


def _item_dict(item: InvoiceItemResponse, lp: int) -> dict[str, Any]:
    net = _as_decimal(item.net_total) or Decimal("0")
    vat = _as_decimal(item.vat_total) or Decimal("0")
    gross = _as_decimal(item.gross_total) or Decimal("0")
    unit_net = _as_decimal(item.unit_price_net) or Decimal("0")
    unit_gross = _unit_price_gross(item) or Decimal("0")
    rate = _as_decimal(item.vat_rate) or Decimal("0")
    return {
        "lp": lp,
        "name": item.name or "",
        "isbn": _strip_display(item.isbn) or None,
        "qty": _format_quantity(item.quantity),
        "unit": _strip_display(item.unit) or "",
        "cnet": _money(unit_net),
        "cbru": _money(unit_gross),
        "vat": _format_vat_rate(rate),
        "vnet": _money(net),
        "kvat": _money(vat),
        "vbru": _money(gross),
        "net": net.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "vat_amt": vat.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "gross": gross.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "vat_rate": rate,
    }


def adapt_invoice_response_to_locked(
    invoice: InvoiceResponse,
    *,
    seller_bank_account: str | None = None,
    ksef_xml_bytes: bytes | None = None,
    ksef_environment: str | None = None,
) -> PocInvoiceFixture:
    """Build locked render model from production InvoiceResponse."""
    ordered = sorted(invoice.items, key=lambda it: it.sort_order)
    items = [_item_dict(it, lp=i) for i, it in enumerate(ordered, start=1)]
    bank_display = format_bank_account_display(seller_bank_account) or ""
    due = _amount_due_for_display(invoice)
    # Preserve remaining_amount=0 semantics (do not collapse to None).
    remaining = invoice.remaining_amount
    if remaining is None and due is not None:
        # Fallback path already applied in _amount_due_for_display; keep None so
        # renderer uses total_gross via same rule.
        pass
    vat_rows = [
        (label, net, vat, gross)
        for label, net, vat, gross in _vat_summary_rows(ordered)
    ]
    return PocInvoiceFixture(
        invoice_number=_strip_display(invoice.number_local) or "—",
        issue_date=_fmt_date(invoice.issue_date),
        sale_date=_fmt_date(invoice.sale_date),
        due_date=_fmt_date(invoice.due_date),
        payment_method=_payment_label(invoice.payment_method),
        bank_account=bank_display,
        seller_name=_party_name(invoice.seller_snapshot),
        seller_address=_party_address(invoice.seller_snapshot),
        seller_nip=_party_nip(invoice.seller_snapshot),
        buyer_name=_party_name(invoice.buyer_snapshot),
        buyer_address=_party_address(invoice.buyer_snapshot),
        buyer_nip=_party_nip(invoice.buyer_snapshot),
        items=items,
        remaining_amount=remaining,
        ksef_number=_strip_display(invoice.ksef_reference_number) or None,
        ksef_xml_bytes=ksef_xml_bytes,
        ksef_environment=(ksef_environment or "test"),
        vat_rows=vat_rows,
        currency=_strip_display(invoice.currency) or "PLN",
        production_bound=True,
        total_gross=_as_decimal(invoice.total_gross),
        document_title=_document_title(invoice),
    )


def render_sale_locked_html(
    invoice: InvoiceResponse,
    *,
    seller_bank_account: str | None = None,
    ksef_xml_bytes: bytes | None = None,
    ksef_environment: str | None = None,
) -> str:
    """Production sale HTML — locked underlay binder (0015N-D geometry)."""
    model = adapt_invoice_response_to_locked(
        invoice,
        seller_bank_account=seller_bank_account,
        ksef_xml_bytes=ksef_xml_bytes,
        ksef_environment=ksef_environment,
    )
    return render_locked_invoice(model).html


def render_sale_locked_bind(
    invoice: InvoiceResponse,
    *,
    seller_bank_account: str | None = None,
    ksef_xml_bytes: bytes | None = None,
    ksef_environment: str | None = None,
) -> LockedBindResult:
    model = adapt_invoice_response_to_locked(
        invoice,
        seller_bank_account=seller_bank_account,
        ksef_xml_bytes=ksef_xml_bytes,
        ksef_environment=ksef_environment,
    )
    return render_locked_invoice(model)
