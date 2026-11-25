import logging

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from domain.errors import (
    Conflict,
    DomainError,
    Forbidden,
    InvalidInput,
    NotFound,
    PayloadTooLarge,
    Unauthorized,
)
from entrypoints.error_handlers import ERROR_RESPONSES, install_error_handlers
from entrypoints.logging_setup import RequestIdMiddleware


class ActivityBody(BaseModel):
    title: str
    member_ids: list[int]


class MemberInUse(Conflict):
    code = "member_in_use"


RAISED = {
    "not_found": NotFound("Member 1 not found"),
    "member_in_use": MemberInUse("Member 1 is used by activity 2"),
    "invalid_name": InvalidInput("blank", field="name"),
    "bare_domain": DomainError("odd"),
    "bad_login": Unauthorized("wrong password"),
    "not_yours": Forbidden("admin only"),
    "too_big": PayloadTooLarge("file over 10 MB", field="file"),
}


def make_client() -> TestClient:
    app = FastAPI(responses=ERROR_RESPONSES)
    install_error_handlers(app)
    app.add_middleware(RequestIdMiddleware)

    @app.get("/raise/{key}")
    def raise_domain(key: str):
        raise RAISED[key]

    @app.get("/items/{item_id}")
    def get_item(item_id: int):
        return {"item_id": item_id}

    @app.post("/activities")
    def create_activity(body: ActivityBody):
        return body

    @app.get("/http")
    def raise_http():
        raise HTTPException(status_code=413, detail="Image too large")

    @app.get("/bug")
    def bug():
        raise ZeroDivisionError("secret internals")

    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize(
    ("key", "status", "code", "field"),
    [
        ("not_found", 404, "not_found", None),
        ("member_in_use", 409, "member_in_use", None),
        ("invalid_name", 422, "invalid_input", "name"),
        ("bare_domain", 400, "domain_error", None),
        ("bad_login", 401, "unauthorized", None),
        ("not_yours", 403, "forbidden", None),
        ("too_big", 413, "payload_too_large", "file"),
    ],
)
def test_domain_errors_map_to_status_code_and_field(key, status, code, field):
    client = make_client()

    response = client.get(f"/raise/{key}")

    assert response.status_code == status
    assert response.json()["code"] == code
    assert response.json()["field"] == field


def test_request_validation_error_names_the_field():
    client = make_client()

    response = client.get("/items/not-a-number")

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"
    assert response.json()["field"] == "item_id"


def test_bad_list_item_is_reported_under_the_list_field_name():
    client = make_client()

    response = client.post("/activities", json={"title": "Calcio", "member_ids": [1, "x"]})

    assert response.status_code == 422
    assert response.json()["field"] == "member_ids"


def test_http_exception_uses_the_common_error_shape():
    client = make_client()

    response = client.get("/http")

    assert response.status_code == 413
    assert response.json() == {"code": "http_413", "message": "Image too large", "field": None}


def test_unexpected_error_is_a_generic_500_that_hides_internals():
    client = make_client()

    response = client.get("/bug")

    assert response.status_code == 500
    assert response.json() == {
        "code": "internal_error",
        "message": "Internal server error",
        "field": None,
    }


def test_unexpected_error_is_logged_with_traceback(caplog):
    client = make_client()

    with caplog.at_level(logging.ERROR):
        client.get("/bug")

    record = next(r for r in caplog.records if r.name == "entrypoints.error_handlers")
    assert record.exc_info is not None
    assert "secret internals" in caplog.text


def test_unexpected_error_response_carries_the_request_id():
    client = make_client()

    response = client.get("/bug", headers={"X-Request-ID": "abc123"})

    assert response.headers["X-Request-ID"] == "abc123"


def test_openapi_documents_the_error_body():
    client = make_client()

    schema = client.get("/openapi.json").json()

    assert "ErrorResponse" in schema["components"]["schemas"]
