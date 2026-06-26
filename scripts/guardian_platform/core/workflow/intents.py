from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class ActionIntent(ABC):
    mutating: bool = False

    @abstractmethod
    def describe(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def intent_type(self) -> str:
        raise NotImplementedError


@dataclass
class NoOpIntent(ActionIntent):
    reason: str = ""
    mutating: bool = False

    @property
    def intent_type(self) -> str:
        return "noop"

    def describe(self) -> str:
        return f"noop: {self.reason or '(no reason)'}"


@dataclass
class FsExistsIntent(ActionIntent):
    path: str = ""
    mutating: bool = False

    @property
    def intent_type(self) -> str:
        return "fs_exists"

    def describe(self) -> str:
        return f"fs exists: {self.path}"


@dataclass
class GitRevParseIntent(ActionIntent):
    ref: str = "HEAD"
    mutating: bool = False

    @property
    def intent_type(self) -> str:
        return "git_rev_parse"

    def describe(self) -> str:
        return f"git rev-parse {self.ref}"


@dataclass
class GitStatusIntent(ActionIntent):
    porcelain: bool = True
    mutating: bool = False

    @property
    def intent_type(self) -> str:
        return "git_status"

    def describe(self) -> str:
        return "git status --porcelain" if self.porcelain else "git status"
