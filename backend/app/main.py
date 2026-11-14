from __future__ import annotations

import logging
import uuid
from time import perf_counter

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import Response

from backend.app.api.v1.catalog import router as catalog_router
from backend.app.api.v1.events import router as events_router
from backend.app.api.v1.identity import router as identity_router
from backend.app.api.v1.interactions import router as interactions_router
from backend.app.api.v1.recommendations import router as recommendations_router
from backend.app.core.cache import worker_heartbeat
from backend.app.core.config import get_settings
from backend.app.core.db import SessionLocal, engine, utcnow
from backend.app.core.logging import configure_logging
from backend.app.core.metrics import (
    ACTIVE_MODEL,
    DATABASE_ERRORS,
    HTTP_DURATION,
    HTTP_REQUESTS,
    OUTBOX_BACKLOG,
    OUTBOX_DEAD_LETTER_COUNT,
    OUTBOX_OLDEST_AGE,
    OUTBOX_RETRY_ATTEMPTS,
    WORKER_HEARTBEAT,
)
from backend.app.core.models import ModelVersion, OutboxEvent

settings = get_settings()
configure_logging()
logger = logging.getLogger("recsys.http")
app = FastAPI(
    title="RecSys API",
    version="0.1.0",
    docs_url="/docs" if settings.app_env == "development" else None,
    redoc_url=None,
)
app.include_router(catalog_router, prefix="/api/v1")
app.include_router(identity_router, prefix="/api/v1")
app.include_router(interactions_router, prefix="/api/v1")
app.include_router(recommendations_router, prefix="/api/v1")
app.include_router(events_router, prefix="/api/v1")


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration = perf_counter() - start
        route = getattr(request.scope.get("route"), "path", "unmatched")
        HTTP_REQUESTS.labels(request.method, route, "500").inc()
        HTTP_DURATION.labels(request.method, route).observe(duration)
        logger.exception(
            "request_failed",
            extra={
                "request_id": request_id,
                "route": route,
                "method": request.method,
                "status": 500,
                "duration_ms": round(duration * 1000, 2),
                "error_code": "unhandled_exception",
            },
        )
        raise
    duration = perf_counter() - start
    route = getattr(request.scope.get("route"), "path", "unmatched")
    HTTP_REQUESTS.labels(request.method, route, str(response.status_code)).inc()
    HTTP_DURATION.labels(request.method, route).observe(duration)
    logger.info(
        "request_completed",
        extra={
            "request_id": request_id,
            "route": route,
            "method": request.method,
            "status": response.status_code,
            "duration_ms": round(duration * 1000, 2),
        },
    )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Response-Time-Ms"] = str(round(duration * 1000, 2))
    return response


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": f"http_{exc.status_code}", "message": str(exc.detail), "request_id": request.state.request_id},
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"code": "validation_error", "message": "Invalid request", "request_id": request.state.request_id, "fields": [{"path": ".".join(str(part) for part in error["loc"]), "message": error["msg"]} for error in exc.errors()]},
    )


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready")
def ready() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        DATABASE_ERRORS.inc()
        raise HTTPException(503, "Database unavailable") from None
    return {"status": "ready", "recommendation_fallback": "available"}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    try:
        with SessionLocal() as db:
            now = utcnow()
            pending_count, oldest, retry_count = db.execute(
                select(
                    func.count(),
                    func.min(OutboxEvent.created_at),
                    func.coalesce(func.sum(OutboxEvent.attempt_count), 0),
                ).where(OutboxEvent.status == "pending")
            ).one()
            dead_letters = db.scalar(
                select(func.count()).where(OutboxEvent.status == "dead_letter")
            )
            active_model = db.scalar(
                select(ModelVersion.version_id).where(ModelVersion.active.is_(True))
            )
        OUTBOX_BACKLOG.set(pending_count)
        OUTBOX_OLDEST_AGE.set(max(0, (now - oldest).total_seconds()) if oldest else 0)
        OUTBOX_RETRY_ATTEMPTS.set(retry_count)
        OUTBOX_DEAD_LETTER_COUNT.set(dead_letters or 0)
        ACTIVE_MODEL.info({"version": active_model or "fallback"})
    except SQLAlchemyError:
        DATABASE_ERRORS.inc()
    WORKER_HEARTBEAT.set(worker_heartbeat())
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
