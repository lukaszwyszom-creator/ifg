"""Adres strony faktury → linia FA(3) AdresL1.

KSeF FA(3) wymaga wolnego tekstu AdresL1, nie osobnego pola „ulica”.
REGON bywa niepełny (miejscowość + kod bez ulicy / z samym numerem).
"""

from __future__ import annotations


def _strip(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    # REGON/JSON czasem wstawia literały zamiast pustki
    if text.lower() in {"none", "null", "undefined"}:
        return ""
    return text


def format_adres_l1(snapshot: dict | None) -> str:
    """Składa AdresL1 z pól snapshotu (street/building/postal/city lub address)."""
    snap = snapshot or {}
    address_text = _strip(snap.get("address"))
    if address_text:
        return address_text

    street = _strip(snap.get("street"))
    building_no = _strip(snap.get("building_no"))
    apartment_no = _strip(snap.get("apartment_no"))
    postal_code = _strip(snap.get("postal_code"))
    city = _strip(snap.get("city"))

    if street:
        street_line = " ".join(part for part in (street, building_no) if part)
    elif building_no and city:
        # Adres wiejski / bez ulicy: „Prusicko 10”
        street_line = f"{city} {building_no}"
    elif building_no:
        street_line = building_no
    else:
        street_line = ""

    if apartment_no:
        street_line = f"{street_line} m. {apartment_no}".strip()

    city_line = " ".join(part for part in (postal_code, city) if part)

    if street_line and city_line:
        return f"{street_line}, {city_line}"
    return street_line or city_line or "-"


def can_build_adres_l1(snapshot: dict | None) -> bool:
    """True, gdy da się zbudować sensowną linię AdresL1 (bez wymogu pola street)."""
    snap = snapshot or {}
    if _strip(snap.get("address")):
        return True

    street = _strip(snap.get("street"))
    building_no = _strip(snap.get("building_no"))
    apartment_no = _strip(snap.get("apartment_no"))
    postal_code = _strip(snap.get("postal_code"))
    city = _strip(snap.get("city"))

    has_place_line = bool(street or building_no or apartment_no)
    has_locality = bool(postal_code and city)
    if not (has_place_line and has_locality):
        return False

    # format_adres_l1 musi zwrócić coś innego niż placeholder
    return format_adres_l1(snap) not in {"", "-"}
