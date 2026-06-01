from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.models.warehouse_item import WarehouseItemORM


class WarehouseItemRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, item_id: UUID) -> WarehouseItemORM | None:
        return self.session.get(WarehouseItemORM, item_id)

    def list_all(self, include_inactive: bool = False) -> list[WarehouseItemORM]:
        query = select(WarehouseItemORM)
        if not include_inactive:
            query = query.where(WarehouseItemORM.is_active.is_(True))
        query = query.order_by(WarehouseItemORM.name)
        return list(self.session.execute(query).scalars().all())

    def add(self, item: WarehouseItemORM) -> WarehouseItemORM:
        self.session.add(item)
        self.session.flush()
        return item

    def save(self, item: WarehouseItemORM) -> WarehouseItemORM:
        self.session.add(item)
        self.session.flush()
        return item
