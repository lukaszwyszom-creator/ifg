from __future__ import annotations

from datetime import datetime, timezone

# Semantically identical to datetime.UTC (Python 3.11+).
UTC = timezone.utc

__all__ = ["UTC", "datetime", "timezone"]
