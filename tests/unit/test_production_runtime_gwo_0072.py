"""GWO-IFG-0072 — maintenance, monitor, audit trail tests."""
from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from ifg_guardian.core.runtime_audit import (
    AUDIT_FILE,
    RuntimeAuditSession,
    append_audit_record,
    build_audit_record,
    read_audit_records,
    sanitize_text,
)
from ifg_guardian.core.runtime_maintenance import (
    MAINTENANCE_FILE,
    MaintenanceMarker,
    clear_maintenance_marker,
    load_maintenance_marker,
    save_maintenance_marker,
)
from ifg_guardian.core.runtime_monitor import (
    ALERT_THRESHOLD_SECONDS,
    MonitorState,
    evaluate_monitor_transition,
)
from ifg_guardian.core.runtime_notify import RuntimeNotifier
from ifg_guardian.core.runtime_status import ProductionRuntimeStatus, classify_runtime_status
from ifg_guardian.core.runtime_store import atomic_write_json, read_json


def _ps_line(service: str, state: str) -> str:
    return f"{service}\t{state}"


class TestProductionMaintenanceStatus:
    def test_maintenance_all_stopped(self):
        ps = "\n".join(
            [
                _ps_line("api", "exited"),
                _ps_line("worker", "exited"),
                _ps_line("db", "exited"),
            ]
        )
        report = classify_runtime_status(ps, maintenance_active=True)
        assert report.status == ProductionRuntimeStatus.PRODUCTION_MAINTENANCE
        assert report.exit_code == 0

    def test_maintenance_inconsistent_partial_running(self):
        ps = "\n".join(
            [
                _ps_line("api", "running (healthy)"),
                _ps_line("worker", "exited"),
                _ps_line("db", "running (healthy)"),
            ]
        )
        report = classify_runtime_status(ps, maintenance_active=True)
        assert report.status == ProductionRuntimeStatus.PRODUCTION_DEGRADED
        assert report.maintenance_inconsistent

    def test_maintenance_inconsistent_all_running(self):
        ps = "\n".join(
            [
                _ps_line("api", "running (healthy)"),
                _ps_line("worker", "running"),
                _ps_line("db", "running (healthy)"),
            ]
        )
        report = classify_runtime_status(ps, maintenance_active=True)
        assert report.status == ProductionRuntimeStatus.PRODUCTION_DEGRADED
        assert report.maintenance_inconsistent


class TestMaintenanceMarker:
    def test_atomic_write_and_read(self, tmp_path, monkeypatch):
        path = tmp_path / "maintenance.json"
        monkeypatch.setattr("ifg_guardian.core.runtime_maintenance.MAINTENANCE_FILE", path)
        marker = MaintenanceMarker(
            active=True,
            operation_id="op-1",
            started_at_utc="2026-07-11T10:00:00Z",
            actor="user",
            hostname="mac",
            reason="test",
            commit="abc",
        )
        save_maintenance_marker(marker)
        loaded = load_maintenance_marker()
        assert loaded is not None
        assert loaded.operation_id == "op-1"
        clear_maintenance_marker()
        assert load_maintenance_marker() is None


class TestMaintenanceWorkflowOrder:
    def test_start_writes_marker_before_stop(self, tmp_path, monkeypatch):
        marker_path = tmp_path / "maintenance.json"
        order: list[str] = []
        monkeypatch.setattr("ifg_guardian.core.runtime_maintenance.MAINTENANCE_FILE", marker_path)
        monkeypatch.setattr("ifg_guardian.core.runtime_audit.AUDIT_FILE", tmp_path / "audit.jsonl")
        monkeypatch.setattr(
            "ifg_guardian.modules.production_maintenance.enforce_mutating_live_orchestration",
            lambda **k: None,
        )

        pre = type(
            "S",
            (),
            {
                "reachable": True,
                "runtime": type("R", (), {"status": ProductionRuntimeStatus.PRODUCTION_RUNNING, "problems": []})(),
            },
        )()
        post = type(
            "S",
            (),
            {
                "reachable": True,
                "runtime": type("R", (), {"status": ProductionRuntimeStatus.PRODUCTION_MAINTENANCE, "problems": []})(),
            },
        )()

        def snapshot(*args, **kwargs):
            return pre if not marker_path.is_file() else post

        monkeypatch.setattr("ifg_guardian.modules.production_maintenance.collect_prod_health_snapshot", snapshot)

        def fake_stop(*args, **kwargs):
            order.append("stop")
            assert marker_path.is_file(), "marker must exist before compose stop"

        monkeypatch.setattr("ifg_guardian.modules.production_maintenance.remote_compose_stop", fake_stop)

        from ifg_guardian.modules.production_maintenance import run_prod_maintenance_start

        code = run_prod_maintenance_start(reason="test", assume_yes=True, remote_host="ds723")
        assert code == 0
        assert order == ["stop"]
        assert marker_path.is_file()


