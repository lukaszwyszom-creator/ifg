from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import uuid4

from app.domain.enums import InvoiceStatus
from app.domain.models.invoice import Invoice, calculate_overdue_days
from app.services.invoice_service import InvoiceService
from app.services.ksef_session_service import KSeFSessionService
from app.services.ksef_sync_service import KSeFSyncService
from app.services.payment_service import PaymentService
from app.services.settings_service import SettingsService

_TWO_PLACES = Decimal("0.01")
_DASHBOARD_INVOICE_PAGE_SIZE = 1000


class MobileService:
    """Agreguje dane mobilne z istniejących serwisów IFG (bez własnej logiki biznesowej)."""

    def __init__(
        self,
        invoice_service: InvoiceService,
        payment_service: PaymentService,
        ksef_sync_service: KSeFSyncService,
        ksef_session_service: KSeFSessionService,
        settings_service: SettingsService,
    ) -> None:
        self._invoice_service = invoice_service
        self._payment_service = payment_service
        self._ksef_sync_service = ksef_sync_service
        self._ksef_session_service = ksef_session_service
        self._settings_service = settings_service

    def get_dashboard(self, period: str | None = None) -> dict[str, Any]:
        resolved_period, period_from, period_before = self._resolve_period(period)

        sales_net, sales_vat = self._sum_period_invoices(
            direction="sale",
            issue_date_from=period_from,
            issue_date_before=period_before,
        )
        purchase_net, purchase_vat = self._sum_period_invoices(
            direction="purchase",
            issue_date_from=period_from,
            issue_date_before=period_before,
        )
        vat_balance = (sales_vat - purchase_vat).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
        vat_label = "due" if vat_balance >= Decimal("0") else "refund"

        settlements = self._payment_service.get_settlement_summary(side="all", month=None)
        debtors_count, debtors_total, debtors_overdue = self._settlement_metrics(
            settlements.get("debtors", [])
        )
        creditors_count, creditors_total, creditors_overdue = self._settlement_metrics(
            settlements.get("creditors", [])
        )

        unassigned_count, unassigned_total = self._unassigned_payments_summary()

        sync_status = self._ksef_sync_service.get_sync_status()
        ksef_last_sync_at = sync_status.get("last_success_at")
        ksef_new_count = self._extract_ksef_new_invoices_count(sync_status)
        ksef_connection_status = self._resolve_ksef_connection_status()

        notifications = self._build_notification_items()
        recent_purchases = self._recent_purchase_invoices(period_from, period_before)

        return {
            "period": resolved_period,
            "sales_net": sales_net,
            "purchase_net": purchase_net,
            "vat_balance": vat_balance,
            "vat_label": vat_label,
            "debtors_count": debtors_count,
            "debtors_total_due": debtors_total,
            "debtors_overdue_due": debtors_overdue,
            "creditors_count": creditors_count,
            "creditors_total_due": creditors_total,
            "creditors_overdue_due": creditors_overdue,
            "unassigned_payments_count": unassigned_count,
            "unassigned_payments_total": unassigned_total,
            "ksef_new_invoices_count": ksef_new_count,
            "ksef_last_sync_at": ksef_last_sync_at,
            "ksef_connection_status": ksef_connection_status,
            "notifications_active_count": len(notifications),
            "recent_purchase_invoices": recent_purchases,
        }

    def get_notifications(self) -> dict[str, Any]:
        return {"items": self._build_notification_items()}

    def _build_notification_items(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        now = datetime.now(UTC)

        unassigned_count, unassigned_total = self._unassigned_payments_summary()
        if unassigned_count > 0:
            items.append(
                {
                    "id": uuid4(),
                    "type": "payment_unassigned",
                    "title": "Płatności do przypisania",
                    "subtitle": self._format_count_amount_subtitle(
                        unassigned_count, unassigned_total, "transakcje"
                    ),
                    "count": unassigned_count,
                    "created_at": now,
                    "target_type": "unassigned_payments",
                    "target_id": None,
                }
            )

        sync_status = self._ksef_sync_service.get_sync_status()
        sync_state_status = (sync_status.get("status") or "").lower()
        last_error = sync_status.get("last_error")
        if sync_state_status == "error" or last_error:
            items.append(
                {
                    "id": uuid4(),
                    "type": "ksef_sync_error",
                    "title": "Błąd synchronizacji KSeF",
                    "subtitle": (str(last_error)[:120] if last_error else "Sprawdź połączenie KSeF"),
                    "count": 1,
                    "created_at": sync_status.get("last_attempt_at") or now,
                    "target_type": "ksef",
                    "target_id": None,
                }
            )

        settlements = self._payment_service.get_settlement_summary(side="all", month=None)
        overdue_debtors = self._count_overdue_rows(settlements.get("debtors", []))
        if overdue_debtors > 0:
            overdue_debtors_total = self._sum_overdue_rows(settlements.get("debtors", []))
            items.append(
                {
                    "id": uuid4(),
                    "type": "debtor_overdue",
                    "title": "Przeterminowane należności",
                    "subtitle": self._format_count_amount_subtitle(
                        overdue_debtors, overdue_debtors_total, "faktury"
                    ),
                    "count": overdue_debtors,
                    "created_at": now,
                    "target_type": "debtors",
                    "target_id": None,
                }
            )

        overdue_creditors = self._count_overdue_rows(settlements.get("creditors", []))
        if overdue_creditors > 0:
            overdue_creditors_total = self._sum_overdue_rows(settlements.get("creditors", []))
            items.append(
                {
                    "id": uuid4(),
                    "type": "creditor_overdue",
                    "title": "Przeterminowane zobowiązania",
                    "subtitle": self._format_count_amount_subtitle(
                        overdue_creditors, overdue_creditors_total, "faktury"
                    ),
                    "count": overdue_creditors,
                    "created_at": now,
                    "target_type": "creditors",
                    "target_id": None,
                }
            )

        # TODO(etap2): ksef_new_invoice — powiadomienie o nowych fakturach zakupowych w okresie

        return items

    @staticmethod
    def _resolve_period(period: str | None) -> tuple[str, date, date]:
        if period:
            year, month = (int(part) for part in period.split("-"))
        else:
            today = date.today()
            year, month = today.year, today.month
            period = f"{year:04d}-{month:02d}"

        period_from = date(year, month, 1)
        if month == 12:
            period_before = date(year + 1, 1, 1)
        else:
            period_before = date(year, month + 1, 1)
        return period, period_from, period_before

    def _sum_period_invoices(
        self,
        *,
        direction: str,
        issue_date_from: date,
        issue_date_before: date,
    ) -> tuple[Decimal, Decimal]:
        invoices, _total = self._invoice_service.list_invoices(
            direction=direction,
            page=1,
            size=_DASHBOARD_INVOICE_PAGE_SIZE,
            issue_date_from=issue_date_from,
            issue_date_before=issue_date_before,
        )
        # TODO(etap2): paginacja gdy faktur w miesiącu > _DASHBOARD_INVOICE_PAGE_SIZE
        net_total = Decimal("0")
        vat_total = Decimal("0")
        for invoice in invoices:
            if invoice.status == InvoiceStatus.REJECTED:
                continue
            if invoice.currency != "PLN":
                continue
            net_total += invoice.total_net
            vat_total += invoice.total_vat
        return (
            net_total.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP),
            vat_total.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP),
        )

    def _recent_purchase_invoices(
        self,
        issue_date_from: date,
        issue_date_before: date,
    ) -> list[dict[str, Any]]:
        invoices, _total = self._invoice_service.list_invoices(
            direction="purchase",
            page=1,
            size=3,
            issue_date_from=issue_date_from,
            issue_date_before=issue_date_before,
        )
        recent: list[dict[str, Any]] = []
        for invoice in invoices:
            recent.append(
                {
                    "id": invoice.id,
                    "supplier_name": self._supplier_name(invoice),
                    "number": invoice.number_local or invoice.ksef_reference_number or "",
                    "amount_gross": invoice.total_gross.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP),
                    "issue_date": invoice.issue_date,
                }
            )
        return recent

    @staticmethod
    def _supplier_name(invoice: Invoice) -> str:
        seller = invoice.seller_snapshot or {}
        name = seller.get("name") if isinstance(seller, dict) else None
        return str(name).strip() if name else "Nieznany dostawca"

    def _unassigned_payments_summary(self) -> tuple[int, Decimal]:
        rows, total = self._payment_service.list_transactions(
            page=1,
            size=500,
            match_status=None,
        )
        amount = Decimal("0")
        for row in rows:
            remaining = row.remaining_amount
            if not isinstance(remaining, Decimal):
                remaining = Decimal(str(remaining))
            amount += remaining
        return total, amount.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)

    def _resolve_ksef_connection_status(self) -> str:
        settings_data = self._settings_service.get_settings()
        seller_nip = (settings_data.get("seller_nip") or "").strip() or None
        payload = self._ksef_session_service.get_connection_status(seller_nip)
        ui_status = (payload.get("ui_status") or "").upper()
        if ui_status == "CONNECTED":
            return "connected"
        if ui_status == "ERROR":
            return "error"
        return "disconnected"

    @staticmethod
    def _extract_ksef_new_invoices_count(sync_status: dict[str, Any]) -> int:
        state_json = sync_status.get("state_json") or {}
        last_counts = state_json.get("last_counts") or {}
        saved = last_counts.get("saved")
        if isinstance(saved, int):
            return saved
        if isinstance(saved, str) and saved.isdigit():
            return int(saved)
        # TODO(etap2): liczba nowych dokumentów KSeF w wybranym okresie (nie tylko ostatni sync)
        return 0

    @staticmethod
    def _settlement_metrics(rows: list[dict[str, Any]]) -> tuple[int, Decimal, Decimal]:
        contractors: set[str] = set()
        total_due = Decimal("0")
        overdue_due = Decimal("0")
        for row in rows:
            name = (row.get("contractor_name") or "").strip() or "?"
            contractors.add(name)
            remaining = MobileService._as_decimal(row.get("remaining_amount"))
            total_due += remaining
            if MobileService._is_overdue(row.get("due_date")):
                overdue_due += remaining
        return (
            len(contractors),
            total_due.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP),
            overdue_due.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP),
        )

    @staticmethod
    def _count_overdue_rows(rows: list[dict[str, Any]]) -> int:
        return sum(1 for row in rows if MobileService._is_overdue(row.get("due_date")))

    @staticmethod
    def _sum_overdue_rows(rows: list[dict[str, Any]]) -> Decimal:
        total = Decimal("0")
        for row in rows:
            if MobileService._is_overdue(row.get("due_date")):
                total += MobileService._as_decimal(row.get("remaining_amount"))
        return total.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)

    @staticmethod
    def _is_overdue(due_date_raw: Any) -> bool:
        due_date = MobileService._as_date(due_date_raw)
        overdue_days = calculate_overdue_days(due_date)
        return overdue_days is not None and overdue_days > 0

    @staticmethod
    def _as_date(value: Any) -> date | None:
        if value is None:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError:
                return None
        return None

    @staticmethod
    def _as_decimal(value: Any) -> Decimal:
        if isinstance(value, Decimal):
            return value
        if value is None:
            return Decimal("0")
        return Decimal(str(value))

    @staticmethod
    def _format_count_amount_subtitle(count: int, amount: Decimal, noun: str) -> str:
        amount_int = int(amount.to_integral_value())
        return f"{count} {noun} · {amount_int:,} zł".replace(",", " ")
