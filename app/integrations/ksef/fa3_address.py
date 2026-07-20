"""FA(3) TAdres → ustrukturyzowany snapshot adresu.

FA(3) (`TAdres` w fa3.xsd) NIE ma elementów ``Miejscowosc`` / ``KodPocztowy`` / ``Ulica``.
Adres to wolny tekst ``AdresL1`` (+ opcjonalnie ``AdresL2``).

IFG przy eksporcie składa AdresL1 jako: ``{street}, {postal} {city}``
(``mapper._format_adres_l1``). Import musi wykonać odwrotne, kanoniczne mapowanie
do pól ``street`` / ``postal_code`` / ``city`` — to nie jest fallback UI ani
„wycinanie z ulicy” po zapisie, tylko poprawne odwzorowanie schematu FA(3).

Gdy w XML występują legacy/nieściśle elementy ``Miejscowosc`` / ``KodPocztowy`` /
``Ulica``, mają pierwszeństwo przed rozbiorem AdresL1/L2.
"""

from __future__ import annotations

import re
from typing import Any

# Kod pocztowy PL: XX-XXX lub XXXXX, potem miejscowość do końca segmentu.
_POSTAL_CITY_RE = re.compile(
    r"(?P<postal>\d{2}-\d{3}|\d{5})\s+(?P<city>.+?)\s*$",
    re.UNICODE,
)


def normalize_pl_postal_code(raw: str) -> str:
    postal = (raw or "").strip()
    if len(postal) == 5 and postal.isdigit():
        return f"{postal[:2]}-{postal[2:]}"
    return postal


def extract_postal_city_from_address_text(text: str) -> tuple[str, str] | None:
    """Zwraca ``(postal_code, city)`` gdy tekst kończy się wzorcem PL kod+miasto."""
    cleaned = (text or "").strip().strip(",;")
    if not cleaned:
        return None
    match = _POSTAL_CITY_RE.search(cleaned)
    if not match:
        return None
    postal = normalize_pl_postal_code(match.group("postal"))
    city = (match.group("city") or "").strip(" ,;")
    if not city:
        return None
    return postal, city


def strip_postal_city_suffix(text: str, postal: str, city: str) -> str:
    """Usuwa z końca linii fragment ``postal city`` (i zbędne przecinki)."""
    raw = (text or "").strip()
    if not raw:
        return ""
    # Spróbuj odciąć dokładny suffix; fallback: regex na końcu.
    variants = [
        f"{postal} {city}",
        f"{postal.replace('-', '')} {city}" if "-" in postal else None,
    ]
    result = raw
    for variant in variants:
        if not variant:
            continue
        if result.endswith(variant):
            result = result[: -len(variant)].rstrip(" ,;")
            return result
    match = _POSTAL_CITY_RE.search(result)
    if match:
        result = result[: match.start()].rstrip(" ,;")
    return result


def split_fa3_address_lines(
    *,
    adres_l1: str = "",
    adres_l2: str = "",
    structured_street: str = "",
    structured_postal: str = "",
    structured_city: str = "",
    structured_apartment: str = "",
    country: str = "PL",
) -> dict[str, str]:
    """Buduje ustrukturyzowany adres z pól FA(3) / legacy.

    Priorytet city/postal:
    1. structured_city / structured_postal (Miejscowosc / KodPocztowy),
    2. AdresL2 (często druga linia = kod + miasto),
    3. AdresL1.
    """
    l1 = (adres_l1 or "").strip()
    l2 = (adres_l2 or "").strip()
    street = (structured_street or "").strip() or l1
    postal = (structured_postal or "").strip()
    city = (structured_city or "").strip()
    apartment = (structured_apartment or "").strip()

    if not city or not postal:
        from_l2 = extract_postal_city_from_address_text(l2)
        from_l1 = extract_postal_city_from_address_text(l1)
        chosen = from_l2 or from_l1
        if chosen:
            found_postal, found_city = chosen
            if not postal:
                postal = found_postal
            if not city:
                city = found_city
            if from_l2 and from_l2 == chosen:
                # L2 było linią kod+miasto, nie nr lokalu.
                apartment = ""
                if not structured_street:
                    street = l1
            elif from_l1 and from_l1 == chosen and not structured_street:
                street = strip_postal_city_suffix(l1, found_postal, found_city)

    if not street and l1:
        street = strip_postal_city_suffix(l1, postal, city) if (postal and city) else l1

    # Gdy L2 nie było kodem+miastem i nie mamy apartment — zostaw L2 tylko jeśli
    # wygląda na lokal (krótki) i city już mamy z L1; w przeciwnym razie ignoruj.
    if l2 and not apartment and city and extract_postal_city_from_address_text(l2) is None:
        if len(l2) <= 24 and not extract_postal_city_from_address_text(l2):
            # Nie przypisuj długich linii adresowych jako apartment_no.
            if re.match(r"^(m\.?|lok\.?|apartment)?\s*\d+", l2, re.IGNORECASE):
                apartment = l2

    return {
        "street": street,
        "building_no": "",
        "apartment_no": apartment,
        "postal_code": normalize_pl_postal_code(postal) if postal else "",
        "city": city,
        "country": (country or "PL").strip() or "PL",
    }


def extract_city_only_from_stored_address_fields(
    *,
    street: str = "",
    apartment_no: str = "",
    postal_code: str = "",
    city: str = "",
) -> str | None:
    """Do backfillu: wylicz city bez zmiany innych pól snapshotu.

    Zwraca nową wartość city albo ``None`` gdy nie da się jednoznacznie odczytać.
    """
    existing = (city or "").strip()
    if existing:
        return existing

    for text in (apartment_no, street):
        found = extract_postal_city_from_address_text(text or "")
        if found:
            return found[1]
    # Gdy postal już jest, a city w street po kodzie:
    postal = (postal_code or "").strip()
    if postal:
        combined = f"{street} {apartment_no}".strip()
        found = extract_postal_city_from_address_text(combined)
        if found:
            return found[1]
    return None


def address_text_implies_city(adres_l1: str = "", adres_l2: str = "") -> bool:
    """True gdy wolny tekst FA(3) zawiera jednoznaczny wzorzec kod+miasto."""
    return (
        extract_postal_city_from_address_text(adres_l2) is not None
        or extract_postal_city_from_address_text(adres_l1) is not None
    )


def purchase_seller_city_integrity_error(
    *,
    seller_snapshot: dict[str, Any],
    adres_l1: str = "",
    adres_l2: str = "",
    structured_city_present_in_xml: bool = False,
) -> str | None:
    """Błąd integralności gdy źródło ma miejscowość, a snapshot.city jest puste.

    Nie blokuje dokumentów bez wyodrębnialnej miejscowości (np. adres zagraniczny
    bez wzorca PL) — tylko gdy źródło jednoznacznie zawiera city.
    """
    city = str((seller_snapshot or {}).get("city") or "").strip()
    if city:
        return None
    if structured_city_present_in_xml or address_text_implies_city(adres_l1, adres_l2):
        return (
            "seller_snapshot.city puste mimo miejscowości w adresie sprzedawcy FA(3) "
            f"(AdresL1/AdresL2 lub Miejscowosc); name={str((seller_snapshot or {}).get('name') or '')[:80]!r}"
        )
    return None
