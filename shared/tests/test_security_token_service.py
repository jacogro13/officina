from datetime import UTC, datetime, timedelta

import jwt
import pytest

from adapters.security.jwt.pyjwt_token_service import PyJwtTokenService
from domain.auth_errors import InvalidToken, TokenExpired

SECRET = "test-secret-key-at-least-32-bytes-long"
ALGORITHM = "HS256"


def _service(expiry_minutes: int = 60) -> PyJwtTokenService:
    return PyJwtTokenService(SECRET, ALGORITHM, expiry_minutes)


def _tampered() -> str:
    header, payload, signature = _service().issue("user-1", {}).split(".")
    flipped = ("A" if signature[0] != "A" else "B") + signature[1:]
    return f"{header}.{payload}.{flipped}"


def _signed(payload: dict, key: str = SECRET) -> str:
    return jwt.encode(payload, key, algorithm=ALGORITHM)


def _in_an_hour() -> datetime:
    return datetime.now(tz=UTC) + timedelta(hours=1)


def test_issued_token_decodes_to_its_subject() -> None:
    service = _service()

    token = service.issue("user-1", {"username": "anna"})

    assert service.decode(token) == "user-1"


def test_issued_token_carries_exactly_sub_claims_and_exp() -> None:
    token = _service().issue("user-1", {"username": "anna"})

    payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])

    assert set(payload) == {"sub", "username", "exp"}
    assert payload["sub"] == "user-1"
    assert payload["username"] == "anna"


def test_expired_token_is_token_expired() -> None:
    token = _service(expiry_minutes=-1).issue("user-1", {})

    with pytest.raises(TokenExpired):
        _service().decode(token)


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(_tampered(), id="tampered-signature"),
        pytest.param(_signed({"sub": "user-1", "exp": _in_an_hour()}, "x" * 32), id="wrong-key"),
        pytest.param("not-a-jwt", id="garbage"),
        pytest.param(_signed({"username": "anna", "exp": _in_an_hour()}), id="no-sub"),
    ],
)
def test_bad_token_is_invalid_token(token: str) -> None:
    with pytest.raises(InvalidToken) as caught:
        _service().decode(token)

    assert not isinstance(caught.value, TokenExpired)
    assert caught.value.code == "invalid_token"
