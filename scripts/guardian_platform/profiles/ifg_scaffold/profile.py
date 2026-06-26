"""Backward-compatible alias — ifg_scaffold resolves to IFGProfile (M1)."""

from guardian_platform.profiles.ifg.profile import IFGProfile

IFGScaffoldProfile = IFGProfile

__all__ = ["IFGScaffoldProfile"]
