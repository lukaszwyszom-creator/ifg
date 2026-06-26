from __future__ import annotations

from abc import ABC, abstractmethod

from guardian_platform.profiles.ifg.repo_audit.models import ClassifiedFile
from guardian_platform.profiles.ifg.lib.risk import RiskLevel


class RepoAuditExtension(ABC):
    @property
    @abstractmethod
    def plugin_name(self) -> str:
        raise NotImplementedError

    def classify_file(self, path: str, status: str) -> ClassifiedFile | None:
        return None

    def extra_risks(self, audit_files: list[ClassifiedFile]) -> list[RiskLevel]:
        return []


def ifg_repo_audit_extensions() -> list[RepoAuditExtension]:
    """IFG-specific repo audit extensions (M2: none yet)."""
    return []
