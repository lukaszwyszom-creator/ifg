"""Elegant A4 sales-invoice presentation (GWO-0015).

Presentation-only. Reuses shared helpers from pdf_service.
Does not generate fake KSeF QR codes.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from app.schemas.invoice import InvoiceItemResponse, InvoiceResponse
from app.services.bank_account import format_bank_account_display
from app.services.pdf_service import (
    _PAYMENT_METHOD_LABELS,
    _amount_due_for_display,
    _as_decimal,
    _correction_section,
    _document_title,
    _esc,
    _format_quantity,
    _format_vat_rate,
    _party_address_lines,
    _strip_display,
    _vat_summary_rows,
)

# Shared layout axis: meta middle separator and parties separator share 50%.
_LAYOUT_AXIS_X = "50%"

_ASSET_DIR = Path(__file__).resolve().parent.parent / "assets" / "invoice"


def _amount_pl(value: Decimal | None) -> str:
    if value is None:
        return "—"
    quantized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    sign = "-" if quantized < 0 else ""
    absolute = abs(quantized)
    raw = f"{absolute:.2f}"
    whole, frac = raw.split(".")
    groups: list[str] = []
    while whole:
        groups.append(whole[-3:])
        whole = whole[:-3]
    grouped = " ".join(reversed(groups))
    return f"{sign}{grouped},{frac}"


def _money_pl(value: Decimal | None, currency: str) -> str:
    if value is None:
        return "—"
    return f"{_amount_pl(value)} {currency}"


def _unit_price_gross(item: InvoiceItemResponse) -> Decimal | None:
    """Presentation unit gross from existing item fields — no fiscal recalc of totals."""
    qty = _as_decimal(item.quantity)
    gross = _as_decimal(item.gross_total)
    unit_net = _as_decimal(item.unit_price_net)
    vat = _as_decimal(item.vat_rate)
    if qty is not None and qty > 0 and gross is not None:
        return (gross / qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if unit_net is not None and vat is not None:
        return (unit_net * (Decimal("1") + vat / Decimal("100"))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    return None


def _stained_glass_markup() -> str:
    """Swappable brand slot. Missing file → empty circle (not fake branding)."""
    for name in ("stained_glass.png", "stained_glass.svg", "stained_glass.jpg"):
        path = _ASSET_DIR / name
        if path.is_file():
            # Relative file:// unsupported in WeasyPrint reliably; embed as data URI only
            # when operator supplies asset — for now path-based via base64 if small PNG/SVG.
            import base64

            raw = path.read_bytes()
            if name.endswith(".svg"):
                mime = "image/svg+xml"
            elif name.endswith(".jpg"):
                mime = "image/jpeg"
            else:
                mime = "image/png"
            b64 = base64.b64encode(raw).decode("ascii")
            return (
                f'<div class="stained-glass has-asset" '
                f'data-stained-glass="provided">'
                f'<img src="data:{mime};base64,{b64}" alt="" /></div>'
            )
    return (
        '<div class="stained-glass missing-asset" '
        'data-stained-glass="STAINED_GLASS_ASSET_REQUIRED" '
        'aria-hidden="true"></div>'
    )


def _ksef_footer(invoice: InvoiceResponse) -> str:
    """KSeF number when present. QR intentionally omitted — no verified QR builder in IFG."""
    ref = _strip_display(invoice.ksef_reference_number)
    ksef_text = f'<div class="ksef-text">KSEF: {_esc(ref)}</div>' if ref else '<div class="ksef-text"></div>'
    return f"""
<footer class="ksef-footer">
  {ksef_text}
  <div class="qr-slot" data-qr-status="MISSING_MECHANISM" aria-hidden="true"></div>
