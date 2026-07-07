from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class SchedulerTickResult:
    should_enqueue: bool
    slot_key: str | None
    is_recovery: bool
    reason: str


@dataclass(frozen=True)
class ParsedCron:
    minutes: tuple[int, ...]
    hours: tuple[int, ...]


def parse_minute_hour_cron(expr: str) -> ParsedCron:
    """
    Parse 5-field cron and return minute/hour sets.
    Supported forms for minute/hour:
    - "*"
    - "*/n"
    - "a,b,c"
    - "a-b"
    """
    parts = (expr or "").strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression '{expr}': expected 5 fields")
    minute_expr, hour_expr, day_expr, month_expr, dow_expr = parts
    if day_expr != "*" or month_expr != "*" or dow_expr != "*":
        raise ValueError(
            "Only minute/hour cron is supported for scheduler (day/month/dow must be '*')"
        )
    minutes = _parse_field(minute_expr, 0, 59)
    hours = _parse_field(hour_expr, 0, 23)
    return ParsedCron(minutes=tuple(sorted(minutes)), hours=tuple(sorted(hours)))


def _parse_field(expr: str, min_value: int, max_value: int) -> set[int]:
    if expr == "*":
        return set(range(min_value, max_value + 1))
    if expr.startswith("*/"):
        step = int(expr[2:])
        if step <= 0:
            raise ValueError(f"Invalid step in cron field: {expr}")
        return set(range(min_value, max_value + 1, step))

    values: set[int] = set()
    for part in expr.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start = int(start_s)
            end = int(end_s)
            if start > end:
                raise ValueError(f"Invalid range in cron field: {part}")
            values.update(range(start, end + 1))
            continue
        values.add(int(part))

    for v in values:
        if v < min_value or v > max_value:
            raise ValueError(f"Cron field value out of range: {v}")
    if not values:
        raise ValueError(f"Empty cron field: {expr}")
    return values


def latest_due_slot_key(now: datetime, cron: ParsedCron) -> str | None:
    """
    Return latest due slot key for current/previous day (YYYY-MM-DDTHH:MM),
    bounded to at most last one missed slot.
    """
    candidates: list[datetime] = []
    for day_offset in (0, -1):
        day = (now + timedelta(days=day_offset)).date()
        for hour in cron.hours:
            for minute in cron.minutes:
                slot = datetime(
                    day.year,
                    day.month,
                    day.day,
                    hour,
                    minute,
                    tzinfo=now.tzinfo,
                )
                if slot <= now:
                    candidates.append(slot)
    if not candidates:
        return None
    latest = max(candidates)
    return latest.strftime("%Y-%m-%dT%H:%M")


def evaluate_tick(
    *,
    enabled: bool,
    cron_expr: str,
    now: datetime,
    last_executed_slot_key: str | None,
) -> SchedulerTickResult:
    if not enabled:
        return SchedulerTickResult(
            should_enqueue=False,
            slot_key=None,
            is_recovery=False,
            reason="disabled",
        )
    try:
        parsed = parse_minute_hour_cron(cron_expr)
    except ValueError as exc:
        return SchedulerTickResult(
            should_enqueue=False,
            slot_key=None,
            is_recovery=False,
            reason=f"invalid_cron:{exc}",
        )
    due_slot = latest_due_slot_key(now, parsed)
    if due_slot is None:
        return SchedulerTickResult(
            should_enqueue=False,
            slot_key=None,
            is_recovery=False,
            reason="no_due_slot",
        )
    if due_slot == last_executed_slot_key:
        return SchedulerTickResult(
            should_enqueue=False,
            slot_key=due_slot,
            is_recovery=False,
            reason="already_executed",
        )

    current_slot = now.strftime("%Y-%m-%dT%H:%M")
    return SchedulerTickResult(
        should_enqueue=True,
        slot_key=due_slot,
        is_recovery=(due_slot != current_slot),
        reason="due",
    )