class TestAuditTrail:
    def test_started_completed_failed(self, tmp_path, monkeypatch):
        audit_path = tmp_path / "runtime_audit.jsonl"
        monkeypatch.setattr("ifg_guardian.core.runtime_audit.AUDIT_FILE", audit_path)
        session = RuntimeAuditSession(workflow="prod.recover", event_type="prod_recover")
        session.started()
        session.completed(result="ok")
        session2 = RuntimeAuditSession(workflow="prod.maintenance.start", event_type="maintenance_start")
        session2.started()
        session2.failed("boom")
        records = read_audit_records()
        assert len(records) == 4
        phases = [r["phase"] for r in records]
        assert phases.count("started") == 2
        assert "failed" in phases

    def test_no_secrets_in_audit(self):
        dirty = "Authorization: Bearer secret-token-123"
        clean = sanitize_text(dirty)
        assert clean is not None
        assert "secret-token" not in clean

    def test_atomic_append_record(self, tmp_path, monkeypatch):
        audit_path = tmp_path / "runtime_audit.jsonl"
        monkeypatch.setattr("ifg_guardian.core.runtime_audit.AUDIT_FILE", audit_path)
        append_audit_record(build_audit_record(
            operation_id="x",
            event_type="test",
            workflow="test",
            phase="started",
        ))
        assert audit_path.is_file()
        line = audit_path.read_text().strip()
        parsed = json.loads(line)
        assert parsed["workflow"] == "test"


class TestRuntimeMonitor:
    def _notifier(self, tmp_path):
        log = tmp_path / "notify.log"
        return RuntimeNotifier(log_path=log)

    def test_first_failure_no_alert(self, tmp_path):
        result = evaluate_monitor_transition(
            observed_state=ProductionRuntimeStatus.PRODUCTION_STOPPED.value,
            notifier=self._notifier(tmp_path),
            now="2026-07-11T10:00:00Z",
        )
        assert result.alert_sent is False
        assert result.exit_code == 1

    def test_short_alarm_no_alert(self, tmp_path):
        state_path = tmp_path / "monitor.json"
        monkeypatch_path = tmp_path
        started = "2026-07-11T10:00:00Z"
        atomic_write_json(
            state_path,
            {
                "current_state": ProductionRuntimeStatus.PRODUCTION_STOPPED.value,
                "first_seen_at": started,
                "last_seen_at": started,
                "consecutive_failures": 2,
            },
        )
        with patch("ifg_guardian.core.runtime_monitor.MONITOR_STATE_FILE", state_path):
            result = evaluate_monitor_transition(
                observed_state=ProductionRuntimeStatus.PRODUCTION_STOPPED.value,
                notifier=self._notifier(tmp_path),
                now="2026-07-11T10:05:00Z",
            )
        assert result.alert_sent is False

    def test_confirmed_alarm_once(self, tmp_path):
        state_path = tmp_path / "monitor.json"
        started = "2026-07-11T10:00:00Z"
        confirmed = "2026-07-11T10:11:00Z"
        atomic_write_json(
            state_path,
            {
                "current_state": ProductionRuntimeStatus.PRODUCTION_STOPPED.value,
                "first_seen_at": started,
                "last_seen_at": started,
                "consecutive_failures": 3,
            },
        )
        notifier = self._notifier(tmp_path)
        with patch("ifg_guardian.core.runtime_monitor.MONITOR_STATE_FILE", state_path):
            first = evaluate_monitor_transition(
                observed_state=ProductionRuntimeStatus.PRODUCTION_STOPPED.value,
                notifier=notifier,
                now=confirmed,
            )
            second = evaluate_monitor_transition(
                observed_state=ProductionRuntimeStatus.PRODUCTION_STOPPED.value,
                notifier=notifier,
                now="2026-07-11T10:16:00Z",
            )
        assert first.alert_sent is True
        assert second.alert_sent is False
        assert ALERT_THRESHOLD_SECONDS == 600

    def test_maintenance_no_availability_alarm(self, tmp_path):
        result = evaluate_monitor_transition(
            observed_state=ProductionRuntimeStatus.PRODUCTION_MAINTENANCE.value,
            maintenance_active=True,
            notifier=self._notifier(tmp_path),
            now="2026-07-11T10:20:00Z",
        )
        assert result.alert_sent is False
        assert result.exit_code == 0

    def test_recovery_notification_once(self, tmp_path):
        state_path = tmp_path / "monitor.json"
        atomic_write_json(
            state_path,
            {
                "current_state": ProductionRuntimeStatus.PRODUCTION_STOPPED.value,
                "first_seen_at": "2026-07-11T10:00:00Z",
                "last_seen_at": "2026-07-11T10:15:00Z",
                "last_alerted_state": ProductionRuntimeStatus.PRODUCTION_STOPPED.value,
                "last_alerted_at": "2026-07-11T10:11:00Z",
            },
        )
        notifier = self._notifier(tmp_path)
        with patch("ifg_guardian.core.runtime_monitor.MONITOR_STATE_FILE", state_path):
            result = evaluate_monitor_transition(
                observed_state=ProductionRuntimeStatus.PRODUCTION_RUNNING.value,
                notifier=notifier,
                now="2026-07-11T10:20:00Z",
            )
        assert result.recovery_sent is True
        assert result.exit_code == 0


class TestMonitorInstallGuard:
    def test_blocks_on_ds723(self, monkeypatch):
        monkeypatch.setattr(
            "ifg_guardian.modules.production_monitor.is_ds723_target_host",
            lambda **k: True,
        )
        from ifg_guardian.modules.production_monitor import run_prod_monitor_install

        assert run_prod_monitor_install() == 1


class TestUnreachableMonitor:
    def test_unreachable_state(self, tmp_path):
        result = evaluate_monitor_transition(
            observed_state="UNREACHABLE",
            diagnostic="SSH timeout",
            notifier=RuntimeNotifier(log_path=tmp_path / "n.log"),
            now="2026-07-11T10:00:00Z",
        )
        assert result.observed_state == "UNREACHABLE"
        assert result.exit_code == 1
