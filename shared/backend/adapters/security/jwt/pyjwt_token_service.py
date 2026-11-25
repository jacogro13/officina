# canonical: backend/adapters/security/jwt/pyjwt_token_service.py v1
"""pyjwt behind the app's `TokenService` port (Blueprint v2, D7).

Tokens carry exactly `sub`, the extra claims the app passes, and `exp` — no `iat` —
so an app moving to this adapter keeps the claims its old code wrote.
"""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

import jwt

from domain.auth_errors import InvalidToken, TokenExpired
from domain.ports.token_service import TokenService


class PyJwtTokenService(TokenService):
    """Bearer tokens as symmetrically signed JWTs (HS256 by default).

    A token is self-contained: it can't be revoked before it expires without a
    denylist.
    """

    def __init__(
        self, secret_key: str, algorithm: str = "HS256", expiry_minutes: int = 10080
    ) -> None:
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._expiry_minutes = expiry_minutes

    def issue(self, subject: str, claims: Mapping[str, str | int | bool]) -> str:
        expires = datetime.now(tz=UTC) + timedelta(minutes=self._expiry_minutes)
        payload = {**claims, "sub": subject, "exp": expires}
        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def decode(self, token: str) -> str:
        try:
            payload = jwt.decode(token, self._secret_key, algorithms=[self._algorithm])
        except jwt.ExpiredSignatureError as exc:
            raise TokenExpired("Token has expired") from exc
        except jwt.PyJWTError as exc:
            raise InvalidToken("Invalid token") from exc
        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject:
            raise InvalidToken("Invalid token: missing or malformed subject")
        return subject
