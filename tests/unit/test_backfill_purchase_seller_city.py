"""Testy backfill seller city — klasyfikacja i idempotencja (bez DB)."""

from __future__ import annotations

from app.integrations.ksef.fa3_address import extract_city_only_from_stored_address_fields


def test_backfill_dry_classification_patterns_from_production_samples() -> None:
    samples = [
        ("ul. Puławska 2 02-566 Warszawa", "", "Warszawa"),
        ("Wynalazek 1", "02-677 Warszawa", "Warszawa"),
        ("Ks. Bp.K. Dominika 11, 83-130 Pelplin", "", "Pelplin"),
        ("UL. SZOSA GDAŃSKA 3, 86031 OSIELSKO", "", "OSIELSKO"),
        ("Sufczyn 480", "Sufczyn, 32-852 Biadoliny Sufczyn", "Biadoliny Sufczyn"),
        ("Only street", "", None),
    ]
    for street, apt, expected in samples:
        got = extract_city_only_from_stored_address_fields(
            street=street,
            apartment_no=apt,
            city="",
        )
        assert got == expected, (street, apt, got, expected)


def test_backfill_extract_city_city_before_postal() -> None:
    assert (
        extract_city_only_from_stored_address_fields(
            street="Sępia 13, Bydgoszcz 85-434",
            city="",
        )
        == "Bydgoszcz"
    )
    assert (
        extract_city_only_from_stored_address_fields(
            street="ul. Ostróżki 12",
            apartment_no="BIAŁE BŁOTA, 86-005",
            city="",
        )
        == "BIAŁE BŁOTA"
    )
    assert (
        extract_city_only_from_stored_address_fields(
            street="ul. Kolonijna 3",
            apartment_no="Osielsko, 86-031",
            city="",
        )
        == "Osielsko"
    )
