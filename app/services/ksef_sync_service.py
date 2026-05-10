from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.persistence.repositories.app_settings_repository import AppSettingsRepository
from app.persistence.repositories.ksef_sync_state_repository import KSeFSyncStateRepository
from app.services.ksef_session_service import KSeFSessionService


_SCOPE_PURCHASE_INVOICES = "purchase_invoices"


class KSeFSyncService:
    def __init__(
        self,
        session: Session,
        sync_state_repository: KSeFSyncStateRepository,
        settings_repository: AppSettingsRepository,
        ksef_session_service: KSeFSessionService,
    ) -> None:
        self.session = session
        self.sync_state_repository = sync_state_repository
        self.settings_repository = settings_repository
        self.ksef_session_service = ksef_session_service

    def get_sync_status(self) -> dict:
        state = self.sync_state_repository.get_or_create(_SCOPE_PURCHASE_INVOICES)
        return self._serialize_state(state)

    def sync_purchase_invoices(
        self,
        force: bool = False,
        actor_user_id: UUID | None = None,
    ) -> dict:
        state = self.sync_state_repository.mark_running(_SCOPE_PURCHASE_INVOICES)
        try:
            nip = self._resolve_seller_nip()
            date_from, date_to = self._resolve_sync_window(state.state_json, force=force)
            counts = self.ksef_session_service.sync_received_invoices(
                nip=nip,
                date_from=date_from,
                date_to=date_to,
                actor_user_id=actor_user_id,
            )
            next_state = {
                "last_date_from": date_from.isoformat(),
                "last_date_to": date_to.isoformat(),
                "last_counts": counts,
            }
            state = self.sync_state_repository.mark_success(
                _SCOPE_PURCHASE_INVOICES,
                state_json=next_state,
            )
            return {
                "counts": counts,
                "status": self._serialize_state(state),
            }
        except Exception as exc:  # noqa: BLE001
            state = self.sync_state_repository.mark_error(_SCOPE_PURCHASE_INVOICES, str(exc))
            self.session.flush()
            raise

    def _resolve_seller_nip(self) -> str:
        settings = self.settings_repository.get()
        seller_nip = (settings.seller_nip if settings is not None else "") or ""
        seller_nip = seller_nip.strip()
        if not seller_nip:
            raise AppError("Brak seller_nip w ustawieniach aplikacji. Ustaw NIP sprzedawcy przed synchronizacją KSeF.")
        return seller_nip

    @staticmethod
    def _resolve_sync_window(state_json: dict | None, force: bool) -> tuple[date, date]:
        date_to = datetime.now(UTC).date()
        if force or not state_json:
            return date_to - timedelta(days=30), date_to

        last_date_to_raw = state_json.get("last_date_to")
        if isinstance(last_date_to_raw, str):
            try:
                last_date_to = date.fromisoformat(last_date_to_raw)
                # Małe nakładanie okna (1 dzień) zwiększa bezpieczeństwo przy opóźnieniach KSeF.
                return max(date_to - timedelta(days=30), last_date_to - timedelta(days=1)), date_to
            except ValueError:
                pass

        return date_to - timedelta(days=30), date_to

    @staticmethod
    def _serialize_state(state) -> dict:
        return {
            "scope": state.scope,
            "status": state.status,
            "last_success_at": state.last_success_at,
            "last_attempt_at": state.last_attempt_at,
            "last_error": state.last_error,
            "state_json": state.state_json,
        }
