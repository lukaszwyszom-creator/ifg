"""Kalkulacje finansowe dla faktur (czyste, bez I/O).

Wydzielone z `invoice_service.py` aby oddzielić logikę finansową
(item-level oraz totals nagłówka) od orchestration faktury.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.domain.exceptions import InvalidInvoiceError
from app.domain.models.invoice import InvoiceItem

_TWO_PLACES = Decimal("0.01")


def _q(value: Decimal) -> Decimal:
    return value.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


class InvoiceTotalsCalculator:
    """Pure-functions: brak dostępu do DB, brak stanu."""

    @staticmethod
    def calculate_line_amounts(
        *,
        quantity: Decimal,
        vat_rate: Decimal,
        price_mode: str = "net",
        unit_price_net: Decimal | None = None,
        unit_price_gross: Decimal | None = None,
        line_gross_total: Decimal | None = None,
    ) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        """Wylicza kwoty pozycji. Zwraca unit_price_net, net_total, vat_total, gross_total."""
        unit_price_net = unit_price_net or Decimal("0")
        unit_price_gross = unit_price_gross or Decimal("0")
        line_gross_total = line_gross_total or Decimal("0")

        if price_mode == "gross":
            if line_gross_total > Decimal("0"):
                gross_total = _q(line_gross_total)
            elif unit_price_gross > Decimal("0"):
                gross_total = _q(quantity * unit_price_gross)
            else:
                raise InvalidInvoiceError(
                    "Tryb ceny brutto wymaga unit_price_gross lub kwoty brutto pozycji."
                )

            if vat_rate > Decimal("0"):
                net_total = _q(gross_total / (Decimal("1") + vat_rate / Decimal("100")))
            else:
                net_total = gross_total
            vat_total = _q(gross_total - net_total)
            stored_unit_net = _q(net_total / quantity) if quantity > Decimal("0") else Decimal("0")
            return stored_unit_net, net_total, vat_total, gross_total

        if unit_price_net < Decimal("0"):
            raise InvalidInvoiceError("Cena jednostkowa netto nie może być ujemna.")

        net_total = _q(quantity * unit_price_net)
        vat_total = _q(net_total * vat_rate / Decimal("100"))
        gross_total = _q(net_total + vat_total)
        return unit_price_net, net_total, vat_total, gross_total

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
            vat_rate = Decimal(str(raw["vat_rate"]))
            price_mode = str(raw.get("price_mode") or "net").lower()

            if quantity <= 0:
                raise InvalidInvoiceError(
                    f"Pozycja {idx + 1}: ilość musi być większa od zera."
                )
            if quantity != quantity.to_integral_value():
                raise InvalidInvoiceError(
                    f"Pozycja {idx + 1}: ilość musi być liczbą całkowitą."
                )
            if vat_rate < 0 or vat_rate > 100:
                raise InvalidInvoiceError(
                    f"Pozycja {idx + 1}: stawka VAT musi być w zakresie 0–100."
                )

            unit_price_net = Decimal(str(raw.get("unit_price_net") or 0))
            unit_price_gross = Decimal(str(raw.get("unit_price_gross") or 0))

            if price_mode == "gross":
                if unit_price_gross <= Decimal("0") and unit_price_net > Decimal("0"):
                    unit_price_gross = unit_price_net
                if unit_price_gross < Decimal("0"):
                    raise InvalidInvoiceError(
                        f"Pozycja {idx + 1}: cena jednostkowa brutto nie może być ujemna."
                    )
            elif unit_price_net < Decimal("0"):
                raise InvalidInvoiceError(
                    f"Pozycja {idx + 1}: cena jednostkowa nie może być ujemna."
                )

            stored_unit_net, net_total, vat_total, gross_total = (
                InvoiceTotalsCalculator.calculate_line_amounts(
                    quantity=quantity,
                    vat_rate=vat_rate,
                    price_mode=price_mode,
                    unit_price_net=unit_price_net,
                    unit_price_gross=unit_price_gross,
                )
            )

            items.append(
                InvoiceItem(
                    name=name,
                    quantity=quantity,
                    unit=raw.get("unit", "szt."),
                    unit_price_net=stored_unit_net,
                    vat_rate=vat_rate,
                    net_total=net_total,
                    vat_total=vat_total,
                    gross_total=gross_total,
                    sort_order=idx + 1,
                    isbn=raw.get("isbn") or None,
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
            _q(Decimal(str(total_net))),
            _q(Decimal(str(total_vat))),
            _q(Decimal(str(total_gross))),
        )
