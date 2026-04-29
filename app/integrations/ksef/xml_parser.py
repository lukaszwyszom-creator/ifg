"""Parser FA(3) XML → słownik domenowy faktury zakupowej.

Używany przy imporcie faktur odebranych z KSeF.
Namespace: http://crd.gov.pl/wzor/2023/06/29/9781/
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import Any

from lxml import etree

logger = logging.getLogger(__name__)

_NS = "http://crd.gov.pl/wzor/2023/06/29/9781/"
_NS_MAP = {"fa": _NS}


def _txt(el: etree._Element | None) -> str:
    """Bezpiecznie zwraca text z elementu lub pusty string."""
    if el is None:
        return ""
    return (el.text or "").strip()


def _dec(el: etree._Element | None, default: Decimal = Decimal("0")) -> Decimal:
    """Bezpiecznie parsuje Decimal z elementu."""
    text = _txt(el)
    if not text:
        return default
    try:
        return Decimal(text)
    except InvalidOperation:
        return default


def _find(el: etree._Element, xpath: str) -> etree._Element | None:
    return el.find(xpath, _NS_MAP)


def _findall(el: etree._Element, xpath: str) -> list[etree._Element]:
    return el.findall(xpath, _NS_MAP)


def _parse_address(subject_el: etree._Element) -> dict[str, str]:
    addr = _find(subject_el, "fa:Adres")
    if addr is None:
        return {}
    return {
        "street": _txt(_find(addr, "fa:AdresL1")),
        "building_no": "",
        "apartment_no": _txt(_find(addr, "fa:AdresL2")),
        "postal_code": _txt(_find(addr, "fa:KodPocztowy")),
        "city": _txt(_find(addr, "fa:Miejscowosc")),
        "country": _txt(_find(addr, "fa:KodKraju")) or "PL",
    }


def _parse_subject(subject_el: etree._Element) -> dict[str, Any]:
    """Parsuje Podmiot1/Sprzedawca lub Podmiot2/Nabywca → snapshot."""
    return {
        "nip": _txt(_find(subject_el, "fa:NIP")),
        "name": _txt(_find(subject_el, "fa:Nazwa")),
        **_parse_address(subject_el),
    }


def _parse_item(row_el: etree._Element, sort_order: int) -> dict[str, Any]:
    """Parsuje FaWiersz → dict pasujący do InvoiceItem."""
    vat_rate_text = _txt(_find(row_el, "fa:P_12"))
    try:
        vat_rate = Decimal(vat_rate_text)
    except InvalidOperation:
        # "zw", "np" itp.
        vat_rate = Decimal("0")

    unit_price_net = _dec(_find(row_el, "fa:P_9A"))
    quantity = _dec(_find(row_el, "fa:P_8B"), Decimal("1"))
    net_total = _dec(_find(row_el, "fa:P_11"))

    vat_total = (net_total * vat_rate / Decimal("100")).quantize(Decimal("0.01"))
    gross_total = net_total + vat_total

    return {
        "name": _txt(_find(row_el, "fa:P_7")),
        "quantity": quantity,
        "unit": _txt(_find(row_el, "fa:P_8A")) or "szt.",
        "unit_price_net": unit_price_net,
        "vat_rate": vat_rate,
        "net_total": net_total,
        "vat_total": vat_total,
        "gross_total": gross_total,
        "sort_order": sort_order,
    }


# Mapowanie pola P_13/P_14 → suma netto/VAT dla różnych stawek
_P13_FIELDS = ["P_13_1", "P_13_2", "P_13_3", "P_13_4", "P_13_6", "P_13_7", "P_13_8", "P_13_9", "P_13_10", "P_13_11"]
_P14_FIELDS = ["P_14_1", "P_14_2", "P_14_3", "P_14_4", "P_14_5"]


def _parse_xml_root(xml_bytes: bytes) -> etree._Element:
    try:
        return etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as exc:
        raise ValueError(f"Błędny XML FA(3): {exc}") from exc


def _extract_required_structure(
    root: etree._Element,
) -> tuple[etree._Element, etree._Element, etree._Element]:
    fa_el = _find(root, "fa:Fa")
    if fa_el is None:
        raise ValueError("Brak elementu <Fa> w dokumencie FA(3)")

    podmiot1 = _find(root, "fa:Podmiot1")
    podmiot2 = _find(root, "fa:Podmiot2")
    if podmiot1 is None or podmiot2 is None:
        raise ValueError("Brak elementów Podmiot1/Podmiot2 w dokumencie FA(3)")

    sprzedawca_el = _find(podmiot1, "fa:Sprzedawca")
    nabywca_el = _find(podmiot2, "fa:Nabywca")
    if sprzedawca_el is None or nabywca_el is None:
        raise ValueError("Brak danych sprzedawcy/nabywcy w dokumencie FA(3)")

    return fa_el, sprzedawca_el, nabywca_el


def _extract_basic_fields(fa_el: etree._Element) -> tuple[str, str, str, str]:
    issue_date_txt = _txt(_find(fa_el, "fa:P_1"))
    sale_date_txt = _txt(_find(fa_el, "fa:P_1M")) or issue_date_txt
    number_local = _txt(_find(fa_el, "fa:P_2"))
    currency = _txt(_find(fa_el, "fa:KodWaluty")) or "PLN"
    return issue_date_txt, sale_date_txt, number_local, currency


def _extract_totals(fa_el: etree._Element) -> tuple[Decimal, Decimal, Decimal]:
    total_net = sum(_dec(_find(fa_el, f"fa:{field}")) for field in _P13_FIELDS)
    total_vat = sum(_dec(_find(fa_el, f"fa:{field}")) for field in _P14_FIELDS)
    total_gross = _dec(_find(fa_el, "fa:P_15"))
    if total_gross == Decimal("0") and total_net > Decimal("0"):
        total_gross = total_net + total_vat
    return total_net, total_vat, total_gross


def _extract_annotations(fa_el: etree._Element) -> dict[str, bool]:
    return {
        "use_split_payment": _txt(_find(fa_el, "fa:P_16")) == "true",
        "self_billing": _txt(_find(fa_el, "fa:P_17")) == "true",
        "reverse_charge": _txt(_find(fa_el, "fa:P_18")) == "true",
        "reverse_charge_art": _txt(_find(fa_el, "fa:P_18A")) == "true",
        "reverse_charge_flag": _txt(_find(fa_el, "fa:P_18B")) == "true",
        "cash_accounting_method": _txt(_find(fa_el, "fa:P_19")) == "true",
    }


def _extract_exchange_rate(fa_el: etree._Element) -> tuple[Decimal | None, str | None]:
    kurs_el = _find(fa_el, "fa:KursWaluty")
    if kurs_el is None:
        return None, None

    exchange_rate = _dec(_find(kurs_el, "fa:KursWalutyZ")) or None
    exchange_rate_date = _txt(_find(kurs_el, "fa:DataKursuWaluty")) or None
    return exchange_rate, exchange_rate_date


def _extract_invoice_type(fa_el: etree._Element) -> str:
    rodzaj = _txt(_find(fa_el, "fa:RodzajFaktury")) or "VAT"
    return rodzaj


def _parse_items(fa_el: etree._Element) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for idx, row_el in enumerate(_findall(fa_el, "fa:FaWiersz"), start=1):
        try:
            items.append(_parse_item(row_el, idx))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Błąd parsowania pozycji %d: %s", idx, exc)
    return items


def _build_parsed_invoice_payload(
    fa_el: etree._Element,
    seller_snapshot: dict[str, Any],
    buyer_snapshot: dict[str, Any],
) -> dict[str, Any]:
    issue_date_txt, sale_date_txt, number_local, currency = _extract_basic_fields(fa_el)
    if not issue_date_txt:
        raise ValueError("Brak daty wystawienia (P_1) w dokumencie FA(3)")

    total_net, total_vat, total_gross = _extract_totals(fa_el)
    exchange_rate, exchange_rate_date = _extract_exchange_rate(fa_el)

    return {
        "number_local": number_local or None,
        "issue_date": issue_date_txt,
        "sale_date": sale_date_txt,
        "currency": currency,
        "seller_snapshot": seller_snapshot,
        "buyer_snapshot": buyer_snapshot,
        "total_net": total_net,
        "total_vat": total_vat,
        "total_gross": total_gross,
        "invoice_type": _extract_invoice_type(fa_el),
        "items": _parse_items(fa_el),
        **_extract_annotations(fa_el),
        "exchange_rate": exchange_rate,
        "exchange_rate_date": exchange_rate_date,
    }


def parse_fa3_xml(xml_bytes: bytes) -> dict[str, Any]:
    """Parsuje XML FA(3) → dict gotowy do tworzenia Invoice w bazie.

    Zwraca słownik z kluczami pasującymi do Invoice ORM / domain model.
    Raises ValueError jeśli XML jest niepoprawny lub brakuje wymaganych pól.
    """
    root = _parse_xml_root(xml_bytes)
    fa_el, sprzedawca_el, nabywca_el = _extract_required_structure(root)
    seller_snapshot = _parse_subject(sprzedawca_el)
    buyer_snapshot = _parse_subject(nabywca_el)
    return _build_parsed_invoice_payload(
        fa_el=fa_el,
        seller_snapshot=seller_snapshot,
        buyer_snapshot=buyer_snapshot,
    )
