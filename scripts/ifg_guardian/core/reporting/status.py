"""Ujednolicone poziomy statusów raportów Guardiana (GWO-GUARDIAN-0077)."""
from __future__ import annotations

from enum import Enum


class ReportLevel(str, Enum):
    PASS = "PASS"
    INFO = "INFO"
    WARN = "WARN"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    READY_WITH_OVERRIDE = "READY_WITH_OVERRIDE"


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


STANDARD_LEVELS = frozenset(level.value for level in ReportLevel)
STANDARD_CONFIDENCE = frozenset(level.value for level in ConfidenceLevel)

_CHECK_STATUS_MAP = {
    "PASS": ReportLevel.PASS,
    "WARN": ReportLevel.WARN,
    "FAIL": ReportLevel.FAIL,
    "CRITICAL": ReportLevel.BLOCKED,
}

_OVERALL_STATUS_MAP = {
    "READY": ReportLevel.READY,
    "READY_WITH_WARNINGS": ReportLevel.READY_WITH_WARNINGS,
    "BLOCKED": ReportLevel.BLOCKED,
}

_PREFLIGHT_STATUS_MAP = {
    "PASS": ReportLevel.PASS,
    "WARNING": ReportLevel.WARN,
    "FAIL": ReportLevel.FAIL,
}

_DEPLOYMENT_GATE_MAP = {
    "GO": ReportLevel.READY,
    "NO_GO": ReportLevel.BLOCKED,
}

_RELEASE_DECISION_MAP = {
    "READY_FOR_DEPLOY": ReportLevel.READY,
    "READY_WITH_WARNINGS": ReportLevel.READY_WITH_WARNINGS,
    "READY_WITH_OVERRIDE": ReportLevel.READY_WITH_OVERRIDE,
    "STAGING_ONLY": ReportLevel.WARN,
    "PRODUCTION_BLOCKED": ReportLevel.BLOCKED,
}


def _enum_value(status: Enum | str) -> str:
    if isinstance(status, Enum):
        return status.value
    return str(status)


def normalize_check_status(status: Enum | str) -> ReportLevel:
    return _CHECK_STATUS_MAP.get(_enum_value(status), ReportLevel.INFO)


def normalize_overall_status(status: Enum | str) -> ReportLevel:
    return _OVERALL_STATUS_MAP.get(_enum_value(status), ReportLevel.INFO)


def normalize_preflight_status(status: Enum | str) -> ReportLevel:
    return _PREFLIGHT_STATUS_MAP.get(_enum_value(status), ReportLevel.INFO)


def normalize_deployment_gate(status: Enum | str) -> ReportLevel:
    return _DEPLOYMENT_GATE_MAP.get(_enum_value(status), ReportLevel.INFO)


def normalize_release_decision(status: Enum | str) -> ReportLevel:
    return _RELEASE_DECISION_MAP.get(_enum_value(status), ReportLevel.INFO)


def normalize_confidence(value: str | None) -> str:
    if not value:
        return ConfidenceLevel.UNKNOWN.value
    text = str(value).strip().upper()
    if text in STANDARD_CONFIDENCE:
        return text
    return ConfidenceLevel.UNKNOWN.value


def normalize_decision_yes_no(*, required: bool, blocked: bool = False) -> str:
    if blocked:
        return ReportLevel.BLOCKED.value
    return "YES" if required else "NO"
