from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
from unittest.mock import patch

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian import cli  # noqa: E402
from ifg_guardian.core.deferred_decisions.models import (  # noqa: E402
    DeferredDecisionStatus,
    DeferredDecisionType,
    DeferredPriority,
    coerce_decision_type,
    coerce_priority,
)
from ifg_guardian.core.deferred_decisions.service import DeferredDecisionService  # noqa: E402
from ifg_guardian.core.deferred_decisions.store import load_store  # noqa: E402
from ifg_guardian.modules.deferred_decisions import (  # noqa: E402
    run_deferred_add,
    run_deferred_review,
    run_deferred_show,
)


def _store_path(base: Path) -> Path:
    return base / "docs" / "guardian" / "deferred_decisions.json"


class TestDeferredDecisionEnums(unittest.TestCase):
    def test_coerce_enums(self):
        self.assertEqual(coerce_decision_type("architecture"), DeferredDecisionType.ARCHITECTURE)
        self.assertEqual(coerce_decision_type("Technical Debt"), DeferredDecisionType.TECHNICAL_DEBT)
        self.assertEqual(coerce_priority("high"), DeferredPriority.HIGH)


class TestDeferredDecisionStore(unittest.TestCase):
    def setUp(self):
        import tempfile

        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_add_and_allocate_id(self):
        path = _store_path(self.tmp_path)
        service = DeferredDecisionService(store_path=path)
        item = service.add(
            project="IFG",
            module="Test Module",
            decision_type="UX",
            priority="Low",
            defer_reason="Out of scope",
            description="Deferred UX polish",
            review_when="Next iteration",
            source="unit-test",
            created_at="2026-07-09",
        )
        self.assertEqual(item.id, "GDD-0001")
        reloaded = load_store(path)
        self.assertEqual(len(reloaded.items), 1)
        self.assertEqual(reloaded.next_id, 2)

    def test_list_filters_by_project_and_status(self):
        path = _store_path(self.tmp_path)
        service = DeferredDecisionService(store_path=path)
        service.add(
            project="IFG",
            module="A",
            decision_type="UX",
            priority="Low",
            defer_reason="r",
            description="d1",
            review_when="later",
            source="t",
            created_at="2026-07-09",
        )
        item2 = service.add(
            project="OTHER",
            module="B",
            decision_type="Process",
            priority="High",
            defer_reason="r",
            description="d2",
            review_when="later",
            source="t",
            created_at="2026-07-09",
        )
        service.mark_done(item2.id)

        open_ifg = service.list_items(project="IFG", status="OPEN")
        self.assertEqual(len(open_ifg), 1)
        self.assertEqual(open_ifg[0].module, "A")

        done = service.list_items(status="DONE")
        self.assertEqual(len(done), 1)
        self.assertEqual(done[0].project, "OTHER")

    def test_mark_done_sets_closed_at(self):
        path = _store_path(self.tmp_path)
        service = DeferredDecisionService(store_path=path)
        item = service.add(
            project="IFG",
            module="A",
            decision_type="Refactor",
            priority="Medium",
            defer_reason="r",
            description="d",
            review_when="later",
            source="t",
            created_at="2026-07-09",
        )
        updated = service.mark_done(item.id)
        self.assertEqual(updated.status, DeferredDecisionStatus.DONE)
        self.assertEqual(updated.closed_at, "2026-07-09")

    def test_render_review_markdown(self):
        path = _store_path(self.tmp_path)
        service = DeferredDecisionService(store_path=path)
        service.add(
            project="IFG",
            module="Monitor",
            decision_type="Performance",
            priority="High",
            defer_reason="Scale not reached",
            description="Backend filtering",
            review_when=">500 rows",
            source="GWO-0059",
            created_at="2026-07-09",
        )
        md = service.render_review_markdown(project="IFG", today=date(2026, 7, 9))
        self.assertIn("# GDD REVIEW 2026-07-09", md)
        self.assertIn("GDD-0001", md)
        self.assertIn("Backend filtering", md)

    def test_run_deferred_add_cli(self):
        path = _store_path(self.tmp_path)
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = run_deferred_add(
                project="IFG",
                module="CLI Module",
                decision_type="Process",
                priority="Medium",
                defer_reason="Later",
                description="Test via CLI runner",
                review_when="Next release",
                source="unit-test",
                store_path=path,
            )
        self.assertEqual(code, 0)
        self.assertIn("Created GDD-0001", buf.getvalue())
        store = load_store(path)
        self.assertEqual(store.items[0].description, "Test via CLI runner")

    def test_run_deferred_show_not_found(self):
        path = _store_path(self.tmp_path)
        DeferredDecisionService(store_path=path)  # creates empty store on first add only
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"schema_version":1,"next_id":1,"items":[]}\n', encoding="utf-8")
        code = run_deferred_show(item_id="GDD-9999", store_path=path)
        self.assertEqual(code, 1)

    def test_run_deferred_review_writes_report(self):
        path = _store_path(self.tmp_path)
        service = DeferredDecisionService(store_path=path)
        service.add(
            project="IFG",
            module="Review",
            decision_type="Other",
            priority="Low",
            defer_reason="r",
            description="d",
            review_when="later",
            source="t",
            created_at="2026-07-09",
        )
        report = self.tmp_path / "docs" / "guardian" / "GDD_REVIEW_TEST.md"
        with patch("ifg_guardian.modules.deferred_decisions.date") as mock_date:
            mock_date.today.return_value = date(2026, 7, 9)
            code = run_deferred_review(
                project="IFG",
                report_path=report,
                output_format="terminal",
                store_path=path,
            )
        self.assertEqual(code, 0)
        self.assertTrue(report.exists())
        self.assertIn("GDD-0001", report.read_text(encoding="utf-8"))


class TestDeferredDecisionMigration(unittest.TestCase):
    def test_seed_store_loads_migration_entries(self):
        root = Path(__file__).resolve().parents[2]
        store = load_store(root / "docs" / "guardian" / "deferred_decisions.json")
        self.assertGreaterEqual(len(store.items), 9)
        ids = {item.id for item in store.items}
        self.assertIn("GDD-0001", ids)
        self.assertIn("GDD-0006", ids)
        handoff = next(item for item in store.items if item.id == "GDD-0001")
        self.assertEqual(handoff.module, "Guardian Handoff")
        self.assertEqual(handoff.status, DeferredDecisionStatus.OPEN)


class TestDeferredDecisionCli(unittest.TestCase):
    def test_cli_deferred_list_dispatch(self):
        captured: dict[str, object] = {}

        def _fake_list(**kwargs):
            captured.update(kwargs)
            return 0

        with patch("ifg_guardian.cli.run_deferred_list", _fake_list):
            code = cli.main(["deferred", "list", "--project", "IFG", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(captured["project"], "IFG")
        self.assertEqual(captured["output_format"], "json")


if __name__ == "__main__":
    unittest.main()
