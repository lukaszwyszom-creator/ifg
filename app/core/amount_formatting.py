from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

TWOPLACES = Decimal('0.01')
EXCEL_PLN_NUMBER_FORMAT = '# ##0,00 "zł"'
EXCEL_NUMBER_FORMAT = '# ##0,00'


def _to_decimal(value: object) -> Decimal:
    if value is None or value == '':
        return Decimal('0.00')
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def format_pln_amount(value: object) -> str:
    amount = _to_decimal(value).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    sign = '-' if amount < 0 else ''
    abs_amount = abs(amount)
    grouped = f"{abs_amount:,.2f}".replace(',', ' ').replace('.', ',')
    return f'{sign}{grouped} zł'
