from decimal import Decimal

from app.core.amount_formatting import format_pln_amount


def test_format_pln_amount_expected_values() -> None:
    cases = [
        (0, '0,00 zł'),
        (1, '1,00 zł'),
        (12.3, '12,30 zł'),
        (999.99, '999,99 zł'),
        (1000, '1 000,00 zł'),
        (123456.7, '123 456,70 zł'),
        (1234567.89, '1 234 567,89 zł'),
        (Decimal('1234567.895'), '1 234 567,90 zł'),
    ]

    for value, expected in cases:
        assert format_pln_amount(value) == expected


def test_format_pln_amount_handles_negative() -> None:
    assert format_pln_amount(Decimal('-1200.5')) == '-1 200,50 zł'