</footer>"""


def _party_block_elegant(title: str, snapshot: dict | None) -> str:
    snap = snapshot or {}
    name = _strip_display(snap.get("name"))
    nip = _strip_display(snap.get("nip"))
    address_lines = _party_address_lines(snap)
    parts: list[str] = []
    if name:
        parts.append(f'<p class="party-name">{_esc(name)}</p>')
    for line in address_lines:
        parts.append(f"<p>{_esc(line)}</p>")
    if nip:
        parts.append(f"<p>NIP: {_esc(nip)}</p>")
    return (
        f'<div class="party"><h3>{_esc(title)}</h3>\n'
        f"{''.join(parts)}\n"
        "</div>"
    )


def render_sale_elegant_html(
    invoice: InvoiceResponse,
    *,
    seller_bank_account: str | None = None,
) -> str:
    seller = invoice.seller_snapshot or {}
    buyer = invoice.buyer_snapshot or {}
    number = _strip_display(invoice.number_local) or "—"
    title = _document_title(invoice)
    currency = invoice.currency or "PLN"
    amount_due = _amount_due_for_display(invoice)
    bank_display = format_bank_account_display(seller_bank_account)

    issue = _esc(invoice.issue_date) if invoice.issue_date else "—"
    sale = _esc(invoice.sale_date) if invoice.sale_date else "—"
    due = _esc(invoice.due_date) if invoice.due_date else "—"
    method_raw = _strip_display(invoice.payment_method)
    method = _PAYMENT_METHOD_LABELS.get(method_raw, method_raw) if method_raw else "—"

    item_rows = ""
    for index, item in enumerate(invoice.items, start=1):
        isbn_line = ""
        isbn = _strip_display(item.isbn)
        if isbn:
            isbn_line = f'<div class="item-sub">ISBN: {_esc(isbn)}</div>'
        unit_gross = _unit_price_gross(item)
        item_rows += f"""
        <tr>
          <td class="lp">{index}</td>
          <td class="name">{_esc(item.name)}{isbn_line}</td>
          <td class="num qty">{_esc(_format_quantity(item.quantity))}</td>
          <td class="unit">{_esc(_strip_display(item.unit))}</td>
          <td class="num">{_esc(_amount_pl(_as_decimal(item.unit_price_net)))}</td>
          <td class="num">{_esc(_amount_pl(unit_gross))}</td>
          <td class="num vat-rate">{_esc(_format_vat_rate(item.vat_rate))}</td>
          <td class="num">{_esc(_amount_pl(_as_decimal(item.net_total)))}</td>
          <td class="num">{_esc(_amount_pl(_as_decimal(item.vat_total)))}</td>
          <td class="num bold">{_esc(_amount_pl(_as_decimal(item.gross_total)))}</td>
        </tr>"""

    vat_rows_html = ""
    for rate_label, net, vat, gross in _vat_summary_rows(invoice.items):
        vat_rows_html += f"""
        <tr>
          <td>{_esc(rate_label)}</td>
          <td class="num">{_esc(_amount_pl(net))}</td>
          <td class="num">{_esc(_amount_pl(vat))}</td>
          <td class="num">{_esc(_amount_pl(gross))}</td>
        </tr>"""

    bank_block = ""
    if bank_display:
        bank_block = f"""
<div class="bank-row">
  <span class="meta-label">Rachunek bankowy</span>
  <span class="meta-value bank">{_esc(bank_display)}</span>
