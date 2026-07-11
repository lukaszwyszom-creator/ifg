"""Stateful runtime monitor with deduplicated alerting (Mac mini)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ifg_guardian.core.runtime_notify import RuntimeNotification, RuntimeNotifier, default_notifier
from ifg_guardian.core.runtime_status import ProductionRuntimeStatus
from ifg_guardian.core.runtime_store import atomic_write_json, load_or_default, state_path

MONITOR_STATE_FILE = state_path("runtime_monitor.json")
ALERT_THRESHOLD_SECONDS = 600
SCHEMA_VERSION = 1

ALARM_STATES = frozenset(
    {
        ProductionRuntimeStatus.PRODUCTION_STOPPED.value,
        ProductionRuntimeStatus.PRODUCTION_DEGRADED.value,
        "UNREACHABLE",
    }
)
SILENT_STATES = frozenset(
    {
        ProductionRuntimeStatus.PRODUCTION_RUNNING.value,
        ProductionRuntimeStatus.PRODUCTION_MAINTENANCE.value,
    }
)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _seconds_between(start: str | None, end: str | None) -> float:
    a = _parse_utc(start)
    b = _parse_utc(end)
    if not a or not b:
        return 0.0
    return max(0.0, (b - a).total_seconds())


@dataclass
class MonitorState:
    schema_version: int = SCHEMA_VERSION
    current_state: str = ProductionRuntimeStatus.PRODUCTION_RUNNING.value
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    last_alerted_state: str | None = None
    last_alerted_at: str | None = None
    consecutive_failures: int = 0
    last_recovery_at: str | None = None
    last_diagnostic: str | None = None
    maintenance_active: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "current_state": self.current_state,
            "first_seen_at": self.first_seen_at,
            "last_seen_at": self.last_seen_at,
            "last_alerted_state": self.last_alerted_state,
            "last_alerted_at": self.last_alerted_at,
            "consecutive_failures": self.consecutive_failures,
            "last_recovery_at": self.last_recovery_at,
            "last_diagnostic": self.last_diagnostic,
            "maintenance_active": self.maintenance_active,
        }

    @classmethod
    def load(cls) -> MonitorState:
        raw = load_or_default(MONITOR_STATE_FILE, cls().to_dict())
        state = cls()
        state.schema_version = int(raw.get("schema_version", SCHEMA_VERSION))
        state.current_state = str(raw.get("current_state", ProductionRuntimeStatus.PRODUCTION_RUNNING.value))
        state.first_seen_at = raw.get("first_seen_at")
        state.last_seen_at = raw.get("last_seen_at")
        state.last_alerted_state = raw.get("last_alerted_state")
        state.last_alerted_at = raw.get("last_alerted_at")
        state.consecutive_failures = int(raw.get("consecutive_failures", 0))
        state.last_recovery_at = raw.get("last_recovery_at")
        state.last_diagnostic = raw.get("last_diagnostic")
        state.maintenance_active = bool(raw.get("maintenance_active", False))
        return state

    def save(self) -> None:
        atomic_write_json(MONITOR_STATE_FILE, self.to_dict())


@dataclass(frozen=True)
class MonitorCheckResult:
    observed_state: str
    previous_state: str
    alert_sent: bool
    recovery_sent: bool
    alert_reason: str | None
    exit_code: int


def evaluate_monitor_transition(
    *,
    observed_state: str,
    diagnostic: str | None = None,
    maintenance_active: bool = False,
    notifier: RuntimeNotifier | None = None,
    now: str | None = None,
) -> MonitorCheckResult:
    sink = notifier or default_notifier()
    stamp = now or _utc_now()
    state = MonitorState.load()
    previous = state.current_state

    if observed_state == previous:
        state.last_seen_at = stamp
        state.consecutive_failures = state.consecutive_failures + 1 if observed_state in ALARM_STATES else 0
    else:
        state.current_state = observed_state
        state.first_seen_at = stamp
        state.last_seen_at = stamp
        state.consecutive_failures = 1 if observed_state in ALARM_STATES else 0

    state.maintenance_active = maintenance_active
    if diagnostic:
        state.last_diagnostic = diagnostic[:500]

    alert_sent = False
    recovery_sent = False
    alert_reason: str | None = None

    duration = _seconds_between(state.first_seen_at, stamp)
    already_alerted = state.last_alerted_state == observed_state and observed_state in ALARM_STATES

    if observed_state in SILENT_STATES:
        if previous in ALARM_STATES and observed_state == ProductionRuntimeStatus.PRODUCTION_RUNNING.value:
            recovery_sent = sink.send(
                RuntimeNotification(
                    level="INFO",
                    title="IFG runtime recovery",
                    body=(
                        f"Runtime returned to PRODUCTION_RUNNING after {previous}. "
                        f"Diagnostic: {diagnostic or 'n/a'}. "
                        "Suggested: guardian prod health"
                    ),
                )
            )
            state.last_recovery_at = stamp
            state.last_alerted_state = None
            state.last_alerted_at = None
        state.consecutive_failures = 0
        state.save()
        return MonitorCheckResult(
            observed_state=observed_state,
            previous_state=previous,
            alert_sent=recovery_sent,
            recovery_sent=recovery_sent,
            alert_reason=None,
            exit_code=0,
        )

    if observed_state in ALARM_STATES and duration >= ALERT_THRESHOLD_SECONDS and not already_alerted:
        alert_reason = f"confirmed {observed_state} for {int(duration)}s (threshold {ALERT_THRESHOLD_SECONDS}s)"
        alert_sent = sink.send(
            RuntimeNotification(
                level="ALERT",
                title="IFG runtime alert",
                body=(
                    f"Runtime={observed_state}; first_seen={state.first_seen_at}; "
                    f"confirmed_at={stamp}; maintenance={maintenance_active}; "
                    f"diagnostic={diagnostic or 'n/a'}; "
                    "Suggested: guardian prod health && guardian prod recover --yes"
                ),
            )
        )
        state.last_alerted_state = observed_state
        state.last_alerted_at = stamp

    state.save()
    exit_code = 1 if observed_state in ALARM_STATES else 0
    return MonitorCheckResult(
        observed_state=observed_state,
        previous_state=previous,
        alert_sent=alert_sent,
        recovery_sent=recovery_sent,
        alert_reason=alert_reason,
        exit_code=exit_code,
    )
