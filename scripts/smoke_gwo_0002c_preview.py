"""Local preview smoke for GWO-IFG-STOCK-0002C (no DS723)."""
from __future__ import annotations

import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

os.environ.setdefault("JWT_SECRET_KEY", "local-preview-secret-key-32bytes!!")

from app.core.config import settings
from app.core.security import AuthenticatedUser
from app.persistence.models.contractor import ContractorORM
from app.persistence.models.user import UserORM
from app.persistence.models.warehouse_item import WarehouseItemORM
from app.persistence.repositories.audit_repository import AuditRepository
from app.persistence.repositories.contractor_override_repository import (
    ContractorOverrideRepository,
)
from app.persistence.repositories.contractor_repository import ContractorRepository
from app.persistence.repositories.invoice_repository import InvoiceRepository
from app.services.audit_service import AuditService
from app.services.invoice_service import InvoiceService

for key, value in {
    "seller_nip": "1000000035",
    "seller_name": "Sprzedawca Preview",
    "seller_street": "ul. Test",
    "seller_building_no": "1",
    "seller_apartment_no": None,
    "seller_postal_code": "00-001",
    "seller_city": "Warszawa",
    "seller_country": "PL",
}.items():
    object.__setattr__(settings, key, value)


def main() -> None:
    eng = create_engine(os.environ["DATABASE_URL"])
    with Session(eng) as db:
        user = UserORM(
            username=f"prev_{uuid4().hex[:6]}",
            password_hash="x",
            role="administrator",
            is_active=True,
        )
        db.add(user)
        db.flush()
        actor = AuthenticatedUser(
            user_id=str(user.id), username=user.username, role=user.role
        )
        buyer = ContractorORM(
            nip=f"{uuid4().int % 10**10:010d}",
            name="Buyer",
            source="manual",
            street="ul.",
            building_no="1",
            postal_code="00-001",
            city="Wawa",
        )
        db.add(buyer)
        db.flush()
        wi = WarehouseItemORM(
            id=uuid4(),
            name="Preview Towar",
            item_type="goods",
            vat_rate=Decimal("23"),
            unit="szt.",
            is_active=True,
            is_warehouse_active=True,
            suggested_sale_price_mode="net",
        )
        db.add(wi)
        db.flush()

        svc = InvoiceService(
            session=db,
            invoice_repository=InvoiceRepository(db),
            contractor_repository=ContractorRepository(db),
            contractor_override_repository=ContractorOverrideRepository(db),
            audit_service=AuditService(
                session=db, audit_repository=AuditRepository(db)
            ),
        )
        bal0 = db.execute(text("select count(*) from warehouse_balance")).scalar()
        inv = svc.create_invoice(
            {
                "buyer_id": buyer.id,
                "issue_date": date(2026, 8, 4),
                "sale_date": date(2026, 8, 4),
                "due_date": date(2026, 8, 18),
                "payment_method": "transfer",
                "direction": "sale",
                "items": [
                    {
                        "name": "Preview Towar",
                        "quantity": 1,
                        "unit": "szt.",
                        "unit_price_net": "12.00",
                        "vat_rate": "23",
                        "warehouse_item_id": wi.id,
                    }
                ],
            },
            actor,
        )
        inv2 = svc.create_invoice(
            {
                "buyer_id": buyer.id,
                "issue_date": date(2026, 8, 4),
                "sale_date": date(2026, 8, 4),
                "due_date": date(2026, 8, 18),
                "payment_method": "transfer",
                "direction": "sale",
                "items": [
                    {
                        "name": "Reczna",
                        "quantity": 1,
                        "unit": "szt.",
                        "unit_price_net": "5.00",
                        "vat_rate": "23",
                    }
                ],
            },
            actor,
        )
        assert svc.get_invoice(inv.id).items[0].warehouse_item_id == wi.id
        assert svc.get_invoice(inv2.id).items[0].warehouse_item_id is None
        bal1 = db.execute(text("select count(*) from warehouse_balance")).scalar()
        assert bal1 == bal0
        docs = db.execute(text("select count(*) from warehouse_documents")).scalar()
        moves = db.execute(text("select count(*) from stock_movements")).scalar()
        print(
            "SMOKE_OK",
            {
                "invoice_with_fk": str(inv.id),
                "warehouse_item_id": str(wi.id),
                "manual_null": True,
                "warehouse_balance_unchanged": True,
                "warehouse_documents": docs,
                "stock_movements": moves,
            },
        )
        db.commit()


if __name__ == "__main__":
    main()
