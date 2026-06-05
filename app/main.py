from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi import HTTPException as FastAPIHTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routers.auth import router as auth_router
from app.api.routers.contractors import router as contractors_router
from app.api.routers.health import router as health_router
from app.api.routers.invoices import router as invoices_router
from app.api.routers.ksef_session import router as ksef_session_router
from app.api.routers.ksef_session import router_status as ksef_status_router
from app.api.routers.ksef_session import router_sessions as ksef_sessions_router
from app.api.routers.metrics import router as metrics_router
from app.api.routers.mobile import router as mobile_router
from app.api.routers.payments import router as payments_router
from app.api.routers.settings import router as settings_router
from app.api.routers.stock import router as stock_router
from app.api.routers.warehouse_documents import router as warehouse_documents_router
from app.api.routers.warehouse_items import router as warehouse_items_router
from app.api.routers.transmissions import router as transmissions_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestIdMiddleware
from app.persistence.db import session_scope
from app.persistence.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService


PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIST_DIR = PROJECT_ROOT / "frontend-react" / "dist"


class SPAStaticFiles(StaticFiles):
    """StaticFiles that serves index.html as fallback for SPA routing."""

    async def get_response(self, path: str, scope: dict[str, Any]):
        if scope.get("method") not in ("GET", "HEAD"):
            return await super().get_response(path, scope)

        try:
            return await super().get_response(path, scope)
        except (StarletteHTTPException, FastAPIHTTPException) as exc:
            if getattr(exc, "status_code", None) == 404:
                return await super().get_response("index.html", scope)
            raise


@asynccontextmanager
async def application_lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging(settings.log_level, alert_webhook_url=settings.alert_webhook_url)

    if settings.initial_admin_username and settings.initial_admin_password:
        with session_scope() as session:
            auth_service = AuthService(session=session, user_repository=UserRepository(session))
            auth_service.bootstrap_initial_admin(
                username=settings.initial_admin_username,
                password=settings.initial_admin_password,
            )

    yield


def create_application() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        version=settings.app_version,
        lifespan=application_lifespan,
    )

    application.add_middleware(RequestIdMiddleware)
    register_exception_handlers(application)

    application.include_router(health_router)
    application.include_router(metrics_router)
    application.include_router(auth_router, prefix=settings.api_v1_prefix)
    application.include_router(contractors_router, prefix=settings.api_v1_prefix)
    application.include_router(invoices_router, prefix=settings.api_v1_prefix)
    application.include_router(transmissions_router, prefix=settings.api_v1_prefix)
    application.include_router(settings_router, prefix=settings.api_v1_prefix)
    application.include_router(mobile_router, prefix=settings.api_v1_prefix)

    if settings.enable_ksef:
        application.include_router(ksef_status_router, prefix=settings.api_v1_prefix)
        application.include_router(ksef_session_router, prefix=settings.api_v1_prefix)
        application.include_router(ksef_sessions_router, prefix=settings.api_v1_prefix)

    if settings.enable_payments:
        application.include_router(payments_router, prefix=settings.api_v1_prefix)

    if settings.enable_warehouse:
        application.include_router(stock_router, prefix=settings.api_v1_prefix)
        application.include_router(warehouse_items_router, prefix=settings.api_v1_prefix)
        application.include_router(warehouse_documents_router, prefix=settings.api_v1_prefix)

    # Serve frontend SPA under /ui with SPA fallback to index.html.
    if FRONTEND_DIST_DIR.exists():
        application.mount(
            "/ui",
            SPAStaticFiles(directory=str(FRONTEND_DIST_DIR), html=True),
            name="ui",
        )

    return application


app = create_application()


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/ui/", status_code=302)
