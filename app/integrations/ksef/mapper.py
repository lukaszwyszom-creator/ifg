from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from lxml import etree

from app.domain.enums import InvoiceType, PaymentMethod
from app.domain.models.invoice import Invoice, _is_valid_nip
from app.integrations.ksef.exceptions import KSeFMappingError

logger = logging.getLogger(__name__)

# Produkcyjna struktura FA(3) obowiązująca od 2026-02-01 (wzór CRD 13775).
_NS_FA = "http://crd.gov.pl/wzor/2025/06/25/13775/"
_NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"
_NS_MAP = {"fa": _NS_FA, "xsi": _NS_XSI}

_XSD_PATH = Path(__file__).with_name("fa3.xsd")

# Mapowanie stawki VAT na parę pól FA(3): (P_13_x, P_14_x)
# P_14_x = None, gdy brak kwoty podatku (0%, zw., itp.)
_VAT_RATE_FIELDS: dict[str, tuple[str, str | None]] = {
    "23": ("P_13_1", "P_14_1"),
    "8": ("P_13_2", "P_14_2"),
    "5": ("P_13_3", "P_14_3"),
    "0": ("P_13_6_1", None),
    "zw": ("P_13_7", None),
    "np": ("P_13_8", None),
}

_VAT_RATE_FIELDS_PLN: dict[str, str] = {
    "23": "P_14_1W",
    "8": "P_14_2W",
    "5": "P_14_3W",
}

_SCHEMA_VERSION = "3"
_SCHEMA_CODE = "FA"
_FORM_SYSTEM_CODE = "FA (3)"
_FORM_SCHEMA_VERSION = "1-0E"

_PAYMENT_METHOD_FA3: dict[PaymentMethod, str] = {
    PaymentMethod.CASH: "1",
    PaymentMethod.TRANSFER: "6",
}


def _el(parent: etree._Element, tag: str, text: str | None = None) -> etree._Element:
    el = etree.SubElement(parent, f"{{{_NS_FA}}}{tag}")
    if text is not None:
        el.text = str(text)
    return el


def _el_kod_formularza(parent: etree._Element) -> None:
    el = etree.SubElement(parent, f"{{{_NS_FA}}}KodFormularza")
    el.text = _SCHEMA_CODE
    el.set("kodSystemowy", _FORM_SYSTEM_CODE)
    el.set("wersjaSchemy", _FORM_SCHEMA_VERSION)


def _fmt(value) -> str:
    """Formatuje wartość liczbową do 2 miejsc po przecinku."""
    return f"{Decimal(str(value)):.2f}"


def _yn01(flag: bool) -> str:
    """Wartość TWybor1: 1 = tak, 0 = nie."""
    return "1" if flag else "0"


def _yn12(flag: bool) -> str:
    """Wartość TWybor1_2: 1 = tak, 2 = nie."""
    return "1" if flag else "2"


def _rate_key(vat_rate: Decimal) -> str:
    """Zwraca klucz stawki VAT dla tabeli _VAT_RATE_FIELDS."""
    normalized = vat_rate.normalize()
    if normalized == Decimal("0"):
        return "0"
    if normalized == normalized.to_integral_value():
        return str(int(normalized))
    return str(normalized)


def _fmt_line_vat_rate(vat_rate: Decimal) -> str:
    """Format P_12 zgodny z TStawkaPodatku."""
    key = _rate_key(vat_rate)
    if key == "0":
        return "0 KR"
    if key == "zw":
        return "zw"
    return key


def _strip_nip_prefix(nip: str) -> str:
    if nip and len(nip) > 2 and nip[:2].isalpha():
        return nip[2:]
    return nip


def _normalize_nip(raw_nip: str) -> str:
    stripped = _strip_nip_prefix(raw_nip.strip())
    return stripped.replace("-", "").replace(" ", "")


