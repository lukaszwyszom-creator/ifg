from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

from ifg_guardian.core.deferred_decisions.models import (
    DeferredDecision,
    DeferredDecisionStatus,
    DeferredDecisionStore,
    DeferredDecisionType,
    DeferredPriority,
    coerce_decision_type,
    coerce_priority,
    coerce_status,
)
from ifg_guardian.core.deferred_decisions.store import DEFAULT_STORE_PATH, load_store, save_store

_PRIORITY_ORDER = {
    DeferredPriority.HIGH: 0,
    DeferredPriority.MEDIUM: 1,
    DeferredPriority.LOW: 2,
}


class DeferredDecisionService:
    def __init__(self, store_path: Path | None = None) -> None:
        self._store_path = store_path or DEFAULT_STORE_PATH

    def _load(self) -> DeferredDecisionStore:
        return load_store(self._store_path)

    def _save(self, store: DeferredDecisionStore) -> Path:
        return save_store(store, self._store_path)

    def _format_id(self, number: int) -> str:
        return f"GDD-{number:04d}"

    def _allocate_id(self, store: DeferredDecisionStore) -> str:
        while True:
            candidate = self._format_id(store.next_id)
            store.next_id += 1
            if not any(item.id == candidate for item in store.items):
                return candidate

    def add(
        self,
        *,
        project: str,
        module: str,
        decision_type: str,
        priority: str,
        defer_reason: str,
        description: str,
        review_when: str,
        source: str,
        created_at: str | None = None,
    ) -> DeferredDecision:
        store = self._load()
        item = DeferredDecision(
            id=self._allocate_id(store),
            project=project.strip(),
            module=module.strip(),
            type=coerce_decision_type(decision_type),
            priority=coerce_priority(priority),
            status=DeferredDecisionStatus.OPEN,
            defer_reason=defer_reason.strip(),
            description=description.strip(),
            review_when=review_when.strip(),
            source=source.strip(),
            created_at=created_at or date.today().isoformat(),
            closed_at=None,
        )
        store.items.append(item)
        self._save(store)
        return item

    def get(self, item_id: str) -> DeferredDecision | None:
        needle = item_id.strip().upper()
        for item in self._load().items:
            if item.id.upper() == needle:
                return item
        return None

    def list_items(
        self,
        *,
        project: str | None = None,
        status: str | None = "OPEN",
        decision_type: str | None = None,
        priority: str | None = None,
    ) -> list[DeferredDecision]:
        items = list(self._load().items)
        if project:
            project_key = project.strip().lower()
            items = [item for item in items if item.project.lower() == project_key]
        if status:
            status_value = coerce_status(status)
            items = [item for item in items if item.status == status_value]
        if decision_type:
            type_value = coerce_decision_type(decision_type)
            items = [item for item in items if item.type == type_value]
        if priority:
            priority_value = coerce_priority(priority)
            items = [item for item in items if item.priority == priority_value]
        return sorted(
            items,
            key=lambda item: (
                _PRIORITY_ORDER[item.priority],
                item.created_at,
                item.id,
            ),
        )

    def _set_status(self, item_id: str, status: DeferredDecisionStatus) -> DeferredDecision:
        store = self._load()
        for index, item in enumerate(store.items):
            if item.id.upper() != item_id.strip().upper():
                continue
            updated = replace(
                item,
                status=status,
                closed_at=date.today().isoformat() if status != DeferredDecisionStatus.OPEN else None,
            )
            store.items[index] = updated
            self._save(store)
            return updated
        raise KeyError(item_id)

    def mark_done(self, item_id: str) -> DeferredDecision:
        return self._set_status(item_id, DeferredDecisionStatus.DONE)

    def cancel(self, item_id: str) -> DeferredDecision:
        return self._set_status(item_id, DeferredDecisionStatus.CANCELLED)

    def render_review_markdown(
        self,
        *,
        project: str | None = None,
        today: date | None = None,
    ) -> str:
        stamp = (today or date.today()).isoformat()
        open_items = self.list_items(project=project, status="OPEN")
        project_label = project or "ALL"
        lines = [
            f"# GDD REVIEW {stamp}",
            "",
            f"**Projekt:** {project_label}",
            f"**Otwarte wpisy:** {len(open_items)}",
            "",
        ]
        if not open_items:
            lines.append("Brak otwartych Guardian Deferred Decisions.")
            lines.append("")
            return "\n".join(lines)

        for item in open_items:
            lines.extend(
                [
                    f"## {item.id} — {item.module}",
                    "",
                    f"- **Typ:** {item.type.value}",
                    f"- **Priorytet:** {item.priority.value}",
                    f"- **Status:** {item.status.value}",
                    f"- **Powód odłożenia:** {item.defer_reason}",
                    f"- **Opis:** {item.description}",
                    f"- **Kiedy wrócić:** {item.review_when}",
                    f"- **Źródło:** {item.source}",
                    f"- **Utworzono:** {item.created_at}",
                    "",
                ]
            )
        return "\n".join(lines)

    def render_item_markdown(self, item: DeferredDecision) -> str:
        lines = [
            f"# {item.id}",
            "",
            f"- **Projekt:** {item.project}",
            f"- **Moduł:** {item.module}",
            f"- **Typ:** {item.type.value}",
            f"- **Priorytet:** {item.priority.value}",
            f"- **Status:** {item.status.value}",
            f"- **Powód odłożenia:** {item.defer_reason}",
            f"- **Opis:** {item.description}",
            f"- **Kiedy wrócić:** {item.review_when}",
            f"- **Źródło:** {item.source}",
            f"- **Data utworzenia:** {item.created_at}",
            f"- **Data zamknięcia:** {item.closed_at or '—'}",
            "",
        ]
        return "\n".join(lines)
