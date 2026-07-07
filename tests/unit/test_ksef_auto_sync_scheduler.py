from __future__ import annotations

from datetime import UTC, datetime

from app.worker.ksef_auto_sync_scheduler import evaluate_tick, parse_minute_hour_cron


def _dt(hour: int, minute: int, day: int = 7) -> datetime:
    return datetime(2026, 7, day, hour, minute, tzinfo=UTC)


def test_scheduler_start_and_enqueue_due_slot() -> None:
    result = evaluate_tick(
        enabled=True,
        cron_expr="0 8,14 * * *",
        now=_dt(8, 0),
        last_executed_slot_key=None,
    )
    assert result.should_enqueue is True
    assert result.slot_key == "2026-07-07T08:00"
    assert result.is_recovery is False


def test_scheduler_disabled() -> None:
    result = evaluate_tick(
        enabled=False,
        cron_expr="0 8,14 * * *",
        now=_dt(8, 0),
        last_executed_slot_key=None,
    )
    assert result.should_enqueue is False
    assert result.reason == "disabled"


def test_scheduler_no_double_run_for_same_slot() -> None:
    result = evaluate_tick(
        enabled=True,
        cron_expr="0 8,14 * * *",
        now=_dt(8, 1),
        last_executed_slot_key="2026-07-07T08:00",
    )
    assert result.should_enqueue is False
    assert result.reason == "already_executed"


def test_scheduler_recovery_after_restart_0801() -> None:
    result = evaluate_tick(
        enabled=True,
        cron_expr="0 8,14 * * *",
        now=_dt(8, 1),
        last_executed_slot_key="2026-07-06T14:00",
    )
    assert result.should_enqueue is True
    assert result.slot_key == "2026-07-07T08:00"
    assert result.is_recovery is True


def test_scheduler_recovery_after_restart_1401() -> None:
    result = evaluate_tick(
        enabled=True,
        cron_expr="0 8,14 * * *",
        now=_dt(14, 1),
        last_executed_slot_key="2026-07-07T08:00",
    )
    assert result.should_enqueue is True
    assert result.slot_key == "2026-07-07T14:00"
    assert result.is_recovery is True


def test_scheduler_two_slots_per_day_sequence() -> None:
    morning = evaluate_tick(
        enabled=True,
        cron_expr="0 8,14 * * *",
        now=_dt(8, 0),
        last_executed_slot_key=None,
    )
    assert morning.should_enqueue is True
    afternoon = evaluate_tick(
        enabled=True,
        cron_expr="0 8,14 * * *",
        now=_dt(14, 0),
        last_executed_slot_key=morning.slot_key,
    )
    assert afternoon.should_enqueue is True
    assert afternoon.slot_key == "2026-07-07T14:00"


def test_scheduler_cron_change_effective() -> None:
    result = evaluate_tick(
        enabled=True,
        cron_expr="0 9 * * *",
        now=_dt(8, 30),
        last_executed_slot_key="2026-07-06T09:00",
    )
    assert result.should_enqueue is False


def test_scheduler_recovers_only_latest_missed_slot() -> None:
    # Worker was down for a long time; enqueue only latest due slot.
    result = evaluate_tick(
        enabled=True,
        cron_expr="0 8,14 * * *",
        now=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
        last_executed_slot_key="2026-07-06T14:00",
    )
    assert result.should_enqueue is True
    assert result.slot_key == "2026-07-08T08:00"


def test_parse_cron_rejects_day_month_dow_restrictions() -> None:
    try:
        parse_minute_hour_cron("0 8 * * 1")
    except ValueError as exc:
        assert "day/month/dow" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsupported cron fields")
