"""
Generowanie dokumentu PDF / podglądu HTML dla faktury.

Dwa publiczne wywołania:
  render_invoice_html(invoice)  → str  (text/html, do podglądu w przeglądarce)
  render_invoice_pdf(invoice)   → bytes (application/pdf, przez WeasyPrint)

Szablon „modern” A4 — warstwa prezentacji tylko.
Nie zmienia danych fiskalnych, KSeF ani modeli.
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from html import escape

from app.schemas.invoice import InvoiceItemResponse, InvoiceResponse
from app.services.bank_account import format_bank_account_display

logger = logging.getLogger(__name__)

_PAYMENT_METHOD_LABELS: dict[str, str] = {
    "cash": "Gotówka",
    "transfer": "Przelew",
}

_DOC_TITLES: dict[str, str] = {
    "VAT": "FAKTURA VAT",
    "KOR": "FAKTURA KORYGUJĄCA",
    "ZAL": "FAKTURA ZALICZKOWA",
    "ROZ": "FAKTURA ROZLICZAJĄCA",
    "UPR": "FAKTURA UPROSZCZONA",
    "KOR_ZAL": "KOREKTA FAKTURY ZALICZKOWEJ",
    "KOR_ROZ": "KOREKTA FAKTURY ROZLICZAJĄCEJ",
}

_CORRECTION_TYPES = frozenset({"KOR", "KOR_ZAL", "KOR_ROZ"})

_CONTACT_KEY_RE = re.compile(
    r"^(phone|telefon|tel|mobile|komorka|komórka|email|e[_-]?mail|mail)$",
    re.IGNORECASE,
)


def _esc(value: object) -> str:
    return escape(str(value)) if value is not None else ""


def _strip_display(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"none", "null", "undefined"}:
        return ""
    return text


def _as_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _money(value: Decimal | None, currency: str) -> str:
    if value is None:
        return "—"
    return f"{value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)} {currency}"


def _amount(value: Decimal | None) -> str:
    if value is None:
        return "—"
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _format_quantity(value: Decimal | object) -> str:
    dec = _as_decimal(value)
    if dec is None:
        return "—"
    if dec == dec.to_integral_value():
        return str(int(dec.to_integral_value()))
    return str(dec.normalize())


def _format_vat_rate(value: Decimal | object) -> str:
    dec = _as_decimal(value)
    if dec is None:
        return "—"
    if dec == dec.to_integral_value():
        return f"{int(dec)}%"
    return f"{dec.normalize()}%"


def _document_title(invoice: InvoiceResponse) -> str:
    raw = (invoice.invoice_type or "VAT").strip().upper()
    return _DOC_TITLES.get(raw, "FAKTURA VAT")


def _is_correction(invoice: InvoiceResponse) -> bool:
    raw = (invoice.invoice_type or "").strip().upper()
    return raw in _CORRECTION_TYPES


def _party_address_lines(snapshot: dict | None) -> list[str]:
    """Presentation-only address lines from snapshot fields. Never mutates source."""
    snap = snapshot or {}
    address = _strip_display(snap.get("address"))
    street = _strip_display(snap.get("street"))
    building_no = _strip_display(snap.get("building_no"))
    apartment_no = _strip_display(snap.get("apartment_no"))
    postal_code = _strip_display(snap.get("postal_code"))
    city = _strip_display(snap.get("city"))

    lines: list[str] = []

    if address:
        lines.append(address)
        city_line = " ".join(part for part in (postal_code, city) if part)
        if city_line and city_line not in address:
            lines.append(city_line)
        return lines

    if street:
        street_line = " ".join(part for part in (street, building_no) if part)
    elif building_no and city:
        street_line = f"{city} {building_no}"
    elif building_no:
        street_line = building_no
    else:
        street_line = ""

    if apartment_no:
        street_line = f"{street_line} m. {apartment_no}".strip()

    city_line = " ".join(part for part in (postal_code, city) if part)

    if street_line:
        lines.append(street_line)
    if city_line and city_line not in lines:
        lines.append(city_line)
    return lines


def _party_contact_lines(snapshot: dict | None) -> list[str]:
    snap = snapshot or {}
    lines: list[str] = []
    seen: set[str] = set()
    for key, value in snap.items():
        if not _CONTACT_KEY_RE.match(str(key)):
            continue
        text = _strip_display(value)
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        lines.append(text)
    return lines


def _party_inner(snapshot: dict | None, *, include_contact: bool = True) -> str:
    snap = snapshot or {}
    name = _strip_display(snap.get("name"))
    nip = _strip_display(snap.get("nip"))
    address_lines = _party_address_lines(snap)
    contact_lines = _party_contact_lines(snap) if include_contact else []

    parts: list[str] = []
    if name:
        parts.append(f'<p class="party-name">{_esc(name)}</p>')
    for line in address_lines:
        parts.append(f"<p>{_esc(line)}</p>")
    if nip:
        parts.append(f"<p>NIP: {_esc(nip)}</p>")
    for line in contact_lines:
        parts.append(f'<p class="party-contact">{_esc(line)}</p>')
    return "\n".join(parts)


def _party_block(title: str, snapshot: dict | None) -> str:
    return (
        f'<div class="party"><h3>{_esc(title)}</h3>\n'
        f"{_party_inner(snapshot)}\n"
        "</div>"
    )


def _meta_items(invoice: InvoiceResponse) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    if invoice.issue_date:
        items.append(("Data wystawienia", str(invoice.issue_date)))
    if invoice.sale_date:
        items.append(("Data sprzedaży", str(invoice.sale_date)))
    if invoice.due_date:
        items.append(("Termin płatności", str(invoice.due_date)))
    method_raw = _strip_display(invoice.payment_method)
    if method_raw:
        method_label = _PAYMENT_METHOD_LABELS.get(method_raw, method_raw)
        items.append(("Sposób płatności", method_label))
    return items


def _vat_summary_rows(items: list[InvoiceItemResponse]) -> list[tuple[str, Decimal, Decimal, Decimal]]:
    """Aggregate existing item totals by vat_rate — no fiscal recalculation."""
    buckets: dict[Decimal, list[Decimal]] = defaultdict(
        lambda: [Decimal("0.00"), Decimal("0.00"), Decimal("0.00")]
    )
    for item in items:
        rate = _as_decimal(item.vat_rate)
        if rate is None:
            rate = Decimal("0")
        net = _as_decimal(item.net_total) or Decimal("0")
        vat = _as_decimal(item.vat_total) or Decimal("0")
        gross = _as_decimal(item.gross_total) or Decimal("0")
        buckets[rate][0] += net
        buckets[rate][1] += vat
        buckets[rate][2] += gross

    rows: list[tuple[str, Decimal, Decimal, Decimal]] = []
    for rate in sorted(buckets.keys()):
        net, vat, gross = buckets[rate]
        rows.append(
            (
                _format_vat_rate(rate),
                net.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                vat.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                gross.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            )
        )
    return rows


def resolve_seller_bank_account_for_render(
    invoice: InvoiceResponse,
    *,
    company_bank_account: str | None = None,
) -> str | None:
    """Rachunek sprzedawcy na PDF/podglądzie — zależny od kierunku faktury."""
    if invoice.direction == "purchase":
        seller = invoice.seller_snapshot or {}
        for key in ("bank_account", "bankAccount", "nr_rb", "NrRB"):
            raw = seller.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
        return None
    return company_bank_account


def _amount_due_for_display(invoice: InvoiceResponse) -> Decimal | None:
    """DO ZAPŁATY: prefer remaining_amount from API; fallback to total_gross.

    Does not recompute payment allocations — uses InvoiceResponse fields only.
    """
    if invoice.remaining_amount is not None:
        return _as_decimal(invoice.remaining_amount)
    return _as_decimal(invoice.total_gross)


def _due_pay_section(
    invoice: InvoiceResponse,
    *,
    seller_bank_account: str | None,
) -> str:
    currency = invoice.currency or "PLN"
    amount_due = _amount_due_for_display(invoice)
    amount_html = _esc(_money(amount_due, currency))

    details: list[str] = []
    if invoice.due_date:
        details.append(
            f'<div class="pay-detail"><span class="pay-label">Termin</span>'
            f"<strong>{_esc(invoice.due_date)}</strong></div>"
        )
    method_raw = _strip_display(invoice.payment_method)
    if method_raw:
        method_label = _PAYMENT_METHOD_LABELS.get(method_raw, method_raw)
        details.append(
            f'<div class="pay-detail"><span class="pay-label">Sposób płatności</span>'
            f"<strong>{_esc(method_label)}</strong></div>"
        )
    bank_display = format_bank_account_display(seller_bank_account)
    if bank_display:
        details.append(
            f'<div class="pay-detail pay-detail-wide"><span class="pay-label">Rachunek bankowy</span>'
            f"<strong>{_esc(bank_display)}</strong></div>"
        )

    details_html = ""
    if details:
        details_html = f'<div class="pay-details">{"".join(details)}</div>'

    return f"""
