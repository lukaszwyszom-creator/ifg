"""Jednolite logowanie audytu synchronizacji faktur zakupowych KSeF → IFG."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)

_LOG_PREFIX = "KSEF_PURCHASE_SYNC_AUDIT"
_REF_SAMPLE_SIZE = 20


@dataclass
class SyncWindowResolution:
    """Wynik wyliczenia okna dat zapytania metadata KSeF."""

    date_from: date
    date_to: date
    source: str
    requested_date_from: date | None = None
    requested_date_to: date | None = None
    force_full: bool = False
    incremental: bool = False
    days_back: int = 90
    overlap_days: int = 0
    last_date_to: date | None = None
    last_date_from: date | None = None
    last_success_at: str | None = None
    resume_state: dict[str, Any] | None = None
    date_types: tuple[str, ...] = ("PermanentStorage", "Invoicing", "Issue")


@dataclass
class MetadataPageRecord:
    """Pojedyncza strona odpowiedzi POST /invoices/query/metadata."""

    page: int
    page_offset: int
    date_type: str
    received: int
    has_more: bool
    is_truncated: bool
    continuation_token: str | None
    permanent_storage_hwm: str | None
    refs: list[str] = field(default_factory=list)


def _ref_sample(refs: set[str] | list[str]) -> tuple[int, list[str], list[str]]:
    ordered = sorted(refs)
    count = len(ordered)
    if count <= _REF_SAMPLE_SIZE * 2:
        return count, ordered, []
    return count, ordered[:_REF_SAMPLE_SIZE], ordered[-_REF_SAMPLE_SIZE:]


def _format_sample(first: list[str], last: list[str]) -> str:
    if not last:
        return ",".join(first) if first else ""
    return f"{','.join(first)} ... {','.join(last)}"


@dataclass
class PurchaseSyncAudit:
    """Agreguje metryki jednej synchronizacji zakupów — jeden blok logów na końcu."""

    nip: str
    date_from: date
    date_to: date
    sync_path: str = "unknown"
    window: SyncWindowResolution | None = None

    metadata_returned: int = 0
    pages_downloaded: int = 0
    invoice_ids_received: int = 0
    xml_downloaded: int = 0
    saved: int = 0
    skipped_existing: int = 0
    skipped_invalid: int = 0
    skipped_error: int = 0
    final_database_count: int | None = None

    refs_received_from_metadata: set[str] = field(default_factory=set)
    refs_xml_downloaded: set[str] = field(default_factory=set)
    refs_saved: set[str] = field(default_factory=set)
    saved_invoice_ids: list[UUID] = field(default_factory=list)
    refs_skipped_existing: set[str] = field(default_factory=set)
    refs_skipped_invalid: set[str] = field(default_factory=set)
    refs_skipped_error: set[str] = field(default_factory=set)
    db_refs_in_window: set[str] = field(default_factory=set)

    metadata_pages: list[MetadataPageRecord] = field(default_factory=list)
    pagination_errors: list[str] = field(default_factory=list)
    rate_limited: bool = False
    incomplete: bool = False

    def record_window(self, window: SyncWindowResolution) -> None:
        self.window = window
        self.date_from = window.date_from
        self.date_to = window.date_to
        logger.info(
            "%s WINDOW nip=%s date_from=%s date_to=%s source=%s "
            "requested_date_from=%s requested_date_to=%s force_full=%s incremental=%s "
            "days_back=%d overlap_days=%d last_date_to=%s last_date_from=%s "
            "last_success_at=%s date_types=%s resume=%s",
            _LOG_PREFIX,
            self.nip,
            window.date_from.isoformat(),
            window.date_to.isoformat(),
            window.source,
            window.requested_date_from.isoformat() if window.requested_date_from else "n/a",
            window.requested_date_to.isoformat() if window.requested_date_to else "n/a",
            window.force_full,
            window.incremental,
            window.days_back,
            window.overlap_days,
            window.last_date_to.isoformat() if window.last_date_to else "n/a",
            window.last_date_from.isoformat() if window.last_date_from else "n/a",
            window.last_success_at or "n/a",
            ",".join(window.date_types),
            _safe_resume_summary(window.resume_state),
        )

    def record_metadata_page(
        self,
        *,
        page_offset: int,
        date_type: str,
        received: int,
        has_more: bool,
        is_truncated: bool,
        response_payload: dict,
        page_refs: list[str] | None = None,
    ) -> None:
        page_num = len(self.metadata_pages) + 1
        continuation = response_payload.get("continuationToken")
        if continuation is not None:
            continuation = str(continuation)
        hwm = response_payload.get("permanentStorageHwmDate")
        if hwm is not None:
            hwm = str(hwm)
        refs = list(page_refs or [])

        record = MetadataPageRecord(
            page=page_num,
            page_offset=page_offset,
            date_type=date_type,
            received=received,
            has_more=has_more,
            is_truncated=is_truncated,
            continuation_token=continuation,
            permanent_storage_hwm=hwm,
            refs=refs,
        )
        self.metadata_pages.append(record)
        self.pages_downloaded = len(self.metadata_pages)

        logger.info(
            "%s page=%d dateType=%s pageOffset=%d received=%d hasMore=%s "
            "isTruncated=%s continuationToken=%s permanentStorageHwmDate=%s",
            _LOG_PREFIX,
            record.page,
            record.date_type,
            record.page_offset,
            record.received,
            record.has_more,
            record.is_truncated,
            record.continuation_token,
            record.permanent_storage_hwm,
        )

    def record_pagination_error(self, message: str) -> None:
        self.pagination_errors.append(message)
        self.incomplete = True
        logger.error("%s PAGINATION_ERROR %s", _LOG_PREFIX, message)

    def finalize_metadata(self, unique_refs: list[str]) -> None:
        self.metadata_returned = len(unique_refs)
        self.invoice_ids_received = len(unique_refs)
        self.refs_received_from_metadata = set(unique_refs)

    def record_xml_downloaded(self, ref: str) -> None:
        self.refs_xml_downloaded.add(ref)
        self.xml_downloaded = len(self.refs_xml_downloaded)

    def record_saved(self, ref: str, invoice_id: UUID | None = None) -> None:
        self.refs_saved.add(ref)
        self.saved = len(self.refs_saved)
        if invoice_id is not None:
            self.saved_invoice_ids.append(invoice_id)

    def record_skipped_existing(self, ref: str) -> None:
        self.refs_skipped_existing.add(ref)
        self.skipped_existing = len(self.refs_skipped_existing)

    def record_skipped_invalid(self, ref: str) -> None:
        self.refs_skipped_invalid.add(ref)
        self.skipped_invalid = len(self.refs_skipped_invalid)

    def record_skipped_error(self, ref: str) -> None:
        self.refs_skipped_error.add(ref)
        self.skipped_error = len(self.refs_skipped_error)

    def has_missing_refs(self) -> bool:
        if not self.db_refs_in_window:
            return False
        metadata_missing = self.refs_received_from_metadata - self.db_refs_in_window
        xml_missing = self.refs_xml_downloaded - self.db_refs_in_window
        saved_missing = self.refs_saved - self.db_refs_in_window
        return bool(metadata_missing or xml_missing or saved_missing)

    def is_sync_incomplete(self) -> bool:
        return (
            self.incomplete
            or self.rate_limited
            or bool(self.pagination_errors)
            or self.has_missing_refs()
            or self.skipped_invalid > 0
            or self.skipped_error > 0
        )

    def emit_ref_lists(self) -> None:
        categories = (
            ("refs_received_from_metadata", self.refs_received_from_metadata),
            ("refs_xml_downloaded", self.refs_xml_downloaded),
            ("refs_saved", self.refs_saved),
            ("refs_skipped_existing", self.refs_skipped_existing),
            ("refs_skipped_invalid", self.refs_skipped_invalid),
            ("refs_skipped_error", self.refs_skipped_error),
        )
        for name, refs in categories:
            count, first, last = _ref_sample(refs)
            logger.info(
                "%s REFS %s count=%d first20=%s last20=%s",
                _LOG_PREFIX,
                name,
                count,
                ",".join(first) if first else "",
                ",".join(last) if last else "",
            )
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "%s REFS_FULL %s count=%d refs=%s",
                    _LOG_PREFIX,
                    name,
                    count,
                    ",".join(sorted(refs)),
                )

    def emit_missing_comparison(self) -> None:
        db_refs = self.db_refs_in_window
        metadata_not_in_db = sorted(self.refs_received_from_metadata - db_refs)
        xml_not_in_db = sorted(self.refs_xml_downloaded - db_refs)
        saved_not_in_db = sorted(self.refs_saved - db_refs)
        db_extra = sorted(db_refs - self.refs_received_from_metadata)

        if metadata_not_in_db or xml_not_in_db or saved_not_in_db or db_extra:
            self.incomplete = True

        m_count, m_first, m_last = _ref_sample(metadata_not_in_db)
        x_count, x_first, x_last = _ref_sample(xml_not_in_db)
        s_count, s_first, s_last = _ref_sample(saved_not_in_db)
        e_count, e_first, e_last = _ref_sample(db_extra)

        logger.info(
            "%s MISSING metadata_not_in_db_count=%d metadata_not_in_db_sample=%s "
            "xml_not_in_db_count=%d xml_not_in_db_sample=%s "
            "saved_not_in_db_count=%d saved_not_in_db_sample=%s "
            "db_extra_count=%d db_extra_sample=%s incomplete=%s",
            _LOG_PREFIX,
            m_count,
            _format_sample(m_first, m_last),
            x_count,
            _format_sample(x_first, x_last),
            s_count,
            _format_sample(s_first, s_last),
            e_count,
            _format_sample(e_first, e_last),
            self.is_sync_incomplete(),
        )

    def emit_summary(self) -> None:
        """Jeden blok podsumowania po zakończeniu (lub wznowieniu) synchronizacji."""
        for line in self.pagination_errors:
            logger.error("%s %s", _LOG_PREFIX, line)

        incomplete = self.is_sync_incomplete()
        if incomplete:
            logger.error(
                "%s SYNC_INCOMPLETE rate_limited=%s pagination_errors=%d "
                "skipped_invalid=%d skipped_error=%d metadata_returned=%d xml_downloaded=%d saved=%d",
                _LOG_PREFIX,
                self.rate_limited,
                len(self.pagination_errors),
                self.skipped_invalid,
                self.skipped_error,
                self.metadata_returned,
                self.xml_downloaded,
                self.saved,
            )

        logger.info(
            "%s SUMMARY nip=%s date_from=%s date_to=%s sync_path=%s "
            "metadata_returned=%d pages_downloaded=%d invoice_ids_received=%d "
            "xml_downloaded=%d saved=%d skipped_existing=%d skipped_invalid=%d "
            "skipped_error=%d final_database_count=%s rate_limited=%s incomplete=%s",
            _LOG_PREFIX,
            self.nip,
            self.date_from.isoformat(),
            self.date_to.isoformat(),
            self.sync_path,
            self.metadata_returned,
            self.pages_downloaded,
            self.invoice_ids_received,
            self.xml_downloaded,
            self.saved,
            self.skipped_existing,
            self.skipped_invalid,
            self.skipped_error,
            self.final_database_count if self.final_database_count is not None else "n/a",
            self.rate_limited,
            incomplete,
        )

    def emit_full_report(self) -> None:
        self.emit_ref_lists()
        self.emit_missing_comparison()
        self.emit_summary()


def _safe_resume_summary(resume: dict[str, Any] | None) -> str:
    if not resume:
        return "n/a"
    offset = resume.get("current_offset")
    refs_count = len(resume.get("invoice_refs") or [])
    return f"offset={offset} refs={refs_count}"


def resolve_purchase_sync_window_details(
    date_from: date | None,
    date_to: date | None,
    *,
    days_back: int,
    force_full: bool,
    sync_state_json: dict | None,
    incremental: bool = False,
    overlap_days: int = 2,
    full_days: int = 365,
    resume_state: dict | None = None,
) -> SyncWindowResolution:
    """Wylicza zakres dat zapytania KSeF wraz z metadanymi źródła."""
    from datetime import datetime, timezone

    resolved_to = date_to or datetime.now(timezone.utc).date()
    last_success_at = None
    last_date_to = None
    last_date_from = None
    if sync_state_json:
        last_success_at = sync_state_json.get("last_success_at")
        raw_to = sync_state_json.get("last_date_to")
        raw_from = sync_state_json.get("last_date_from")
        if isinstance(raw_to, str):
            try:
                last_date_to = date.fromisoformat(raw_to)
            except ValueError:
                pass
        if isinstance(raw_from, str):
            try:
                last_date_from = date.fromisoformat(raw_from)
            except ValueError:
                pass

    if resume_state:
        source = "resume"
        if date_from is not None:
            return SyncWindowResolution(
                date_from=date_from,
                date_to=resolved_to,
                source=source,
                requested_date_from=date_from,
                requested_date_to=date_to,
                force_full=force_full,
                incremental=incremental,
                days_back=days_back,
                overlap_days=overlap_days,
                last_date_to=last_date_to,
                last_date_from=last_date_from,
                last_success_at=last_success_at if isinstance(last_success_at, str) else None,
                resume_state=resume_state,
            )
        if last_date_to is not None:
            incremental_from = last_date_to - timedelta_days(overlap_days)
            return SyncWindowResolution(
                date_from=incremental_from,
                date_to=resolved_to,
                source=source,
                requested_date_from=date_from,
                requested_date_to=date_to,
                force_full=force_full,
                incremental=True,
                days_back=days_back,
                overlap_days=overlap_days,
                last_date_to=last_date_to,
                last_date_from=last_date_from,
                last_success_at=last_success_at if isinstance(last_success_at, str) else None,
                resume_state=resume_state,
            )

    if date_from is not None:
        return SyncWindowResolution(
            date_from=date_from,
            date_to=resolved_to,
            source="request",
            requested_date_from=date_from,
            requested_date_to=date_to,
            force_full=force_full,
            incremental=incremental,
            days_back=days_back,
            overlap_days=overlap_days,
            last_date_to=last_date_to,
            last_date_from=last_date_from,
            last_success_at=last_success_at if isinstance(last_success_at, str) else None,
            resume_state=resume_state,
        )

    if force_full:
        return SyncWindowResolution(
            date_from=resolved_to - timedelta_days(full_days),
            date_to=resolved_to,
            source="force_full",
            requested_date_from=date_from,
            requested_date_to=date_to,
            force_full=True,
            incremental=incremental,
            days_back=days_back,
            overlap_days=overlap_days,
            last_date_to=last_date_to,
            last_date_from=last_date_from,
            last_success_at=last_success_at if isinstance(last_success_at, str) else None,
            resume_state=resume_state,
        )

    if incremental and last_date_to is not None:
        incremental_from = last_date_to - timedelta_days(overlap_days)
        return SyncWindowResolution(
            date_from=incremental_from,
            date_to=resolved_to,
            source="incremental",
            requested_date_from=date_from,
            requested_date_to=date_to,
            force_full=force_full,
            incremental=True,
            days_back=days_back,
            overlap_days=overlap_days,
            last_date_to=last_date_to,
            last_date_from=last_date_from,
            last_success_at=last_success_at if isinstance(last_success_at, str) else None,
            resume_state=resume_state,
        )

    return SyncWindowResolution(
        date_from=resolved_to - timedelta_days(days_back),
        date_to=resolved_to,
        source="default",
        requested_date_from=date_from,
        requested_date_to=date_to,
        force_full=force_full,
        incremental=incremental,
        days_back=days_back,
        overlap_days=overlap_days,
        last_date_to=last_date_to,
        last_date_from=last_date_from,
        last_success_at=last_success_at if isinstance(last_success_at, str) else None,
        resume_state=resume_state,
    )


def timedelta_days(days: int):
    from datetime import timedelta

    return timedelta(days=days)