</div>"""

    axis = _LAYOUT_AXIS_X
    stained = _stained_glass_markup()

    return f"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)} {_esc(number)}</title>
<style>
  :root {{
    --ink: #1a2744;
    --gold: #8a7348;
    --gold-soft: #c4a574;
    --ivory: #f7f1e6;
    --paper: #faf6ee;
    --line: #c9b896;
    --muted: #5c6578;
    --layout-axis-x: {axis};
    --ornament-x: 10mm;
    --date-sep-height: 1.1em;
  }}
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  @page {{
    size: A4;
    margin: 14mm 14mm 16mm 18mm;
  }}
  html {{
    color-scheme: light;
    background: var(--ivory);
  }}
  body {{
    font-family: "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif;
    font-size: 10pt;
    line-height: 1.45;
    color: var(--ink);
    background: var(--paper);
    padding: 18px 22px 22px 28px;
    max-width: 210mm;
    margin: 0 auto;
    position: relative;
  }}
  .print-btn {{
    display: block;
    margin: 0 auto 14px;
    padding: 8px 22px;
    background: var(--ink);
    color: #fff;
    border: none;
    border-radius: 2px;
    cursor: pointer;
    font-size: 12px;
    font-family: Georgia, serif;
  }}
  .sheet {{
    position: relative;
    padding-left: 8mm;
  }}
  /* Left binder ornament — fixed X; do not shift during layout tweaks */
  .ornament {{
    position: absolute;
    left: var(--ornament-x);
    top: 0;
    bottom: 0;
    width: 0;
    border-left: 0.6pt solid var(--gold);
    z-index: 0;
    pointer-events: none;
  }}
  .ornament .diamond {{
    position: absolute;
    left: -3.5px;
    width: 7px;
    height: 7px;
    background: var(--paper);
    border: 0.6pt solid var(--gold);
    transform: rotate(45deg);
  }}
  .ornament .diamond.d1 {{ top: 42mm; }}
  .ornament .diamond.d2 {{ top: 78mm; }}
  .ornament .diamond.d3 {{ top: 118mm; }}
  .stained-glass {{
    position: absolute;
    left: calc(var(--ornament-x) - 9mm);
    top: 8mm;
    width: 18mm;
    height: 18mm;
    border-radius: 50%;
    border: 0.7pt solid var(--gold-soft);
    background: radial-gradient(circle at 40% 35%, #f3e7d0 0%, #e8d5b0 45%, #d4b87a 100%);
    overflow: hidden;
    z-index: 1;
  }}
  .stained-glass.has-asset {{
    background: var(--paper);
  }}
  .stained-glass img {{
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }}
  .stained-glass.missing-asset::after {{
    content: "";
    display: block;
    width: 100%;
    height: 100%;
    opacity: 0.35;
    background:
      linear-gradient(30deg, transparent 40%, var(--gold-soft) 41%, transparent 42%),
      linear-gradient(-30deg, transparent 40%, var(--gold-soft) 41%, transparent 42%);
  }}
  .brand {{
    text-align: center;
    margin: 6mm 0 8mm;
    position: relative;
    z-index: 1;
  }}
  .brand-name {{
    font-size: 22pt;
    font-weight: 700;
    letter-spacing: 0.28em;
    color: var(--ink);
    line-height: 1.1;
  }}
  .brand-sub {{
    margin-top: 4px;
    font-size: 9pt;
    letter-spacing: 0.55em;
    color: var(--gold);
    font-weight: 600;
  }}
  .doc-head {{
    margin: 4mm 0 3mm;
    position: relative;
    z-index: 1;
  }}
  .doc-title {{
    font-size: 14pt;
    font-weight: 700;
    letter-spacing: 0.08em;
    color: var(--ink);
  }}
  .doc-number {{
    margin-top: 2px;
    font-size: 11pt;
    color: var(--ink);
  }}
  .doc-rule {{
    margin-top: 6px;
    height: 0;
    border-top: 0.7pt solid var(--gold);
    width: 42%;
  }}
  /* Shared axis grid: 4 date cols → mid separator at 50%; parties 2 cols → separator at 50% */
  .meta-dates {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr 1fr;
    column-gap: 0;
    margin: 8px 0 6px;
    position: relative;
    z-index: 1;
  }}
  .meta-dates .meta-cell {{
    padding: 2px 10px;
    min-width: 0;
  }}
  .meta-dates .meta-cell:not(:last-child) {{
    border-right: 0.6pt solid var(--gold-soft);
  }}
  .meta-dates .meta-cell .meta-label,
  .bank-row .meta-label,
  .party h3 {{
    display: block;
    font-size: 7.5pt;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--muted);
    font-family: "Segoe UI", Arial, sans-serif;
    font-weight: 600;
    margin-bottom: 2px;
  }}
  .meta-dates .meta-cell .meta-value {{
    font-size: 10pt;
    font-weight: 600;
    color: var(--ink);
    /* Short separator height locked via line-box — equals --date-sep-height */
    line-height: var(--date-sep-height);
    min-height: var(--date-sep-height);
  }}
  .meta-dates .meta-cell:nth-child(2) {{
    /* middle date separator sits on --layout-axis-x (50%) via 4-col grid */
  }}
  .bank-row {{
    margin: 2px 0 10px;
    padding: 0 10px;
    position: relative;
    z-index: 1;
  }}
  .bank-row .meta-value.bank {{
    font-size: 10.5pt;
    font-weight: 600;
    letter-spacing: 0.02em;
  }}
  .parties {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    column-gap: 0;
    margin: 4px 0 12px;
    position: relative;
    z-index: 1;
  }}
  .parties .party {{
    padding: 4px 14px;
    min-width: 0;
  }}
  .parties .party:first-child {{
    border-right: 0.6pt solid var(--gold);
    /* separator X = --layout-axis-x (50%) — same as meta mid separator */
  }}
  .party .party-name {{
    font-weight: 700;
    font-size: 10.5pt;
    margin-bottom: 2px;
  }}
  .party p {{
    margin-bottom: 1px;
    color: var(--ink);
    font-size: 9.5pt;
  }}
  table.items {{
    width: 100%;
    border-collapse: collapse;
    margin: 6px 0 12px;
    table-layout: fixed;
    position: relative;
    z-index: 1;
  }}
  table.items thead {{ display: table-header-group; }}
  table.items th,
  table.items td {{
    padding: 5px 3px;
    vertical-align: top;
    border-bottom: 0.5pt solid var(--line);
    font-size: 8.5pt;
    color: var(--ink);
    background: transparent;
  }}
  table.items th {{
    font-size: 7pt;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 600;
    color: var(--muted);
    border-bottom: 0.9pt solid var(--gold);
    text-align: left;
    font-family: "Segoe UI", Arial, sans-serif;
  }}
  table.items th.num,
  table.items td.num {{ text-align: right; }}
  table.items th.lp,
  table.items td.lp {{
    width: 1.6em;
    text-align: left;
    padding-left: 0;
    padding-right: 2px;
    white-space: nowrap;
  }}
  table.items th.name,
  table.items td.name {{
    width: 28%;
    word-wrap: break-word;
    overflow-wrap: anywhere;
  }}
  table.items th.qty,
  table.items td.qty {{ width: 3em; }}
  table.items th.unit,
  table.items td.unit {{
    width: 5ch;
    white-space: nowrap;
  }}
  table.items th.vat-rate,
  table.items td.vat-rate {{
    width: 2.8em;
    white-space: nowrap;
  }}
  table.items .item-sub {{
    color: var(--muted);
    font-size: 7.5pt;
    margin-top: 1px;
  }}
  table.items tbody tr {{
    break-inside: avoid;
    page-break-inside: avoid;
  }}
  .bold {{ font-weight: 700; }}
  .summary-wrap {{
    display: grid;
    grid-template-columns: 1.4fr 0.9fr;
    gap: 16px;
    margin: 4px 0 10px;
    break-inside: avoid;
    page-break-inside: avoid;
    position: relative;
    z-index: 1;
  }}
  .vat-block h3 {{
    font-size: 8pt;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--muted);
    margin-bottom: 4px;
    font-family: "Segoe UI", Arial, sans-serif;
  }}
  table.vat-summary {{
    width: 100%;
    border-collapse: collapse;
  }}
  table.vat-summary th,
  table.vat-summary td {{
    padding: 4px 5px;
    border-bottom: 0.5pt solid var(--line);
    font-size: 8.5pt;
  }}
  table.vat-summary th {{
    text-align: left;
    font-size: 7pt;
    text-transform: uppercase;
    color: var(--muted);
    border-bottom: 0.8pt solid var(--gold);
    font-family: "Segoe UI", Arial, sans-serif;
  }}
  table.vat-summary th.num,
  table.vat-summary td.num {{ text-align: right; }}
  .due-quiet {{
    text-align: right;
    align-self: start;
    padding-top: 18px;
  }}
  .due-quiet .due-label {{
    font-size: 8pt;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--muted);
    font-family: "Segoe UI", Arial, sans-serif;
  }}
  .due-quiet .due-amount {{
    margin-top: 2px;
    font-size: 14pt;
    font-weight: 700;
    color: var(--ink);
    letter-spacing: 0.02em;
  }}
  .correction-box {{
    margin: 10px 0;
    padding: 8px 0;
    border-top: 0.5pt solid var(--line);
    break-inside: avoid;
    page-break-inside: avoid;
  }}
  .correction-box h3 {{
    font-size: 8pt;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--muted);
    margin-bottom: 4px;
  }}
  .ksef-footer {{
    display: grid;
    grid-template-columns: 1fr auto;
    align-items: end;
    gap: 12px;
    margin-top: 14px;
    padding-top: 8px;
    border-top: 0.5pt solid var(--line);
    position: relative;
    z-index: 1;
  }}
  .ksef-text {{
    font-size: 8.5pt;
    color: var(--muted);
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  }}
  .qr-slot {{
    width: 22mm;
    height: 22mm;
    /* Reserved — no fake QR rendered */
  }}
  @media print {{
    .print-btn {{ display: none !important; }}
    html, body {{
      background: var(--paper) !important;
      color: var(--ink) !important;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
      padding: 0;
      max-width: none;
    }}
  }}
</style>
</head>
<body data-invoice-template="sale-elegant">
<button class="print-btn" type="button" onclick="window.print()">Drukuj / Zapisz jako PDF</button>
<div class="sheet">
  <div class="ornament" aria-hidden="true">
    <span class="diamond d1"></span>
    <span class="diamond d2"></span>
    <span class="diamond d3"></span>
  </div>
  {stained}

  <header class="brand">
    <div class="brand-name">IKONA</div>
    <div class="brand-sub">W Y D A W N I C T W O</div>
  </header>

  <div class="doc-head">
    <div class="doc-title">{_esc(title)}</div>
    <div class="doc-number">{_esc(number)}</div>
    <div class="doc-rule"></div>
  </div>

  <section class="meta-dates" data-layout-axis-x="{axis}">
    <div class="meta-cell">
      <span class="meta-label">Data wystawienia</span>
      <span class="meta-value">{issue}</span>
    </div>
    <div class="meta-cell" data-axis-before="mid">
      <span class="meta-label">Data sprzedaży</span>
      <span class="meta-value">{sale}</span>
    </div>
    <div class="meta-cell" data-axis-after="mid">
      <span class="meta-label">Termin płatności</span>
      <span class="meta-value">{due}</span>
    </div>
    <div class="meta-cell">
      <span class="meta-label">Sposób płatności</span>
      <span class="meta-value">{_esc(method)}</span>
    </div>
  </section>
  {bank_block}

  <section class="parties" data-layout-axis-x="{axis}">
    {_party_block_elegant("Sprzedawca", seller)}
    {_party_block_elegant("Nabywca", buyer)}
  </section>

  <table class="items">
    <thead>
      <tr>
        <th class="lp">LP</th>
        <th class="name">Nazwa towaru / usługi</th>
        <th class="num qty">Ilość</th>
        <th class="unit">JM</th>
        <th class="num">Cena netto</th>
        <th class="num">Cena brutto</th>
        <th class="num vat-rate">VAT</th>
        <th class="num">Wartość netto</th>
        <th class="num">Kwota VAT</th>
        <th class="num">Wartość brutto</th>
      </tr>
    </thead>
    <tbody>
      {item_rows}
    </tbody>
  </table>

  <div class="summary-wrap">
    <div class="vat-block">
      <h3>Podsumowanie VAT</h3>
      <table class="vat-summary">
        <thead>
          <tr>
            <th>Stawka VAT</th>
            <th class="num">Wartość netto</th>
            <th class="num">Kwota VAT</th>
            <th class="num">Wartość brutto</th>
          </tr>
        </thead>
        <tbody>
          {vat_rows_html}
        </tbody>
      </table>
    </div>
    <div class="due-quiet">
      <div class="due-label">Do zapłaty</div>
      <div class="due-amount">{_esc(_money_pl(amount_due, currency))}</div>
    </div>
  </div>

  {_correction_section(invoice)}
  {_ksef_footer(invoice)}
</div>
</body>
</html>"""
