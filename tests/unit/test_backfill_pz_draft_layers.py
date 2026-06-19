"""E2: backfill PZ draft — logika kandydatów i idempotencja (mock session)."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from scripts.backfill_pz_draft_layers import BackfillCandidate, backfill_pz_draft_layers


class TestBackfillLogic:
    def test_dry_run_reports_candidates_without_insert(self):
        cand = BackfillCandidate(
            doc_id=uuid4(),
            doc_item_id=uuid4(),
            item_id=uuid4(),
            quantity=Decimal("5"),
            received_date=datetime(2026, 6, 1, tzinfo=UTC).date(),
        )

        class FakeSession:
            def add(self, _obj):
                raise AssertionError("dry_run must not add")

        from unittest.mock import patch

        with patch(
            "scripts.backfill_pz_draft_layers.fetch_candidates",
            return_value=[cand],
        ):
            result = backfill_pz_draft_layers(
                FakeSession(),  # type: ignore[arg-type]
                dry_run=True,
                batch_id=uuid4(),
            )
        assert result["candidates"] == 1
        assert result["layers_inserted"] == 0

    def test_backfill_empty_candidates_is_noop(self):
        class FakeSession:
            pass

        from unittest.mock import patch

        with patch(
            "scripts.backfill_pz_draft_layers.fetch_candidates",
            return_value=[],
        ):
            result = backfill_pz_draft_layers(
                FakeSession(),  # type: ignore[arg-type]
                dry_run=False,
                batch_id=uuid4(),
            )
        assert result["candidates"] == 0
        assert result["layers_inserted"] == 0

    def test_backfill_execute_adds_layers_and_balance(self):
        item_id = uuid4()
        cand = BackfillCandidate(
            doc_id=uuid4(),
            doc_item_id=uuid4(),
            item_id=item_id,
            quantity=Decimal("7"),
            received_date=datetime(2026, 6, 1, tzinfo=UTC).date(),
        )
        added: list = []
        balances: dict = {}

        class FakeSession:
            def add(self, obj):
                added.append(obj)

            def get(self, model, key):
                from app.persistence.models.warehouse_document import WarehouseBalanceORM

                if model is WarehouseBalanceORM:
                    return balances.get(key)
                return None

        from unittest.mock import patch

        with patch(
            "scripts.backfill_pz_draft_layers.fetch_candidates",
            return_value=[cand],
        ):
            result = backfill_pz_draft_layers(
                FakeSession(),  # type: ignore[arg-type]
                dry_run=False,
                batch_id=uuid4(),
            )

        assert result["layers_inserted"] == 1
        assert len(added) == 2  # layer + balance
        layer = added[0]
        assert layer.purchase_unit_price is None
        assert layer.remaining_quantity == Decimal("7")
        balance = added[1]
        assert balance.quantity_available == Decimal("7")

    def test_backfill_idempotent_when_no_candidates(self):
        class FakeSession:
            def add(self, _obj):
                raise AssertionError("no candidates => no add")

        from unittest.mock import patch

        with patch(
            "scripts.backfill_pz_draft_layers.fetch_candidates",
            return_value=[],
        ):
            r1 = backfill_pz_draft_layers(
                FakeSession(),  # type: ignore[arg-type]
                dry_run=False,
                batch_id=uuid4(),
            )
            r2 = backfill_pz_draft_layers(
                FakeSession(),  # type: ignore[arg-type]
                dry_run=False,
                batch_id=uuid4(),
            )
        assert r1["candidates"] == 0
        assert r2["candidates"] == 0
