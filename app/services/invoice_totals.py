"""Kalkulacje finansowe dla faktur (czyste, bez I/O).

Wydzielone z `invoice_service.py` aby oddzielić logikę finansową
(item-level oraz totals nagłówka) od orchestration faktury.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.domain.exceptions import InvalidInvoiceError
from app.domain.models.invoice import InvoiceItem

_TWO_PLACES = Decimal("0.01")


class InvoiceTotalsCalculator:
    """Pure-functions: brak dostępu do DB, brak stanu."""

    @staticmethod
    def build_items(raw_items: list[dict]) -> list[InvoiceItem]:
        items: list[InvoiceItem] = []

        for idx, raw in enumerate(raw_items):
            name = raw["name"].strip()
            if not name:
                raise InvalidInvoiceError(
                    f"Pozycja {idx + 1}: nazwa nie może być pusta."
                )

            quantity = Decimal(str(raw["quantity"]))
            unit_price_net = Decimal(str(raw["unit_price_net"]))
            vat_rate = Decimal(str(raw["vat_rate"]))

            if quantity <= 0:
                raise InvalidInvoiceError(
                    f"Pozycja {idx + 1}: ilość musi być większa od zera."
                )
            if unit_price_net < 0:
                raise InvalidInvoiceError(
                    f"Pozycja {idx + 1}: cena jednostkowa nie może być ujemna."
                )
            if vat_rate < 0 or vat_rate > 100:
                raise InvalidInvoiceError(
                    f"Pozycja {idx + 1}: stawka VAT musi być w zakresie 0–100."
                )

            net_total = (quantity * unit_price_net).quantize(
                _TWO_PLACES, rounding=ROUND_HALF_UP
            )
            vat_total = (net_total * vat_rate / 100).quantize(
                _TWO_PLACES, rounding=ROUND_HALF_UP
            )
            gross_total = net_total + vat_total

            items.append(
                InvoiceItem(
                    name=name,
                    quantity=quantity,
                    unit=raw.get("unit", "szt."),
                    unit_price_net=unit_price_net,
                    vat_rate=vat_rate,
                    net_total=net_total,
                    vat_total=vat_total,
                    gross_total=gross_total,
                    sort_order=idx + 1,
                )
            )

        return items

    @staticmethod
    def calculate_totals(
        items: list[InvoiceItem],
    ) -> tuple[Decimal, Decimal, Decimal]:
        total_net = sum(i.net_total for i in items)
        total_vat = sum(i.vat_total for i in items)
        total_gross = sum(i.gross_total for i in items)
        return (
            Decimal(str(total_net)).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP),
            Decimal(str(total_vat)).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP),
            Decimal(str(total_gross)).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP),
        )