def _format_adres_l1(snapshot: dict) -> str:
    street_line = " ".join(
        filter(None, [snapshot.get("street"), snapshot.get("building_no")])
    )
    if snapshot.get("apartment_no"):
        street_line = f"{street_line} m. {snapshot['apartment_no']}".strip()
    city_line = " ".join(filter(None, [snapshot.get("postal_code"), snapshot.get("city")]))
    if street_line and city_line:
        return f"{street_line}, {city_line}"
    return street_line or city_line or "-"


class FA3Mapper:
    """Transformacja modelu wewnętrznego faktury do formatu KSeF FA(3)."""

    SCHEMA_VERSION = _SCHEMA_VERSION

    @staticmethod
    def invoice_to_xml(invoice: Invoice) -> bytes:
        FA3Mapper._validate_invoice(invoice)
        root = etree.Element(f"{{{_NS_FA}}}Faktura", nsmap=_NS_MAP)

        hdr = _el(root, "Naglowek")
        _el_kod_formularza(hdr)
        _el(hdr, "WariantFormularza", _SCHEMA_VERSION)
        _el(
            hdr,
            "DataWytworzeniaFa",
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        _el(hdr, "SystemInfo", "KSeF-Backend/0.1")

        FA3Mapper._build_podmiot1(root, invoice.seller_snapshot or {})
        FA3Mapper._build_podmiot2(root, invoice.buyer_snapshot or {})

        fa = _el(root, "Fa")
        _el(fa, "KodWaluty", invoice.currency or "PLN")
        _el(fa, "P_1", invoice.issue_date.isoformat())
        _el(fa, "P_2", invoice.number_local or "")

        delivery_date = invoice.delivery_date or invoice.sale_date
        if delivery_date and delivery_date != invoice.issue_date:
            _el(fa, "P_6", delivery_date.isoformat())

        FA3Mapper._build_vat_totals(fa, invoice)
        _el(fa, "P_15", _fmt(invoice.total_gross))

        if invoice.currency != "PLN":
            if invoice.exchange_rate is not None:
                _el(fa, "KursWaluty", _fmt(invoice.exchange_rate))
            if invoice.exchange_rate_date is not None:
                _el(fa, "DataKursuWaluty", invoice.exchange_rate_date.isoformat())

        FA3Mapper._build_adnotacje(fa, invoice)
        _el(fa, "RodzajFaktury", invoice.invoice_type.value)

        if invoice.invoice_type in (InvoiceType.KOR, InvoiceType.KOR_ZAL, InvoiceType.KOR_ROZ):
            FA3Mapper._build_dane_fa_korygowanej(fa, invoice)

        for item in invoice.items:
            row = _el(fa, "FaWiersz")
            _el(row, "NrWierszaFa", str(item.sort_order))
            _el(row, "P_7", item.name)
            _el(row, "P_8A", item.unit)
            _el(row, "P_8B", _fmt(item.quantity))
            _el(row, "P_9A", _fmt(item.unit_price_net))
            _el(row, "P_11", _fmt(item.net_total))
            if item.vat_total > Decimal("0"):
                _el(row, "P_11Vat", _fmt(item.vat_total))
            _el(row, "P_12", _fmt_line_vat_rate(item.vat_rate))

        FA3Mapper._build_platnosc(fa, invoice)

        return etree.tostring(root, encoding="UTF-8", xml_declaration=True)

    @staticmethod
    def xml_content_hash(xml_bytes: bytes) -> str:
        import io

        if not xml_bytes:
            raise KSeFMappingError("Pusty XML — nie można wyliczyć hasha.")
        try:
            root = etree.fromstring(xml_bytes)
        except etree.XMLSyntaxError as exc:
            raise KSeFMappingError(f"XML nie jest poprawny składniowo: {exc}") from exc

        buf = io.BytesIO()
        root.getroottree().write_c14n(buf)
        return hashlib.sha256(buf.getvalue()).hexdigest()

    @staticmethod
    def validate_xml(xml_bytes: bytes) -> bool:
        if not xml_bytes:
            return False
        try:
            root = etree.fromstring(xml_bytes)
        except etree.XMLSyntaxError as exc:
            raise KSeFMappingError(f"XML nie jest poprawny składniowo: {exc}") from exc

        if _XSD_PATH.exists():
            FA3Mapper._validate_against_xsd(root)

        return True

    @staticmethod
    def validate_xml_against_xsd(xml_bytes: bytes) -> None:
        if not xml_bytes:
            raise KSeFMappingError("Pusty XML — brak danych do walidacji XSD.")
        try:
            root = etree.fromstring(xml_bytes)
        except etree.XMLSyntaxError as exc:
            raise KSeFMappingError(f"XML nie jest poprawny składniowo: {exc}") from exc
        FA3Mapper._validate_against_xsd(root)

    @staticmethod
    def _validate_against_xsd(root: etree._Element) -> None:
        if not _XSD_PATH.exists():
            raise KSeFMappingError(
                f"Plik XSD FA(3) nie istnieje: {_XSD_PATH}. "
                "Umieść fa3.xsd w app/integrations/ksef/."
            )
        try:
            xsd_doc = etree.parse(str(_XSD_PATH))
            schema = etree.XMLSchema(xsd_doc)
        except etree.XMLSchemaParseError as exc:
            raise KSeFMappingError(f"Błąd wczytywania XSD: {exc}") from exc

        if not schema.validate(root):
            errors = "; ".join(str(e) for e in schema.error_log)
            raise KSeFMappingError(f"Dokument niezgodny z XSD FA(3): {errors}")

    @staticmethod
    def _build_platnosc(fa: etree._Element, invoice: Invoice) -> None:
        platnosc = _el(fa, "Platnosc")

        if invoice.due_date:
            termin = _el(platnosc, "TerminPlatnosci")
            _el(termin, "Termin", invoice.due_date.isoformat())

        method = invoice.payment_method if isinstance(invoice.payment_method, PaymentMethod) else PaymentMethod.TRANSFER
        fa_code = _PAYMENT_METHOD_FA3.get(method, _PAYMENT_METHOD_FA3[PaymentMethod.TRANSFER])
        _el(platnosc, "FormaPlatnosci", fa_code)

    @staticmethod
    def _build_podmiot1(root: etree._Element, snapshot: dict) -> None:
        podmiot = _el(root, "Podmiot1")
        dane = _el(podmiot, "DaneIdentyfikacyjne")
        raw_nip = snapshot.get("nip") or ""
        _el(dane, "NIP", _normalize_nip(raw_nip))
        _el(dane, "Nazwa", snapshot.get("name") or "")

        adres = _el(podmiot, "Adres")
        country = (snapshot.get("country") or "PL").upper()
        _el(adres, "KodKraju", country)
        _el(adres, "AdresL1", _format_adres_l1(snapshot))

    @staticmethod
    def _build_podmiot2(root: etree._Element, snapshot: dict) -> None:
        podmiot = _el(root, "Podmiot2")
        dane = _el(podmiot, "DaneIdentyfikacyjne")

        raw_id = (snapshot.get("nip") or "").strip().replace("-", "").replace(" ", "")
        country = (snapshot.get("country") or "PL").upper()

        if raw_id and len(raw_id) > 2 and raw_id[:2].isalpha() and raw_id[:2].upper() != "PL":
            _el(dane, "KodUE", raw_id[:2].upper())
            _el(dane, "NrVatUE", raw_id[2:])
        elif raw_id:
            _el(dane, "NIP", _normalize_nip(raw_id))
        else:
            _el(dane, "BrakID", "1")

        if snapshot.get("name"):
            _el(dane, "Nazwa", snapshot["name"])

        if snapshot.get("street") or snapshot.get("city"):
            adres = _el(podmiot, "Adres")
            _el(adres, "KodKraju", country)
            _el(adres, "AdresL1", _format_adres_l1(snapshot))

        _el(podmiot, "JST", "2")
        _el(podmiot, "GV", "2")

    @staticmethod
    def _build_vat_totals(fa: etree._Element, invoice: Invoice) -> None:
        is_foreign = invoice.currency != "PLN"
        totals = invoice.aggregate_vat_totals()

        if not totals:
            _el(fa, "P_13_1", _fmt(invoice.total_net))
            _el(fa, "P_14_1", _fmt(invoice.total_vat))
            return

        for rate_decimal, (net_sum, vat_sum, vat_pln_sum) in sorted(
            totals.items(), key=lambda kv: _rate_key(kv[0])
        ):
            key = _rate_key(rate_decimal)
            fields = _VAT_RATE_FIELDS.get(key)
            if fields is None:
                raise KSeFMappingError(
                    f"Nieznana stawka VAT: {rate_decimal} (klucz: '{key}'). "
                    "Dozwolone: 23, 8, 5, 0, zw, np. "
                    "Zaktualizuj _VAT_RATE_FIELDS lub popraw stawkę w fakturze."
                )
            p13, p14 = fields

            _el(fa, p13, _fmt(net_sum))
            if p14 is not None:
                _el(fa, p14, _fmt(vat_sum))
                if is_foreign:
                    p14w = _VAT_RATE_FIELDS_PLN.get(key)
                    if p14w and vat_pln_sum is not None:
                        _el(fa, p14w, _fmt(vat_pln_sum))

    @staticmethod
    def _build_adnotacje(fa: etree._Element, invoice: Invoice) -> None:
        adnotacje = _el(fa, "Adnotacje")
        _el(adnotacje, "P_16", _yn12(invoice.use_split_payment))
        _el(adnotacje, "P_17", _yn12(invoice.self_billing))
        _el(adnotacje, "P_18", _yn12(invoice.reverse_charge))
        _el(adnotacje, "P_18A", _yn12(invoice.reverse_charge_art))

        if invoice.cash_accounting_method:
            _el(adnotacje, "P_19", "1")

        zwolnienie = _el(adnotacje, "Zwolnienie")
        _el(zwolnienie, "P_19N", "1")

        nst = _el(adnotacje, "NoweSrodkiTransportu")
        _el(nst, "P_22N", "1")

        _el(adnotacje, "P_23", "2")

        pmarzy = _el(adnotacje, "PMarzy")
        _el(pmarzy, "P_PMarzyN", "1")

    @staticmethod
    def _build_dane_fa_korygowanej(fa: etree._Element, invoice: Invoice) -> None:
        if invoice.correction_reason:
            _el(fa, "PrzyczynaKorekty", invoice.correction_reason)

        dane = _el(fa, "DaneFaKorygowanej")
        _el(dane, "DataWystFaKorygowanej", invoice.issue_date.isoformat())
        _el(dane, "NrFaKorygowanej", invoice.number_local or "KOREKTA")

        if invoice.correction_of_ksef_number:
            _el(dane, "NrKSeF", "1")
            _el(dane, "NrKSeFFaKorygowanej", invoice.correction_of_ksef_number)
        else:
            _el(dane, "NrKSeFN", "1")

    @staticmethod
    def _validate_invoice(invoice: Invoice) -> None:
        seller = invoice.seller_snapshot or {}
        raw_nip = seller.get("nip") or ""
        pure_nip = _normalize_nip(raw_nip)
        if not _is_valid_nip(pure_nip):
            raise KSeFMappingError(
                f"NIP sprzedawcy jest nieprawidłowy: '{raw_nip}'. "
                "Wymagane dokładnie 10 cyfr bez separatorów."
            )
        if invoice.direction == "sale" and not (invoice.number_local or "").strip():
            raise KSeFMappingError(
                "Pole P_2 (numer faktury) jest wymagane."
            )
        if not invoice.items:
            raise KSeFMappingError(
                "Faktura nie zawiera pozycji — wymagany co najmniej jeden FaWiersz"
            )
        if invoice.invoice_type in (InvoiceType.KOR, InvoiceType.KOR_ZAL, InvoiceType.KOR_ROZ):
            if not invoice.correction_of_ksef_number and not invoice.correction_of_invoice_id:
                raise KSeFMappingError(
                    "Faktura korygująca wymaga correction_of_ksef_number lub "
                    "correction_of_invoice_id."
                )


KSeFMapper = FA3Mapper
