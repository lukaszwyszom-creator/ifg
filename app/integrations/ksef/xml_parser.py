"""Parser FA(3) XML → słownik domenowy faktury zakupowej.

Używany przy imporcie faktur odebranych z KSeF.
Namespace: http://crd.gov.pl/wzor/2025/06/25/13775/
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from lxml import etree

from app.integrations.ksef.fa3_address import (
    purchase_seller_city_integrity_error,
    split_fa3_address_lines,
)

logger = logging.getLogger(__name__)

_NS = "http://crd.gov.pl/wzor/2025/06/25/13775/"
_NS_MAP = {"fa": _NS}
_TWO_PLACES = Decimal("0.01")


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


def _local_name(el: etree._Element) -> str:
    return etree.QName(el).localname


def _first_child_by_local_name(el: etree._Element, *names: str) -> etree._Element | None:
    wanted = set(names)
    for child in el:
        if _local_name(child) in wanted:
            return child
    return None


def _first_text_by_local_name(el: etree._Element, *names: str) -> str:
    child = _first_child_by_local_name(el, *names)
    return _txt(child)


def _field_dec(row_el: etree._Element, fa_tag: str, *local_names: str) -> Decimal:
    """Odczyt kwoty z elementu FA(3) — xpath z namespace, potem localname."""
    value = _dec(_find(row_el, f"fa:{fa_tag}"))
    if value != Decimal("0"):
        return value
    for name in local_names:
        value = _dec(_first_child_by_local_name(row_el, name))
        if value != Decimal("0"):
            return value
    return Decimal("0")


def _field_txt(row_el: etree._Element, fa_tag: str, *local_names: str) -> str:
    text = _txt(_find(row_el, f"fa:{fa_tag}"))
    if text:
        return text
    for name in local_names:
        text = _first_text_by_local_name(row_el, name)
        if text:
            return text
    return ""


def _quantize_money(value: Decimal) -> Decimal:
    return value.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def _parse_address(subject_el: etree._Element) -> dict[str, str]:
    addr = _find(subject_el, "fa:Adres")
    if addr is None:
        addr = _first_child_by_local_name(subject_el, "Adres")
    if addr is None:
        return {}

    adres_l1 = _txt(_find(addr, "fa:AdresL1")) or _first_text_by_local_name(addr, "AdresL1")
    adres_l2 = _txt(_find(addr, "fa:AdresL2")) or _first_text_by_local_name(addr, "AdresL2")
    structured_street = _first_text_by_local_name(addr, "Ulica")
    structured_postal = _txt(_find(addr, "fa:KodPocztowy")) or _first_text_by_local_name(
        addr, "KodPocztowy"
    )
    structured_city = _txt(_find(addr, "fa:Miejscowosc")) or _first_text_by_local_name(
        addr, "Miejscowosc"
    )
    # Legacy NrLokalu — nie mylić z FA(3) AdresL2 (druga linia adresu).
    structured_apartment = _first_text_by_local_name(addr, "NrLokalu")
    country = _txt(_find(addr, "fa:KodKraju")) or _first_text_by_local_name(addr, "KodKraju") or "PL"

    return split_fa3_address_lines(
        adres_l1=adres_l1,
        adres_l2=adres_l2,
        structured_street=structured_street,
        structured_postal=structured_postal,
        structured_city=structured_city,
        structured_apartment=structured_apartment,
        country=country,
    )


def _raw_adres_lines(subject_el: etree._Element | None) -> tuple[str, str, bool]:
    """Zwraca (AdresL1, AdresL2, czy XML ma niepuste Miejscowosc)."""
    if subject_el is None:
        return "", "", False
    addr = _find(subject_el, "fa:Adres")
    if addr is None:
        addr = _first_child_by_local_name(subject_el, "Adres")
    if addr is None:
        return "", "", False
    l1 = _txt(_find(addr, "fa:AdresL1")) or _first_text_by_local_name(addr, "AdresL1")
    l2 = _txt(_find(addr, "fa:AdresL2")) or _first_text_by_local_name(addr, "AdresL2")
    structured_city = _txt(_find(addr, "fa:Miejscowosc")) or _first_text_by_local_name(
        addr, "Miejscowosc"
    )
    return l1, l2, bool(structured_city.strip())


def _parse_subject(subject_el: etree._Element) -> dict[str, Any]:
    """Parsuje Podmiot1/Podmiot2 (DaneIdentyfikacyjne lub legacy wrapper) → snapshot."""
    identity_el = _find(subject_el, "fa:DaneIdentyfikacyjne")
    if identity_el is None:
        identity_el = _first_child_by_local_name(subject_el, "DaneIdentyfikacyjne")
    if identity_el is None:
        identity_el = subject_el

    address_el = subject_el
    if _find(subject_el, "fa:Adres") is None and _first_child_by_local_name(subject_el, "Adres") is None:
        parent = subject_el.getparent()
        if parent is not None:
            address_el = parent

    return {
        "nip": (
            _txt(_find(identity_el, "fa:NIP"))
            or _first_text_by_local_name(identity_el, "NIP", "NrVatUE", "IdentyfikatorPodatkowy")
        ),
        "name": (
            _txt(_find(identity_el, "fa:Nazwa"))
            or _first_text_by_local_name(identity_el, "Nazwa", "NazwaPodmiotu", "PelnaNazwa")
        ),
        **_parse_address(address_el),
    }


def _parse_item(row_el: etree._Element, sort_order: int) -> dict[str, Any]:
    """Parsuje FaWiersz → dict pasujący do InvoiceItem."""
    from app.services.invoice_totals import InvoiceTotalsCalculator

    vat_rate_text = _field_txt(row_el, "P_12", "P_12")
    try:
        vat_rate = Decimal(vat_rate_text)
    except InvalidOperation:
        # "zw", "np" itp.
        vat_rate = Decimal("0")

    unit_price_net = _field_dec(row_el, "P_9A", "P_9A")
    unit_price_gross = _field_dec(row_el, "P_9B", "P_9B")
    quantity = _field_dec(row_el, "P_8B", "P_8B") or Decimal("1")
    net_total_xml = _field_dec(row_el, "P_11", "P_11")
    gross_total_xml = _field_dec(row_el, "P_11A", "P_11A")
    vat_total_xml = _field_dec(row_el, "P_11Vat", "P_11Vat")

    gross_first = (
        gross_total_xml > Decimal("0")
        or (unit_price_gross > Decimal("0") and unit_price_net == Decimal("0"))
    )

    if gross_first:
        _, net_total, vat_total, gross_total = InvoiceTotalsCalculator.calculate_line_amounts(
            quantity=quantity,
            vat_rate=vat_rate,
            price_mode="gross",
            unit_price_gross=unit_price_gross,
            line_gross_total=gross_total_xml,
        )
    else:
        if net_total_xml > Decimal("0"):
            unit_for_calc = _quantize_money(net_total_xml / quantity) if quantity > Decimal("0") else unit_price_net
        else:
            unit_for_calc = unit_price_net
        _, net_total, vat_total, gross_total = InvoiceTotalsCalculator.calculate_line_amounts(
            quantity=quantity,
            vat_rate=vat_rate,
            price_mode="net",
            unit_price_net=unit_for_calc,
        )
        if net_total_xml > Decimal("0"):
            net_total = _quantize_money(net_total_xml)
            if vat_total_xml > Decimal("0"):
                vat_total = _quantize_money(vat_total_xml)
                gross_total = _quantize_money(net_total + vat_total)
            elif gross_total_xml > Decimal("0"):
                gross_total = _quantize_money(gross_total_xml)
                vat_total = _quantize_money(gross_total - net_total)
            elif vat_rate > Decimal("0"):
                vat_total = _quantize_money(net_total * vat_rate / Decimal("100"))
                gross_total = _quantize_money(net_total + vat_total)

    unit_price_net = _quantize_money(net_total / quantity) if quantity > Decimal("0") else Decimal("0")

    return {
        "name": _field_txt(row_el, "P_7", "P_7"),
        "quantity": quantity,
        "unit": _field_txt(row_el, "P_8A", "P_8A") or "szt.",
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


def _resolve_party_element(podmiot_el: etree._Element) -> etree._Element:
    """Zwraca element z danymi identyfikacyjnymi (FA(3) prod. lub legacy wrapper)."""
    dane = podmiot_el.find(f".//{{{_NS}}}DaneIdentyfikacyjne")
    if dane is not None:
        return dane
    for wrapper_tag in ("Sprzedawca", "Nabywca"):
        wrapper = _first_child_by_local_name(podmiot_el, wrapper_tag)
        if wrapper is not None:
            return wrapper
    return podmiot_el


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

    sprzedawca_el = _resolve_party_element(podmiot1)
    nabywca_el = _resolve_party_element(podmiot2)
    return fa_el, sprzedawca_el, nabywca_el


def _extract_basic_fields(fa_el: etree._Element) -> tuple[str, str, str, str]:
    issue_date_txt = _txt(_find(fa_el, "fa:P_1"))
    # FA(3): P_6 = data dostawy/wykonania usługi; P_1M = miejscowość wystawienia (nie data).
    sale_date_txt = _txt(_find(fa_el, "fa:P_6")) or issue_date_txt
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


def _extract_payment_method(fa_el: etree._Element) -> str | None:
    for element in fa_el.iter():
        if _local_name(element) != "FormaPlatnosci":
            continue
        code = (_txt(element) or "").strip()
        if code == "1":
            return "cash"
        if code == "6":
            return "transfer"
    return None


def _extract_due_date(fa_el: etree._Element) -> str | None:
    direct = (
        _txt(_find(fa_el, "fa:TerminPlatnosci"))
        or _txt(_find(fa_el, "fa:DataPlatnosci"))
    )
    if direct:
        return direct

    for element in fa_el.iter():
        if _local_name(element) not in {"Platnosc", "WarunkiPlatnosci", "TerminyPlatnosci"}:
            continue
        for candidate in element.iter():
            if _local_name(candidate) in {"Termin", "TerminPlatnosci", "DataPlatnosci"}:
                value = _txt(candidate)
                if value:
                    return value

    return None


def _extract_invoice_type(fa_el: etree._Element) -> str:
    rodzaj = _txt(_find(fa_el, "fa:RodzajFaktury")) or "VAT"
    return rodzaj


def _findall_fawiersz(fa_el: etree._Element) -> list[etree._Element]:
    rows = _findall(fa_el, "fa:FaWiersz")
    if rows:
        return rows
    return [child for child in fa_el if _local_name(child) == "FaWiersz"]


def parsed_item_has_nonzero_amounts(item: dict[str, Any]) -> bool:
    for key in ("net_total", "vat_total", "gross_total"):
        if Decimal(str(item.get(key, 0))) > Decimal("0"):
            return True
    return False


def parsed_invoice_has_nonzero_items(parsed: dict[str, Any]) -> bool:
    items = parsed.get("items") or []
    return any(parsed_item_has_nonzero_amounts(item) for item in items)


def purchase_items_validation_error(parsed: dict[str, Any]) -> str | None:
    """Zwraca komunikat błędu gdy nagłówek ma brutto, a pozycje są puste/zerowe."""
    total_gross = Decimal(str(parsed.get("total_gross", 0)))
    if total_gross <= Decimal("0"):
        return None
    if parsed_invoice_has_nonzero_items(parsed):
        return None
    return (
        f"total_gross={total_gross} bez niezerowych pozycji "
        f"(items={len(parsed.get('items') or [])})"
    )


def purchase_seller_city_validation_error(parsed: dict[str, Any]) -> str | None:
    """Integralność: źródło ma miejscowość sprzedawcy, a snapshot.city jest puste."""
    meta = parsed.get("_seller_address_raw") or {}
    return purchase_seller_city_integrity_error(
        seller_snapshot=parsed.get("seller_snapshot") or {},
        adres_l1=str(meta.get("adres_l1") or ""),
        adres_l2=str(meta.get("adres_l2") or ""),
        structured_city_present_in_xml=bool(meta.get("structured_city")),
    )


def _parse_items(fa_el: etree._Element) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for idx, row_el in enumerate(_findall_fawiersz(fa_el), start=1):
        try:
            items.append(_parse_item(row_el, idx))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Błąd parsowania pozycji %d: %s", idx, exc)
    return items


def _sum_item_totals(items: list[dict[str, Any]]) -> tuple[Decimal, Decimal, Decimal]:
    net = Decimal("0")
    vat = Decimal("0")
    gross = Decimal("0")
    for item in items:
        net += Decimal(str(item.get("net_total", 0)))
        vat += Decimal(str(item.get("vat_total", 0)))
        gross += Decimal(str(item.get("gross_total", 0)))
    return _quantize_money(net), _quantize_money(vat), _quantize_money(gross)


def _resolve_totals_with_item_fallback(
    total_net: Decimal,
    total_vat: Decimal,
    total_gross: Decimal,
    items: list[dict[str, Any]],
) -> tuple[Decimal, Decimal, Decimal]:
    """Uzupełnia net/VAT/brutto z pozycji, gdy nagłówek FA(3) nie ma P_13/P_14."""
    if not items:
        return total_net, total_vat, total_gross

    items_net, items_vat, items_gross = _sum_item_totals(items)
    has_item_amounts = (
        items_net > Decimal("0") or items_vat > Decimal("0") or items_gross > Decimal("0")
    )
    if not has_item_amounts:
        return total_net, total_vat, total_gross

    header_has_net_vat = total_net > Decimal("0") or total_vat > Decimal("0")

    if not header_has_net_vat:
        if items_net > Decimal("0"):
            total_net = items_net
        if items_vat > Decimal("0"):
            total_vat = items_vat
        elif total_gross > Decimal("0") and total_net > Decimal("0"):
            total_vat = _quantize_money(total_gross - total_net)
        if total_gross == Decimal("0") and items_gross > Decimal("0"):
            total_gross = items_gross
    elif total_gross > Decimal("0") and total_net == Decimal("0") and items_net > Decimal("0"):
        total_net = items_net
        if items_vat > Decimal("0"):
            total_vat = items_vat
        elif total_gross > total_net:
            total_vat = _quantize_money(total_gross - total_net)

    if total_gross == Decimal("0") and total_net > Decimal("0"):
        total_gross = _quantize_money(total_net + total_vat)

    return total_net, total_vat, total_gross


def _build_parsed_invoice_payload(
    fa_el: etree._Element,
    seller_snapshot: dict[str, Any],
    buyer_snapshot: dict[str, Any],
) -> dict[str, Any]:
    issue_date_txt, sale_date_txt, number_local, currency = _extract_basic_fields(fa_el)
    if not issue_date_txt:
        raise ValueError("Brak daty wystawienia (P_1) w dokumencie FA(3)")

    total_net, total_vat, total_gross = _extract_totals(fa_el)
    items = _parse_items(fa_el)
    total_net, total_vat, total_gross = _resolve_totals_with_item_fallback(
        total_net, total_vat, total_gross, items
    )
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
        "items": items,
        **_extract_annotations(fa_el),
        "exchange_rate": exchange_rate,
        "exchange_rate_date": exchange_rate_date,
        "due_date": _extract_due_date(fa_el),
        "payment_method": _extract_payment_method(fa_el),
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
    payload = _build_parsed_invoice_payload(
        fa_el=fa_el,
        seller_snapshot=seller_snapshot,
        buyer_snapshot=buyer_snapshot,
    )
    l1, l2, structured_city = _raw_adres_lines(sprzedawca_el)
    payload["_seller_address_raw"] = {
        "adres_l1": l1,
        "adres_l2": l2,
        "structured_city": structured_city,
    }
    return payload
