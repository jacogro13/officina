# canonical: backend/entrypoints/logging_setup.py v1
"""Logging for every app (Blueprint v2, D6).

    configure_logging(settings.log_level)            # once, at startup
    app.add_middleware(RequestIdMiddleware)          # after creating the app

Output: one readable line per record on stdout (the container runtime keeps it):

    2026-11-16 10:42:01 INFO famiglia.services req=7f3a9c01d2e4 Member created

Each HTTP request gets an id: taken from an incoming `X-Request-ID` header when
it looks safe, otherwise generated. It appears on every log line written while
handling the request and is returned in the `X-Request-ID` response header, so
an error seen in the UI can be matched to its server log lines.

The middleware also writes one access line per request (uvicorn's own access log
is silenced, since it runs outside the request and can't show the id).
"""

import contextvars
import logging
import re
import sys
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s req=%(request_id)s %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
REQUEST_ID_HEADER = "X-Request-ID"

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_access_logger = logging.getLogger("app.access")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class _DropUvicornDuplicateError(logging.Filter):
    """Starlette re-raises every unhandled error after our 500 handler has answered
    (and logged it with the request id); uvicorn would then log the same traceback a
    second time. Drop that second copy."""

    def filter(self, record: logging.LogRecord) -> bool:
        return not record.getMessage().startswith("Exception in ASGI application")


def configure_logging(level: str = "INFO") -> None:
    """Route all logging (app + uvicorn) through one stdout handler. Idempotent."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    handler.addFilter(_RequestIdFilter())

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())

    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
    uvicorn_error = logging.getLogger("uvicorn.error")
    if not any(isinstance(f, _DropUvicornDuplicateError) for f in uvicorn_error.filters):
        uvicorn_error.addFilter(_DropUvicornDuplicateError())
    logging.getLogger("uvicorn.access").disabled = True


class RequestIdMiddleware:
    """Pure ASGI middleware (safe with streaming/SSE responses).

    Health checks are frequent and boring: paths in `quiet_paths` get an id but
    no access line.
    """

    def __init__(self, app: ASGIApp, quiet_paths: tuple[str, ...] = ("/health",)) -> None:
        self.app = app
        self.quiet_paths = quiet_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = (
            dict(scope["headers"]).get(REQUEST_ID_HEADER.lower().encode(), b"").decode("latin-1")
        )
        request_id = incoming if _SAFE_ID.match(incoming) else uuid.uuid4().hex[:12]
        # Not reset afterwards on purpose: each request runs in its own task context,
        # and the 500 handler (which runs after this middleware unwinds) needs the id.
        request_id_var.set(request_id)
        scope.setdefault("state", {})["request_id"] = request_id

        status = 500
        start = time.perf_counter()

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = list(message.get("headers", []))
                headers.append((REQUEST_ID_HEADER.lower().encode(), request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            if scope["path"] not in self.quiet_paths:
                elapsed_ms = (time.perf_counter() - start) * 1000
                _access_logger.info(
                    "%s %s -> %s (%.0f ms)", scope["method"], scope["path"], status, elapsed_ms
                )
