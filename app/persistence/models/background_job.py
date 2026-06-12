import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import DateTime, Index, Integer, String, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.persistence.base import Base

STALE_PROCESSING_SECONDS = 30 * 60


def _utcnow() -> datetime:
    return datetime.now(UTC)


class BackgroundJob(Base):
    __tablename__ = "background_jobs"
    __table_args__ = (
        Index("ix_background_jobs_status_available_at", "status", "available_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_type: Mapped[str] = mapped_column(String(128), index=True)
    payload_json: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(64), index=True, default="pending")
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    last_error: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


def build_claim_jobs_query(batch_size: int):
    return (
        select(BackgroundJob)
        .where(
            BackgroundJob.status == "pending",
            BackgroundJob.attempts < BackgroundJob.max_attempts,
            or_(
                BackgroundJob.available_at.is_(None),
                BackgroundJob.available_at <= _utcnow(),
            ),
        )
        .order_by(BackgroundJob.available_at.asc())
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )


def count_pending_jobs(session: Session) -> int:
    return session.scalar(
        select(func.count()).select_from(BackgroundJob).where(BackgroundJob.status == "pending")
    ) or 0


def count_claimable_jobs(session: Session) -> int:
    return session.scalar(
        select(func.count())
        .select_from(BackgroundJob)
        .where(
            BackgroundJob.status == "pending",
            BackgroundJob.attempts < BackgroundJob.max_attempts,
            or_(
                BackgroundJob.available_at.is_(None),
                BackgroundJob.available_at <= _utcnow(),
            ),
        )
    ) or 0


def count_pending_blocked_reasons(session: Session) -> dict[str, int]:
    future_available = session.scalar(
        select(func.count())
        .select_from(BackgroundJob)
        .where(
            BackgroundJob.status == "pending",
            BackgroundJob.available_at.isnot(None),
            BackgroundJob.available_at > _utcnow(),
        )
    ) or 0
    exhausted_attempts = session.scalar(
        select(func.count())
        .select_from(BackgroundJob)
        .where(
            BackgroundJob.status == "pending",
            BackgroundJob.attempts >= BackgroundJob.max_attempts,
        )
    ) or 0
    processing = session.scalar(
        select(func.count()).select_from(BackgroundJob).where(BackgroundJob.status == "processing")
    ) or 0
    return {
        "future_available_at": future_available,
        "exhausted_attempts": exhausted_attempts,
        "processing": processing,
    }


def fail_exhausted_pending_jobs(session: Session) -> int:
    exhausted = list(
        session.execute(
            select(BackgroundJob).where(
                BackgroundJob.status == "pending",
                BackgroundJob.attempts >= BackgroundJob.max_attempts,
            )
        ).scalars()
    )
    for job in exhausted:
        job.status = "failed"
        job.last_error = job.last_error or "Przekroczono maksymalną liczbę prób"
        job.locked_at = None
        job.locked_by = None
    return len(exhausted)


def release_stale_processing_jobs(
    session: Session,
    stale_after_seconds: int = STALE_PROCESSING_SECONDS,
) -> int:
    cutoff = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
    stale = list(
        session.execute(
            select(BackgroundJob).where(
                BackgroundJob.status == "processing",
                BackgroundJob.locked_at.isnot(None),
                BackgroundJob.locked_at < cutoff,
            )
        ).scalars()
    )
    for job in stale:
        if job.attempts >= job.max_attempts:
            job.status = "failed"
            job.last_error = job.last_error or "Przekroczono maksymalną liczbę prób (stale recovery)"
        else:
            job.status = "pending"
            job.last_error = job.last_error or "Odblokowano po zawieszeniu workera"
        job.locked_at = None
        job.locked_by = None
    return len(stale)


def prepare_job_queue(session: Session) -> dict[str, int]:
    released = release_stale_processing_jobs(session)
    failed_exhausted = fail_exhausted_pending_jobs(session)
    pending_count = count_pending_jobs(session)
    claimable_count = count_claimable_jobs(session)
    blocked = count_pending_blocked_reasons(session)
    return {
        "released_stale_processing": released,
        "failed_exhausted_pending": failed_exhausted,
        "pending_count": pending_count,
        "claimable_count": claimable_count,
        **blocked,
    }


def claimable_jobs(session: Session, batch_size: int) -> list[BackgroundJob]:
    return list(session.execute(build_claim_jobs_query(batch_size)).scalars())


def claim_and_lock_jobs(
    session: Session,
    batch_size: int,
    *,
    locked_by: str = "worker",
) -> list[BackgroundJob]:
    jobs = claimable_jobs(session, batch_size)
    if not jobs:
        return []

    now = datetime.now(UTC)
    for job in jobs:
        job.status = "processing"
        job.locked_at = now
        job.locked_by = locked_by
        job.attempts += 1
    session.flush()
    return jobs
