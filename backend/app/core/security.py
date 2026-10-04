from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import uuid
from contextvars import ContextVar

from fastapi import Header, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.db import AssessmentRow, SessionLocal

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def new_access_token() -> str:
    return secrets.token_urlsafe(32)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        supplied = request.headers.get("X-Request-ID", "")
        rid = supplied[:80] if re.fullmatch(r"[A-Za-z0-9_-]{1,80}", supplied) else str(uuid.uuid4())
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["X-Frame-Options"] = "DENY"
            return response
        finally:
            request_id_var.reset(token)


def require_assessment_token(
    assessment_id: str, x_assessment_token: str | None = Header(default=None)
) -> AssessmentRow:
    if not x_assessment_token:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "assessment_token_required",
                "message": "Provide the assessment token in X-Assessment-Token.",
            },
        )
    with SessionLocal() as db:
        row = db.get(AssessmentRow, assessment_id)
        if row is None:
            raise HTTPException(
                status_code=404, detail={"code": "assessment_not_found", "message": "Assessment was not found."}
            )
        expected = row.token_hash
        if not hmac.compare_digest(expected, token_digest(x_assessment_token)):
            raise HTTPException(
                status_code=403,
                detail={"code": "assessment_token_invalid", "message": "The assessment token is not valid."},
            )
        # Detach from session: callers only need the immutable fields below.
        db.expunge(row)
        return row
