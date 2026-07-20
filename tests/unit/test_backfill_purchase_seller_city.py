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


def test_backfill_second_pass_no_change_when_city_set() -> None:
    assert (
        extract_city_only_from_stored_address_fields(
            street="ul. Puławska 2 02-566 Warszawa",
            city="Warszawa",
        )
        == "Warszawa"
    )
