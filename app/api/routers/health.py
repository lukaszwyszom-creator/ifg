from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def healthcheck(
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    db_timezone: str | None = None
    db_timezone_utc: bool | None = None

    try:
        result = session.execute(text("SHOW timezone"))
        db_timezone = result.scalar_one_or_none()
        if db_timezone is not None:
            db_timezone_utc = db_timezone.upper() in ("UTC", "UTC0", "UTC+0", "ETC/UTC", "Z")
    except Exception:
        # SQLite lub brak wpsarcia dla SHOW timezone
        db_timezone = None
        db_timezone_utc = None

    regon_key = (settings.regon_api_key or "").strip()
    regon_configured = bool(regon_key) and regon_key.lower() != "change-me"

    return {
        "status": "ok",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "db_timezone": db_timezone,
        "db_timezone_utc": db_timezone_utc,
        "regon": {
            "environment": settings.regon_environment,
            "configured": regon_configured,
        },
    }

