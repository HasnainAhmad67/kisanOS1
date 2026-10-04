from __future__ import annotations

import sys
from pathlib import Path as _Path

# Vercel loads this file as the function entry from the project root, where the
# `app` package (backend/app) is not importable yet. Adding backend/ to sys.path
# makes the normal `from app...` imports resolve; no-op in local dev (uvicorn
# runs with backend/ as the working directory).
_BACKEND_ROOT = str(_Path(__file__).resolve().parents[1])
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

import asyncio
import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import router
from app.core.config import get_settings
from app.core.security import RequestContextMiddleware, request_id_var
from app.db import ImageRow, SessionLocal, init_db

settings = get_settings()
logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("kisanos.api")


def purge_expired_images() -> int:
    cutoff = datetime.now(UTC) - timedelta(hours=settings.image_retention_hours)
    deleted = 0
    with SessionLocal() as db:
        rows = db.scalars(select(ImageRow).where(ImageRow.created_at < cutoff)).all()
        root = settings.image_storage_dir.resolve()
        for row in rows:
            path = (root / row.storage_key).resolve()
            if root in path.parents:
                path.unlink(missing_ok=True)
            db.delete(row)
            deleted += 1
        db.commit()
    return deleted


async def _retention_janitor() -> None:
    while True:
        try:
            deleted = await asyncio.to_thread(purge_expired_images)
            if deleted:
                logger.info("expired private images removed", extra={"count": deleted})
        except Exception as exc:  # noqa: BLE001 - retention failure is isolated and retried on the next sweep.
            logger.warning("image retention cleanup failed", extra={"error_type": type(exc).__name__})
        await asyncio.sleep(900)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    removed = await asyncio.to_thread(purge_expired_images)
    if removed:
        logger.info("expired private images removed at startup", extra={"count": removed})
    janitor = asyncio.create_task(_retention_janitor(), name="kisanos-image-retention")
    try:
        yield
    finally:
        janitor.cancel()
        try:
            await janitor
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="KisanOS API",
    version=settings.app_version,
    description="Evidence-first, multi-agent wheat field decision support for the Bahawalpur pilot. No diagnosis or automated field commands.",
    openapi_url=f"{settings.api_prefix}/openapi.json",
    docs_url=f"{settings.api_prefix}/docs",
    redoc_url=None,
    lifespan=lifespan,
)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Assessment-Token", "X-Request-ID"],
)

_RATE_HITS: dict[str, deque[float]] = defaultdict(deque)
_RATE_LIMITS = {"upload": 12, "create": 12, "demo": 3, "default": 180}


@app.middleware("http")
async def request_rate_limit(request: Request, call_next):
    path = request.url.path
    kind = (
        "upload"
        if path.endswith("/images") and request.method == "POST"
        else (
            "create"
            if path.endswith("/assessments") and request.method == "POST"
            else ("demo" if path.endswith("/demo/seed") else "default")
        )
    )
    client_ip = request.client.host if request.client else "unknown"
    key = f"{client_ip}:{kind}"
    current = time.monotonic()
    hits = _RATE_HITS[key]
    while hits and current - hits[0] > 60:
        hits.popleft()
    if len(hits) >= _RATE_LIMITS[kind]:
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": "60"},
            content={
                "code": "rate_limit_exceeded",
                "message": "Too many requests; try again shortly.",
                "request_id": request_id_var.get(),
            },
        )
    hits.append(current)
    if len(_RATE_HITS) > 10000:
        for old_key in list(_RATE_HITS)[:1000]:
            if not _RATE_HITS[old_key] or current - _RATE_HITS[old_key][-1] > 120:
                _RATE_HITS.pop(old_key, None)
    return await call_next(request)


@app.middleware("http")
async def enforce_content_length(request: Request, call_next):
    value = request.headers.get("content-length")
    if value:
        try:
            size = int(value)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={
                    "code": "invalid_content_length",
                    "message": "Invalid Content-Length.",
                    "request_id": request_id_var.get(),
                },
            )
        # Supports four bounded photos per multipart request with some framing overhead.
        if size > settings.max_upload_bytes * settings.max_images_per_assessment + 1024 * 1024:
            return JSONResponse(
                status_code=413,
                content={
                    "code": "request_too_large",
                    "message": "Request exceeds the configured upload bound.",
                    "request_id": request_id_var.get(),
                },
            )
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "code": "validation_error",
            "message": "Request fields failed validation.",
            "request_id": request_id_var.get(),
            "details": {
                "errors": [
                    {
                        "location": list(e.get("loc", [])),
                        "message": e.get("msg", "Invalid value"),
                        "type": e.get("type"),
                    }
                    for e in exc.errors()
                ]
            },
        },
    )


@app.exception_handler(StarletteHTTPException)
async def typed_http_error(request: Request, exc: StarletteHTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "http_error", "message": str(exc.detail)}
    body = {
        "code": detail.get("code", "http_error"),
        "message": detail.get("message", "The request could not be completed."),
        "request_id": request_id_var.get(),
    }
    if "details" in detail:
        body["details"] = detail["details"]
    return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    logger.exception(
        "unhandled API exception", extra={"request_id": request_id_var.get(), "error_type": type(exc).__name__}
    )
    return JSONResponse(
        status_code=500,
        content={
            "code": "internal_error",
            "message": "The request could not be completed.",
            "request_id": request_id_var.get(),
        },
    )


app.include_router(router, prefix=settings.api_prefix)
