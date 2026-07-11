from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian.core.deferred_decisions.integrity import (  # noqa: E402
    IntegrityCode,
    compute_next_id,
    dedupe_items,
    propose_repairs,
    validate_store,
)
from ifg_guardian.core.deferred_decisions.locking import (  # noqa: E402
    GddRegistryLock,
    GddRegistryLockError,
)
from ifg_guardian.core.deferred_decisions.models import (  # noqa: E402
    DeferredDecision,
    DeferredDecisionStatus,
    DeferredDecisionStore,
    DeferredDecisionType,
    DeferredPriority,
)
from ifg_guardian.core.deferred_decisions.service import (  # noqa: E402
    AddDecisionResult,
    DeferredDecisionService,
)
from ifg_guardian.core.deferred_decisions.store import (  # noqa: E402
    GddIntegrityError,
    load_store,
    save_store,
)
from ifg_guardian.modules.deferred_decisions import (  # noqa: E402
    run_deferred_repair,
    run_deferred_validate,
)


def _store_path(base: Path) -> Path:
    return base / "docs" / "guardian" / "deferred_decisions.json"


def _sample_item(
    item_id: str = "GDD-0001",
    *,
    description: str = "Test decision",
    module: str = "Test Module",
    status: DeferredDecisionStatus = DeferredDecisionStatus.OPEN,
    closed_at: str | None = None,
    extra: dict | None = None,
) -> DeferredDecision:
    return DeferredDecision(
        id=item_id,
        project="IFG",
        module=module,
        type=DeferredDecisionType.ARCHITECTURE,
        priority=DeferredPriority.MEDIUM,
        status=status,
        defer_reason="Deferred for later",
        description=description,
        review_when="Next GWO",
        source="unit-test",
        created_at="2026-07-11",
        closed_at=closed_at,
        extra_fields=extra or {},
    )


class TestGddIntegrityValidation(unittest.TestCase):
    def test_valid_store_passes(self):
        store = DeferredDecisionStore(
            next_id=2,
            items=[_sample_item()],
        )
        report = validate_store(store)
        self.assertTrue(report.valid)

    def test_duplicate_id_rejected(self):
        store = DeferredDecisionStore(
            next_id=2,
            items=[_sample_item(), _sample_item()],
        )
        report = validate_store(store)
        self.assertFalse(report.valid)
        codes = {issue.code for issue in report.issues}
        self.assertIn(IntegrityCode.DUPLICATE_ID, codes)

    def test_next_id_recomputed_for_namespaced_ids(self):
        store = DeferredDecisionStore(
            next_id=2,
            items=[
                _sample_item("GDD-0001"),
                _sample_item("GDD-MAC-0001", module="macdiag"),
            ],
        )
        report = validate_store(store)
        self.assertTrue(report.valid)

    def test_done_without_closed_at_detected(self):
        store = DeferredDecisionStore(
            next_id=2,
            items=[
                DeferredDecision(
                    id="GDD-0001",
                    project="IFG",
                    module="A",
                    type=DeferredDecisionType.PROCESS,
                    priority=DeferredPriority.LOW,
                    status=DeferredDecisionStatus.DONE,
                    defer_reason="r",
                    description="d",
                    review_when="later",
                    source="t",
                    created_at="2026-07-11",
                    closed_at=None,
                )
            ],
        )
        report = validate_store(store)
        self.assertFalse(report.valid)
        self.assertIn(IntegrityCode.DONE_WITHOUT_CLOSED_AT, {i.code for i in report.issues})

    def test_open_with_closed_at_detected(self):
        item = _sample_item(closed_at="2026-07-11")
        store = DeferredDecisionStore(next_id=2, items=[item])
        report = validate_store(store)
        self.assertFalse(report.valid)
        self.assertIn(IntegrityCode.OPEN_WITH_CLOSED_AT, {i.code for i in report.issues})

    def test_unknown_fields_preserved(self):
        item = _sample_item(extra={"lamus_status": "Odroczone (LAMUS)"})
        store = DeferredDecisionStore(next_id=2, items=[item])
        path = Path(tempfile.mkdtemp()) / "store.json"
        save_store(store, path, use_lock=False)
        reloaded = load_store(path)
        self.assertEqual(reloaded.items[0].extra_fields["lamus_status"], "Odroczone (LAMUS)")


class TestGddIdempotency(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmpdir.name)
        self.path = _store_path(self.tmp_path)
        self.service = DeferredDecisionService(store_path=self.path)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _add_once(self):
        return self.service.add(
            project="IFG",
            module="Notification Engine",
            decision_type="Architecture",
            priority="High",
            defer_reason="Later",
            description="Notification Engine adapters",
            review_when="After core split",
            source="GWO-0073",
            created_at="2026-07-11",
        )

    def test_readd_returns_already_exists(self):
        first = self._add_once()
        second = self._add_once()
        self.assertEqual(first.result, AddDecisionResult.CREATED)
        self.assertEqual(second.result, AddDecisionResult.ALREADY_EXISTS)
        self.assertEqual(first.item.id, second.item.id)
        store = load_store(self.path)
        self.assertEqual(len(store.items), 1)

    def test_same_id_different_content_returns_id_conflict(self):
        self.service.add(
            project="IFG",
            module="A",
            decision_type="UX",
            priority="Low",
            defer_reason="r",
            description="first",
            review_when="later",
            source="t",
            created_at="2026-07-11",
            item_id="GDD-0099",
        )
        response = self.service.add(
            project="IFG",
            module="B",
            decision_type="UX",
            priority="Low",
            defer_reason="r",
            description="second",
            review_when="later",
            source="t",
            created_at="2026-07-11",
            item_id="GDD-0099",
        )
        self.assertEqual(response.result, AddDecisionResult.ID_CONFLICT)


