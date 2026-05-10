from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.models.ksef_sync_state import KSeFSyncStateORM


class KSeFSyncStateRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create(self, scope: str) -> KSeFSyncStateORM:
        stmt = select(KSeFSyncStateORM).where(KSeFSyncStateORM.scope == scope)
        orm = self.session.execute(stmt).scalar_one_or_none()
        if orm is not None:
            return orm

        orm = KSeFSyncStateORM(scope=scope, status="idle")
        self.session.add(orm)
        self.session.flush()
        return orm

    def mark_running(self, scope: str) -> KSeFSyncStateORM:
        orm = self.get_or_create(scope)
        orm.status = "running"
        orm.last_attempt_at = datetime.now(UTC)
        orm.last_error = None
        self.session.flush()
        return orm

    def mark_success(self, scope: str, state_json: dict | None = None) -> KSeFSyncStateORM:
        orm = self.get_or_create(scope)
        now = datetime.now(UTC)
        orm.status = "success"
        orm.last_success_at = now
        orm.last_attempt_at = now
        orm.last_error = None
        if state_json is not None:
            orm.state_json = state_json
        self.session.flush()
        return orm

    def mark_error(self, scope: str, error: str) -> KSeFSyncStateORM:
        orm = self.get_or_create(scope)
        orm.status = "error"
        orm.last_attempt_at = datetime.now(UTC)
        orm.last_error = (error or "")[:1024]
        self.session.flush()
        return orm
