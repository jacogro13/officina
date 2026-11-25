import logging
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from entrypoints.logging_setup import RequestIdMiddleware, configure_logging


@pytest.fixture(autouse=True)
def restore_root_logger():
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)


def make_client() -> TestClient:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/hello")
    def hello():
        logging.getLogger("famiglia.services").info("Member created")
        return {"ok": True}

    @app.get("/health")
    def health():
        return {"ok": True}

    return TestClient(app)


def test_response_carries_a_generated_request_id():
    client = make_client()

    response = client.get("/hello")

    assert re.fullmatch(r"[0-9a-f]{12}", response.headers["X-Request-ID"])


@pytest.mark.parametrize(
    ("incoming", "reused"),
    [
        ("abc-123_XYZ", True),
        ("has spaces", False),
        ("x" * 65, False),
    ],
)
def test_incoming_request_id_is_reused_only_when_safe(incoming, reused):
    client = make_client()

    response = client.get("/hello", headers={"X-Request-ID": incoming})

    assert (response.headers["X-Request-ID"] == incoming) is reused


def test_log_lines_include_the_request_id(capsys):
    configure_logging("INFO")
    client = make_client()

    client.get("/hello", headers={"X-Request-ID": "req42"})

    out = capsys.readouterr().out
    assert re.search(r"INFO famiglia\.services req=req42 Member created", out)
    assert re.search(r"INFO app\.access req=req42 GET /hello -> 200 \(\d+ ms\)", out)


def test_log_level_filters_lower_records(capsys):
    configure_logging("WARNING")
    client = make_client()

    client.get("/hello")

    assert "Member created" not in capsys.readouterr().out


def test_uvicorns_duplicate_traceback_is_dropped(capsys):
    configure_logging("INFO")
    uvicorn_error = logging.getLogger("uvicorn.error")

    uvicorn_error.error("Exception in ASGI application\n")
    uvicorn_error.info("Application startup complete.")

    out = capsys.readouterr().out
    assert "Exception in ASGI application" not in out
    assert "Application startup complete." in out


def test_health_checks_get_no_access_line(capsys):
    configure_logging("INFO")
    client = make_client()

    client.get("/health")

    assert "app.access" not in capsys.readouterr().out