class TestGddAtomicStore(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self._tmpdir.name) / "registry.json"

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_atomic_write_survives_failure(self):
        store = DeferredDecisionStore(next_id=2, items=[_sample_item()])
        save_store(store, self.path, use_lock=False)
        original = self.path.read_text(encoding="utf-8")

        def _boom(*_args, **_kwargs):
            raise OSError("simulated failure")

        with patch("ifg_guardian.core.deferred_decisions.store.os.replace", side_effect=_boom):
            with self.assertRaises(OSError):
                save_store(
                    DeferredDecisionStore(
                        next_id=3,
                        items=[
                            _sample_item("GDD-0001", description="first"),
                            _sample_item("GDD-0002", description="second"),
                        ],
                    ),
                    self.path,
                    use_lock=False,
                )
        self.assertEqual(self.path.read_text(encoding="utf-8"), original)

    def test_invalid_store_refuses_save(self):
        store = DeferredDecisionStore(next_id=99, items=[_sample_item()])
        with self.assertRaises(GddIntegrityError):
            save_store(store, self.path, use_lock=False)


class TestGddRepair(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.path = _store_path(Path(self._tmpdir.name))

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_dedupe_exact_duplicates(self):
        dup = _sample_item("GDD-0013", module="Notification Engine", description="Notify adapters")
        dup2 = _sample_item("GDD-0013", module="Notification Engine", description="Notify adapters")
        store = DeferredDecisionStore(next_id=16, items=[dup, dup2])
        deduped, actions = dedupe_items(store.items)
        self.assertEqual(len(deduped), 1)
        self.assertTrue(actions)

    def test_repair_dry_run_does_not_modify_file(self):
        payload = {
            "schema_version": 1,
            "next_id": 99,
            "items": [
                _sample_item("GDD-0013").to_dict(),
                _sample_item("GDD-0013").to_dict(),
            ],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        before = self.path.read_text(encoding="utf-8")
        code = run_deferred_repair(apply=False, store_path=self.path)
        self.assertEqual(code, 0)
        self.assertEqual(self.path.read_text(encoding="utf-8"), before)

    def test_repair_yes_fixes_unambiguous_duplicates(self):
        payload = {
            "schema_version": 1,
            "next_id": 99,
            "items": [
                _sample_item("GDD-0013").to_dict(),
                _sample_item("GDD-0013").to_dict(),
            ],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        code = run_deferred_repair(apply=True, store_path=self.path)
        self.assertEqual(code, 0)
        store = load_store(self.path)
        self.assertEqual(len(store.items), 1)
        self.assertEqual(compute_next_id(store.items), store.next_id)


class TestGddLocking(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.lock_path = Path(self._tmpdir.name) / "gdd.lock"

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_lock_timeout_returns_controlled_error(self):
        holder = GddRegistryLock(lock_path=self.lock_path, timeout_seconds=0.2)
        holder.__enter__()
        try:
            with self.assertRaises(GddRegistryLockError):
                with GddRegistryLock(lock_path=self.lock_path, timeout_seconds=0.2):
                    pass
        finally:
            holder.__exit__(None, None, None)

    def test_lock_serializes_parallel_writes(self):
        store_path = Path(self._tmpdir.name) / "registry.json"
        barrier = threading.Barrier(3)
        errors: list[str] = []

        def writer(suffix: str) -> None:
            try:
                barrier.wait(timeout=5)
                service = DeferredDecisionService(store_path=store_path)
                with patch(
                    "ifg_guardian.core.deferred_decisions.service.GddRegistryLock",
                    lambda **kwargs: GddRegistryLock(lock_path=self.lock_path, **kwargs),
                ):
                    service.add(
                        project="IFG",
                        module=f"M-{suffix}",
                        decision_type="Process",
                        priority="Low",
                        defer_reason="r",
                        description=f"d-{suffix}",
                        review_when="later",
                        source="t",
                        created_at="2026-07-11",
                    )
            except Exception as exc:  # pragma: no cover - diagnostic
                errors.append(str(exc))

        threads = [threading.Thread(target=writer, args=(str(i),)) for i in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
            self.assertFalse(thread.is_alive(), "writer thread hung")

        self.assertEqual(errors, [])
        store = load_store(store_path)
        self.assertEqual(len(store.items), 3)


class TestProductionRegistry(unittest.TestCase):
    def test_production_registry_has_no_duplicate_standard_ids(self):
        root = Path(__file__).resolve().parents[2]
        store = load_store(root / "docs" / "guardian" / "deferred_decisions.json")
        ids = [item.id for item in store.items if item.id.startswith("GDD-") and item.id[4:8].isdigit()]
        self.assertEqual(len(ids), len(set(ids)))
        for needle in ("GDD-0013", "GDD-0014", "GDD-0015"):
            self.assertEqual(sum(1 for item in store.items if item.id == needle), 1)

    def test_production_registry_validates(self):
        root = Path(__file__).resolve().parents[2]
        code = run_deferred_validate(store_path=root / "docs" / "guardian" / "deferred_decisions.json")
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
