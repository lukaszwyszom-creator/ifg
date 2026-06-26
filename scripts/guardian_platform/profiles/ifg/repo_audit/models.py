from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from guardian_platform.profiles.ifg.lib.line_endings import Confidence
from guardian_platform.profiles.ifg.lib.risk import FileCategory, RiskLevel


@dataclass
class ClassifiedFile:
    path: str
    status: str
    category: FileCategory
    risk: RiskLevel
    note: str = ""
    confidence: Confidence | None = None
    verification: list[str] = field(default_factory=list)
    restore_recommended: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "status": self.status,
            "category": self.category.value,
            "risk": self.risk.value,
            "note": self.note,
            "confidence": self.confidence.value if self.confidence else None,
            "verification": list(self.verification),
            "restore_recommended": self.restore_recommended,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClassifiedFile:
        conf = data.get("confidence")
        return cls(
            path=data["path"],
            status=data.get("status", ""),
            category=FileCategory(data["category"]),
            risk=RiskLevel(data["risk"]),
            note=data.get("note", ""),
            confidence=Confidence(conf) if conf else None,
            verification=list(data.get("verification", [])),
            restore_recommended=data.get("restore_recommended", False),
        )


@dataclass
class RepoAuditState:
    do_fetch: bool = False
    branch: str = ""
    head: str = ""
    dirty: bool = False
    ahead: int = 0
    behind: int = 0
    porcelain: str = ""
    gitattributes_exists: bool = False
    gitignore_exists: bool = False
    files: list[ClassifiedFile] = field(default_factory=list)
    overall_risk: RiskLevel = RiskLevel.LOW
    recommended_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "do_fetch": self.do_fetch,
            "branch": self.branch,
            "head": self.head,
            "dirty": self.dirty,
            "ahead": self.ahead,
            "behind": self.behind,
            "porcelain": self.porcelain,
            "gitattributes_exists": self.gitattributes_exists,
            "gitignore_exists": self.gitignore_exists,
            "files": [f.to_dict() for f in self.files],
            "overall_risk": self.overall_risk.value,
            "recommended_actions": list(self.recommended_actions),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RepoAuditState:
        return cls(
            do_fetch=data.get("do_fetch", False),
            branch=data.get("branch", ""),
            head=data.get("head", ""),
            dirty=data.get("dirty", False),
            ahead=data.get("ahead", 0),
            behind=data.get("behind", 0),
            porcelain=data.get("porcelain", ""),
            gitattributes_exists=data.get("gitattributes_exists", False),
            gitignore_exists=data.get("gitignore_exists", False),
            files=[ClassifiedFile.from_dict(f) for f in data.get("files", [])],
            overall_risk=RiskLevel(data.get("overall_risk", RiskLevel.LOW.value)),
            recommended_actions=list(data.get("recommended_actions", [])),
        )
