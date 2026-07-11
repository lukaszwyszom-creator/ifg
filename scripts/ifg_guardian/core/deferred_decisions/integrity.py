"""GDD registry integrity rules, validation and repair proposals."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ifg_guardian.core.deferred_decisions.models import (
    DeferredDecision,
    DeferredDecisionStatus,
    DeferredDecisionStore,
)

STANDARD_ID_RE = re.compile(r"^GDD-(\d{4})$")
NAMESPACED_ID_RE = re.compile(r"^GDD-[A-Z]+-\d{4}$")
SUPPORTED_STATUSES = {s.value for s in DeferredDecisionStatus}
REQUIRED_ITEM_FIELDS = (
    "id",
    "project",
    "module",
    "type",
    "priority",
    "status",
    "defer_reason",
    "description",
    "review_when",
    "source",
    "created_at",
)


class IntegrityCode(str, Enum):
    OK = "OK"
    DUPLICATE_ID = "DUPLICATE_ID"
    DUPLICATE_LOGIC = "DUPLICATE_LOGIC"
    INVALID_ID_FORMAT = "INVALID_ID_FORMAT"
    INVALID_NEXT_ID = "INVALID_NEXT_ID"
    INVALID_STATUS = "INVALID_STATUS"
    DONE_WITHOUT_CLOSED_AT = "DONE_WITHOUT_CLOSED_AT"
    OPEN_WITH_CLOSED_AT = "OPEN_WITH_CLOSED_AT"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    EMPTY_REQUIRED_FIELD = "EMPTY_REQUIRED_FIELD"
    INVALID_SCHEMA_VERSION = "INVALID_SCHEMA_VERSION"


@dataclass
class IntegrityIssue:
    code: IntegrityCode
    message: str
    item_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:
    valid: bool
    issues: list[IntegrityIssue] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        return 0 if self.valid else 1


@dataclass
class RepairAction:
    action: str
    description: str
    item_id: str | None = None


@dataclass
class RepairReport:
    actions: list[RepairAction] = field(default_factory=list)
    store: DeferredDecisionStore | None = None

    @property
    def changed(self) -> bool:
        return bool(self.actions)


def normalize_text(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def logic_key_from_item(item: DeferredDecision) -> str:
    return "|".join(
        [
            normalize_text(item.project),
            normalize_text(item.module),
            item.type.value.lower(),
            normalize_text(item.description),
        ]
    )


def logic_key_from_raw(raw: dict[str, Any]) -> str:
    return "|".join(
        [
            normalize_text(str(raw.get("project", ""))),
            normalize_text(str(raw.get("module", ""))),
            normalize_text(str(raw.get("type", ""))),
            normalize_text(str(raw.get("description", ""))),
        ]
    )


def is_standard_id(item_id: str) -> bool:
    return bool(STANDARD_ID_RE.match(item_id))


def is_namespaced_id(item_id: str) -> bool:
    return bool(NAMESPACED_ID_RE.match(item_id))


def parse_standard_id_number(item_id: str) -> int | None:
    match = STANDARD_ID_RE.match(item_id)
    if not match:
        return None
    return int(match.group(1))


def compute_next_id(items: list[DeferredDecision]) -> int:
    used = {num for item in items if (num := parse_standard_id_number(item.id)) is not None}
    candidate = 1
    while candidate in used:
        candidate += 1
    return candidate


def _item_completeness(item: DeferredDecision) -> int:
    payload = item.to_dict()
    return sum(1 for value in payload.values() if value not in (None, "", []))


def dedupe_items(items: list[DeferredDecision]) -> tuple[list[DeferredDecision], list[RepairAction]]:
    """Remove exact duplicate IDs; keep the more complete entry."""
    actions: list[RepairAction] = []
    by_id: dict[str, DeferredDecision] = {}
    order: list[str] = []

    for item in items:
        key = item.id
        if key not in by_id:
            by_id[key] = item
            order.append(key)
            continue
        existing = by_id[key]
        keep_new = _item_completeness(item) > _item_completeness(existing)
        dropped = key if keep_new else key
        if keep_new:
            by_id[key] = item
        actions.append(
            RepairAction(
                action="remove_duplicate_id",
                description=f"Removed duplicate ID {dropped} (kept richer entry)",
                item_id=key,
            )
        )

    deduped = [by_id[item_id] for item_id in order]
    return deduped, actions


def validate_store(store: DeferredDecisionStore) -> ValidationReport:
    issues: list[IntegrityIssue] = []

    if store.schema_version < 1:
        issues.append(
            IntegrityIssue(
                code=IntegrityCode.INVALID_SCHEMA_VERSION,
                message=f"Unsupported schema_version: {store.schema_version}",
            )
        )

    seen_ids: dict[str, int] = {}
    seen_logic: dict[str, str] = {}

    for index, item in enumerate(store.items):
        raw = item.to_dict()
        for req in REQUIRED_ITEM_FIELDS:
            if req not in raw:
                issues.append(
                    IntegrityIssue(
                        code=IntegrityCode.MISSING_REQUIRED_FIELD,
                        message=f"Missing required field '{req}'",
                        item_id=item.id,
                    )
                )
            elif raw[req] in (None, ""):
                issues.append(
                    IntegrityIssue(
                        code=IntegrityCode.EMPTY_REQUIRED_FIELD,
                        message=f"Empty required field '{req}'",
                        item_id=item.id,
                    )
                )

        if not (is_standard_id(item.id) or is_namespaced_id(item.id)):
            issues.append(
                IntegrityIssue(
                    code=IntegrityCode.INVALID_ID_FORMAT,
                    message=f"Invalid ID format: {item.id}",
                    item_id=item.id,
                )
            )

        seen_ids[item.id] = seen_ids.get(item.id, 0) + 1
        if seen_ids[item.id] > 1:
            issues.append(
                IntegrityIssue(
                    code=IntegrityCode.DUPLICATE_ID,
                    message=f"Duplicate ID: {item.id}",
                    item_id=item.id,
                    details={"occurrence": seen_ids[item.id]},
                )
            )

        logic = logic_key_from_item(item)
        if logic in seen_logic and seen_logic[logic] != item.id:
            issues.append(
                IntegrityIssue(
                    code=IntegrityCode.DUPLICATE_LOGIC,
                    message=(
                        f"Duplicate logical decision under {item.id} "
                        f"(also {seen_logic[logic]})"
                    ),
                    item_id=item.id,
                    details={"other_id": seen_logic[logic]},
                )
            )
        else:
            seen_logic[logic] = item.id

        if item.status.value not in SUPPORTED_STATUSES:
            issues.append(
                IntegrityIssue(
                    code=IntegrityCode.INVALID_STATUS,
                    message=f"Unsupported status: {item.status.value}",
                    item_id=item.id,
                )
            )
        if item.status == DeferredDecisionStatus.DONE and not item.closed_at:
            issues.append(
                IntegrityIssue(
                    code=IntegrityCode.DONE_WITHOUT_CLOSED_AT,
                    message="DONE entry missing closed_at",
                    item_id=item.id,
                )
            )
        if item.status == DeferredDecisionStatus.OPEN and item.closed_at:
            issues.append(
                IntegrityIssue(
                    code=IntegrityCode.OPEN_WITH_CLOSED_AT,
                    message="OPEN entry must not have closed_at",
                    item_id=item.id,
                )
            )

    expected_next = compute_next_id(store.items)
    if store.next_id != expected_next:
        issues.append(
            IntegrityIssue(
                code=IntegrityCode.INVALID_NEXT_ID,
                message=f"next_id={store.next_id}, expected={expected_next}",
                details={"expected_next_id": expected_next, "actual_next_id": store.next_id},
            )
        )

    return ValidationReport(valid=not issues, issues=issues)


def propose_repairs(store: DeferredDecisionStore) -> RepairReport:
    actions: list[RepairAction] = []
    working = DeferredDecisionStore(
        schema_version=store.schema_version,
        next_id=store.next_id,
        items=list(store.items),
    )

    if any(issue.code == IntegrityCode.DUPLICATE_ID for issue in validate_store(working).issues):
        deduped, dedupe_actions = dedupe_items(working.items)
        working.items = deduped
        actions.extend(dedupe_actions)

    expected_next = compute_next_id(working.items)
    if working.next_id != expected_next:
        actions.append(
            RepairAction(
                action="fix_next_id",
                description=f"Set next_id from {working.next_id} to {expected_next}",
            )
        )
        working.next_id = expected_next

    for item in working.items:
        if item.status == DeferredDecisionStatus.OPEN and item.closed_at:
            actions.append(
                RepairAction(
                    action="clear_closed_at_for_open",
                    description=f"Clear closed_at on OPEN entry {item.id}",
                    item_id=item.id,
                )
            )
        if item.status == DeferredDecisionStatus.DONE and not item.closed_at:
            actions.append(
                RepairAction(
                    action="set_closed_at_for_done",
                    description=f"Set closed_at=created_at for DONE entry {item.id}",
                    item_id=item.id,
                )
            )

    repaired = DeferredDecisionStore(
        schema_version=working.schema_version,
        next_id=working.next_id,
        items=[
            DeferredDecision(
                id=item.id,
                project=item.project,
                module=item.module,
                type=item.type,
                priority=item.priority,
                status=item.status,
                defer_reason=item.defer_reason,
                description=item.description,
                review_when=item.review_when,
                source=item.source,
                created_at=item.created_at,
                closed_at=(
                    None
                    if item.status == DeferredDecisionStatus.OPEN
                    else (item.closed_at or item.created_at)
                ),
                extra_fields=dict(item.extra_fields),
            )
            for item in working.items
        ],
    )

    return RepairReport(actions=actions, store=repaired if actions else None)
