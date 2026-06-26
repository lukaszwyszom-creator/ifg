from __future__ import annotations

from enum import Enum


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FileCategory(str, Enum):
    COMMIT = "commit"
    IGNORE = "ignore"
    DELETE_REVIEW = "delete_review"
    CRLF_ONLY = "crlf_only"
    UNKNOWN_LINE_ENDINGS = "unknown_line_endings"
    SUBSTANTIVE = "substantive"
    DEPLOY_BLOCKER = "deploy_blocker"

    # Deprecated alias — kept for backward-compatible report parsing
    CRLF_NOISE = "crlf_noise"


def max_risk(*levels: RiskLevel) -> RiskLevel:
    order = (RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL)
    best = RiskLevel.LOW
    for level in levels:
        if order.index(level) > order.index(best):
            best = level
    return best
