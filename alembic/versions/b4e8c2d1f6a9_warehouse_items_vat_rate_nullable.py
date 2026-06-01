"""warehouse_items_vat_rate_nullable

Revision ID: b4e8c2d1f6a9
Revises: a3f9b1c2d5e8
Create Date: 2026-05-22 20:00:00.000000

Zmiany:
  warehouse_items.vat_rate — nullable, bez server_default=23.
  VAT ustawiany wyłącznie przy zaksięgowaniu PZ.

TODO (data cleanup, opcjonalnie ręcznie):
  Istniejące pozycje mogą mieć vat_rate=23 z poprzedniego server_default
  mimo braku zaksięgowanego PZ. Nie masowo zerujemy — brak jednoznacznego
  kryterium (default_price_net IS NULL sugeruje brak PZ, ale starsze dane
  mogły mieć ręcznie ustawiony VAT przed blokadą edycji w kartotece).
  Docelowo: UPDATE warehouse_items SET vat_rate = NULL WHERE default_price_net IS NULL;
"""

import sqlalchemy as sa
from alembic import op

revision = "b4e8c2d1f6a9"
down_revision = "a3f9b1c2d5e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "warehouse_items",
        "vat_rate",
        existing_type=sa.Numeric(5, 2),
        nullable=True,
        server_default=None,
    )


def downgrade() -> None:
    op.execute(sa.text("UPDATE warehouse_items SET vat_rate = 23 WHERE vat_rate IS NULL"))
    op.alter_column(
        "warehouse_items",
        "vat_rate",
        existing_type=sa.Numeric(5, 2),
        nullable=False,
        server_default="23",
    )
