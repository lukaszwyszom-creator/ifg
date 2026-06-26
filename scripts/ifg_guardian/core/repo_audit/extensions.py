from __future__ import annotations

from abc import ABC, abstractmethod

from ifg_guardian.core.repo_audit.models import ClassifiedFile
from ifg_guardian.core.risk import RiskLevel


class RepoAuditExtension(ABC):
    """Optional plugin hook — IFG may extend classification and risk rules."""

    @property
    @abstractmethod
    def plugin_name(self) -> str:
        raise NotImplementedError

    def classify_file(self, path: str, status: str) -> ClassifiedFile | None:
        return None

    def extra_risks(self, audit_files: list[ClassifiedFile]) -> list[RiskLevel]:
        return []
