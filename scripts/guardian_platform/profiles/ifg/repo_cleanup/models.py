from __future__ import annotations

from enum import Enum


class AdvisorDecision(str, Enum):
    KEEP = "KEEP"
    ARCHIVE = "ARCHIVE"
    REVIEW = "REVIEW"
    DELETE = "DELETE"


class HistoryKind(str, Enum):
    CANONICAL = "canonical"
    CLOSED_INCIDENT = "closed_incident"
    SPRINT_REPORT = "sprint_report"
    RUNTIME_REPORT = "runtime_report"
    OPERATIONS = "operations"
    UNKNOWN = "unknown"
    LOCAL_ARTIFACT = "local_artifact"


class CleanupAction(str, Enum):
    LOCAL_REMOVE = "local_remove"
    GIT_MV = "git_mv"
    LIST_REVIEW = "list_review"
    NOOP = "noop"
