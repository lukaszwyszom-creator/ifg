from __future__ import annotations

from enum import Enum


class ExecutionMode(str, Enum):
    LIVE = "LIVE"
    DRY_RUN = "DRY_RUN"
    PLAN = "PLAN"

    @property
    def simulates_mutations(self) -> bool:
        return self in (ExecutionMode.DRY_RUN, ExecutionMode.PLAN)
