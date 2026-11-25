# canonical: backend/entrypoints/error_handlers.py v2
"""One error path for the whole API (Blueprint v2, D2).

    app = FastAPI(lifespan=lifespan, responses=ERROR_RESPONSES)
    install_error_handlers(app)

Afterwards routes contain no try/except for domain errors. Every error response
has the body `{"code", "message", "field"}`:

    DomainError → Unauthorized 401 · Forbidden 403 · NotFound 404 · Conflict 409
                  · PayloadTooLarge 413 · InvalidInput 422 · other 400
    FastAPI request validation → 422 "invalid_input" (+ field)
    HTTPException → its status, code "http_<status>"
    anything else → 500 "internal_error", logged with traceback, generic message

`describe()` is public so non-JSON entrypoints (CLI, SSE streams) can reuse the mapping.
"""

import logging
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException

from domain.errors import (
    Conflict,
    DomainError,
    Forbidden,
    InvalidInput,
    NotFound,
    PayloadTooLarge,
    Unauthorized,
)

logger = logging.getLogger(__name__)


class ErrorResponse(BaseModel):
    """The single error body of every endpoint (shows up in OpenAPI → frontend types)."""

    code: str
    message: str
    field: str | None = None


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status: {"model": ErrorResponse} for status in (400, 401, 403, 404, 409, 413, 422, 429, 500)
}
"""Pass to `FastAPI(responses=...)` so OpenAPI documents the error body."""


@dataclass(frozen=True)
class ErrorInfo:
    status: int
    code: str
    message: str
    field: str | None = None


_STATUS_BY_KIND: tuple[tuple[type[DomainError], int], ...] = (
    (Unauthorized, 401),
    (Forbidden, 403),
    (NotFound, 404),
    (Conflict, 409),
    (PayloadTooLarge, 413),
    (InvalidInput, 422),
)


def describe(exc: Exception) -> ErrorInfo:
    """Map any exception to status/code/message/field. Logs unexpected ones."""
    if isinstance(exc, DomainError):
        status = next((s for kind, s in _STATUS_BY_KIND if isinstance(exc, kind)), 400)
        return ErrorInfo(status, exc.code, exc.message, exc.field)
    if isinstance(exc, RequestValidationError):
        errors = exc.errors()
        first = errors[0] if errors else {}
        # loc looks like ("body", "co_participant_ids", 1): skip where it came from
        # ("body", "query", …) and list positions; the last name is the field.
        names = [part for part in first.get("loc", ())[1:] if isinstance(part, str)]
        field = names[-1] if names else None
        return ErrorInfo(422, "invalid_input", str(first.get("msg", "Invalid request")), field)
    if isinstance(exc, HTTPException):
        return ErrorInfo(exc.status_code, f"http_{exc.status_code}", str(exc.detail))
    logger.error("Unhandled error: %r", exc, exc_info=exc)
    return ErrorInfo(500, "internal_error", "Internal server error")


async def _handle(request: Request, exc: Exception) -> JSONResponse:
    info = describe(exc)
    body = ErrorResponse(code=info.code, message=info.message, field=info.field)
    headers = {}
    request_id = getattr(request.state, "request_id", None)  # set by RequestIdMiddleware (D6)
    if request_id:
        headers["X-Request-ID"] = request_id
    return JSONResponse(status_code=info.status, content=body.model_dump(), headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _handle)
    app.add_exception_handler(RequestValidationError, _handle)
    app.add_exception_handler(HTTPException, _handle)
    app.add_exception_handler(Exception, _handle)