<section class="due-box">
  <div class="due-label">Do zapłaty</div>
  <div class="due-amount">{amount_html}</div>
  {details_html}
</section>"""


def _correction_section(invoice: InvoiceResponse) -> str:
    if not _is_correction(invoice):
        return ""
    reason = _strip_display(invoice.correction_reason)
    if not reason:
        return ""
    return f"""
<section class="correction-box">
  <h3>Przyczyna korekty</h3>
  <p>{_esc(reason)}</p>
</section>"""


def _ksef_section(invoice: InvoiceResponse) -> str:
    ref = _strip_display(invoice.ksef_reference_number)
    if not ref:
        return ""
    return f"""
<section class="ksef-box">
  <span class="ksef-label">Numer KSeF</span>
  <code>{_esc(ref)}</code>
</section>"""


def render_invoice_html(
    invoice: InvoiceResponse,
    *,
    seller_bank_account: str | None = None,
) -> str:
    seller = invoice.seller_snapshot or {}
    buyer = invoice.buyer_snapshot or {}
    number = _strip_display(invoice.number_local) or "—"
    title = _document_title(invoice)
    currency = invoice.currency or "PLN"

    item_rows = ""
    for index, item in enumerate(invoice.items, start=1):
        isbn_line = ""
        isbn = _strip_display(item.isbn)
        if isbn:
            isbn_line = (
                f'<div class="item-sub">ISBN: {_esc(isbn)}</div>'
            )
        item_rows += f"""
        <tr>
          <td class="num lp">{index}</td>
          <td class="name">{_esc(item.name)}{isbn_line}</td>
          <td class="num">{_esc(_format_quantity(item.quantity))}</td>
          <td>{_esc(_strip_display(item.unit))}</td>
          <td class="num">{_esc(_amount(_as_decimal(item.unit_price_net)))}</td>
          <td class="num">{_esc(_format_vat_rate(item.vat_rate))}</td>
          <td class="num">{_esc(_amount(_as_decimal(item.net_total)))}</td>
          <td class="num">{_esc(_amount(_as_decimal(item.vat_total)))}</td>
          <td class="num bold">{_esc(_amount(_as_decimal(item.gross_total)))}</td>
        </tr>"""

    vat_rows_html = ""
    for rate_label, net, vat, gross in _vat_summary_rows(invoice.items):
        vat_rows_html += f"""
        <tr>
          <td>{_esc(rate_label)}</td>
          <td class="num">{_esc(_amount(net))}</td>
          <td class="num">{_esc(_amount(vat))}</td>
          <td class="num">{_esc(_amount(gross))}</td>
        </tr>"""

    meta_html = ""
    for label, value in _meta_items(invoice):
        meta_html += (
            f'<div class="meta-item"><span class="meta-label">{_esc(label)}</span>'
            f'<span class="meta-value">{_esc(value)}</span></div>'
        )

    return f"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)} {_esc(number)}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  @page {{
    size: A4;
    margin: 14mm 12mm 16mm 12mm;
  }}
  html {{
    color-scheme: light;
    background: #ffffff;
  }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.4;
    color: #111111;
    background: #ffffff;
    padding: 20px;
    max-width: 210mm;
    margin: 0 auto;
  }}
  .print-btn {{
    display: block;
    margin: 0 auto 16px;
    padding: 10px 28px;
    background: #1a1a1a;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px;
  }}
  .header {{
    display: flex;
    flex-direction: row;
    justify-content: space-between;
    gap: 20px;
    margin-bottom: 18px;
    align-items: flex-start;
  }}
  .header .seller-compact {{
    flex: 1.2 1 0;
    min-width: 0;
  }}
  .header .doc-title-block {{
    flex: 1 1 0;
    min-width: 0;
  }}
  .seller-compact .party-name {{
    font-size: 12pt;
    font-weight: 700;
    margin-bottom: 4px;
  }}
  .seller-compact p {{
    margin-bottom: 2px;
    color: #333333;
    font-size: 10pt;
  }}
  .doc-title-block {{
    text-align: right;
  }}
  .doc-title {{
    font-size: 18pt;
    font-weight: 700;
    letter-spacing: 0.02em;
    color: #111111;
    line-height: 1.2;
  }}
  .doc-number {{
    margin-top: 6px;
    font-size: 11pt;
    color: #333333;
  }}
  .meta {{
    display: flex;
    flex-direction: row;
    flex-wrap: wrap;
    gap: 10px 18px;
    padding: 10px 0;
    border-top: 1px solid #e5e5e5;
    border-bottom: 1px solid #e5e5e5;
    margin-bottom: 16px;
  }}
  .meta-item {{
    flex: 1 1 140px;
    min-width: 120px;
  }}
  .meta-label {{
    display: block;
    font-size: 8.5pt;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #777777;
    margin-bottom: 2px;
  }}
  .meta-value {{
    font-size: 10.5pt;
    color: #111111;
    font-weight: 600;
  }}
  .parties {{
    display: flex;
    flex-direction: row;
    gap: 24px;
    margin-bottom: 16px;
  }}
  .parties .party {{
    flex: 1 1 0;
    min-width: 0;
  }}
  .party h3 {{
    font-size: 8.5pt;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #777777;
    margin-bottom: 6px;
    font-weight: 600;
  }}
  .party .party-name {{
    font-weight: 700;
    font-size: 11pt;
    margin-bottom: 3px;
  }}
  .party p {{
    margin-bottom: 2px;
    color: #222222;
  }}
  .party-contact {{
    color: #555555;
    font-size: 10pt;
  }}
  table.items {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 14px;
    table-layout: fixed;
  }}
  table.items thead {{
    display: table-header-group;
  }}
  table.items th,
  table.items td {{
    padding: 6px 5px;
    vertical-align: top;
    border-bottom: 1px solid #e8e8e8;
    color: #111111;
    background: #ffffff;
    font-size: 9.5pt;
  }}
  table.items th {{
    font-size: 8pt;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    font-weight: 600;
    color: #555555;
    border-bottom: 1.5px solid #cccccc;
    text-align: left;
  }}
  table.items th.num,
  table.items td.num {{
    text-align: right;
  }}
  table.items td.lp {{
    width: 28px;
    color: #666666;
  }}
  table.items td.name {{
    word-wrap: break-word;
    overflow-wrap: anywhere;
    width: 34%;
  }}
  table.items .item-sub {{
    color: #666666;
    font-size: 8.5pt;
    margin-top: 2px;
  }}
  table.items tbody tr {{
    break-inside: avoid;
    page-break-inside: avoid;
  }}
  .bold {{ font-weight: 700; }}
  .summary-wrap {{
    display: flex;
    flex-direction: row;
    gap: 20px;
    margin-bottom: 14px;
    break-inside: avoid;
    page-break-inside: avoid;
  }}
  .summary-wrap > div {{
    flex: 1 1 0;
    min-width: 0;
  }}
  table.vat-summary {{
    width: 100%;
    border-collapse: collapse;
  }}
  table.vat-summary th,
  table.vat-summary td {{
    padding: 5px 6px;
    border-bottom: 1px solid #e8e8e8;
    font-size: 9.5pt;
  }}
  table.vat-summary th {{
    text-align: left;
    font-size: 8pt;
    text-transform: uppercase;
    color: #666666;
    border-bottom: 1.5px solid #cccccc;
  }}
  table.vat-summary th.num,
  table.vat-summary td.num {{
    text-align: right;
  }}
  .totals {{
    text-align: right;
  }}
  .totals-row {{
    display: flex;
    justify-content: flex-end;
    gap: 20px;
    margin-bottom: 4px;
    font-size: 10.5pt;
  }}
  .totals-row span {{
    color: #666666;
    min-width: 56px;
    text-align: left;
  }}
  .totals-row strong {{
    min-width: 110px;
    text-align: right;
  }}
  .totals-row.grand {{
    margin-top: 8px;
    padding-top: 8px;
    border-top: 1.5px solid #111111;
    font-size: 12pt;
  }}
  .due-box {{
    margin: 4px 0 14px;
    padding: 12px 14px;
    border: 1.5px solid #111111;
    break-inside: avoid;
    page-break-inside: avoid;
  }}
  .due-label {{
    font-size: 9pt;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #555555;
    margin-bottom: 2px;
  }}
  .due-amount {{
    font-size: 18pt;
    font-weight: 700;
    color: #111111;
    line-height: 1.2;
  }}
  .pay-details {{
    display: block;
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px solid #dddddd;
  }}
  .pay-detail {{
    display: inline-block;
    vertical-align: top;
    width: 48%;
    margin: 0 1% 8px 0;
  }}
  .pay-detail-wide {{
    display: block;
    width: 100%;
    margin-bottom: 0;
  }}
  .pay-label {{
    display: block;
    font-size: 8pt;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #777777;
    margin-bottom: 2px;
  }}
  .correction-box {{
    margin: 12px 0;
    padding: 10px 0;
    border-top: 1px solid #e5e5e5;
    break-inside: avoid;
    page-break-inside: avoid;
  }}
  .correction-box h3 {{
    font-size: 8.5pt;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #777777;
    margin-bottom: 6px;
  }}
  .ksef-box {{
    margin-top: 12px;
    font-size: 9.5pt;
    color: #444444;
  }}
  .ksef-label {{
    display: block;
    font-size: 8pt;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #777777;
    margin-bottom: 2px;
  }}
  .ksef-box code {{
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 9.5pt;
  }}
  @media print {{
    .print-btn {{ display: none !important; }}
    html, body {{
      background: #ffffff !important;
      color: #111111 !important;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
      padding: 0;
      max-width: none;
    }}
  }}
  @media screen and (max-width: 720px) {{
    .header, .parties, .summary-wrap {{
      flex-direction: column;
    }}
    .doc-title-block {{ text-align: left; }}
    .pay-detail {{ width: 100%; }}
  }}
</style>
</head>
<body>
<button class="print-btn" type="button" onclick="window.print()">Drukuj / Zapisz jako PDF</button>

<header class="header">
  <div class="seller-compact party">
    {_party_inner(seller, include_contact=True)}
  </div>
  <div class="doc-title-block">
    <div class="doc-title">{_esc(title)}</div>
    <div class="doc-number">{_esc(number)}</div>
  </div>
</header>

<section class="meta">
  {meta_html}
</section>

<section class="parties">
  {_party_block("Sprzedawca", seller)}
  {_party_block("Nabywca", buyer)}
</section>

<table class="items">
  <thead>
    <tr>
      <th class="num">Lp.</th>
      <th>Nazwa</th>
      <th class="num">Ilość</th>
      <th>Jm.</th>
      <th class="num">Cena netto</th>
      <th class="num">VAT</th>
      <th class="num">Netto</th>
      <th class="num">VAT kwota</th>
      <th class="num">Brutto</th>
    </tr>
  </thead>
  <tbody>
    {item_rows}
  </tbody>
</table>

<div class="summary-wrap">
  <div>
    <table class="vat-summary">
      <thead>
        <tr>
          <th>Stawka VAT</th>
          <th class="num">Netto</th>
          <th class="num">VAT</th>
          <th class="num">Brutto</th>
        </tr>
      </thead>
      <tbody>
        {vat_rows_html}
      </tbody>
    </table>
  </div>
  <div class="totals">
    <div class="totals-row"><span>Netto</span><strong>{_esc(_money(_as_decimal(invoice.total_net), currency))}</strong></div>
    <div class="totals-row"><span>VAT</span><strong>{_esc(_money(_as_decimal(invoice.total_vat), currency))}</strong></div>
    <div class="totals-row grand"><span>Brutto</span><strong>{_esc(_money(_as_decimal(invoice.total_gross), currency))}</strong></div>
  </div>
</div>

{_due_pay_section(invoice, seller_bank_account=seller_bank_account)}

{_correction_section(invoice)}

{_ksef_section(invoice)}

</body>
</html>"""


def render_invoice_pdf(
    invoice: InvoiceResponse,
    *,
    seller_bank_account: str | None = None,
) -> bytes:
    """Generuje binarny PDF z WeasyPrint na podstawie szablonu HTML.

    Przy pierwszym wywołaniu importuje WeasyPrint (lazy import — biblioteka
    ładuje libpango/cairo tylko przy rzeczywistym użyciu).
    Rzuca ImportError gdy weasyprint nie jest zainstalowany.
    """
    try:
        from weasyprint import HTML  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "WeasyPrint nie jest zainstalowany. Dodaj 'weasyprint' do requirements "
            "i upewnij się, że systemowe biblioteki (libpango, libcairo) są dostępne."
        ) from exc

    html_content = render_invoice_html(
        invoice,
        seller_bank_account=seller_bank_account,
    )
    logger.debug("Generowanie PDF dla faktury %s przez WeasyPrint", invoice.id)
    pdf_bytes: bytes = HTML(string=html_content, base_url=None).write_pdf()
    return pdf_bytes
