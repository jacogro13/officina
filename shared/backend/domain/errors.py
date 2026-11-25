# canonical: backend/domain/errors.py v2
"""Domain error family (Blueprint v2, D2).

Every *expected* failure the user can cause is a `DomainError` subclass with a
stable `code` (English, snake_case). The frontend maps `code` to Italian text;
`message` is for logs and debugging only.

Subclass one of the kinds below so the HTTP layer knows the status:

    class MemberInUse(Conflict):
        code = "member_in_use"

This module has no imports: it is pure domain.
"""


class DomainError(Exception):
    """Base for every expected, user-facing failure. Prefer a subclass of one of
    the kinds below; a bare `DomainError` is reported as HTTP 400."""

    code: str = "domain_error"

    def __init__(self, message: str = "", *, field: str | None = None) -> None:
        self.message = message or self.code
        self.field = field
        super().__init__(self.message)


class NotFound(DomainError):
    """A referenced entity does not exist (HTTP 404)."""

    code = "not_found"


class Conflict(DomainError):
    """The request is valid but clashes with current state (HTTP 409)."""

    code = "conflict"


class InvalidInput(DomainError):
    """A value breaks a domain rule (HTTP 422). Set `field` when one field is at fault."""

    code = "invalid_input"


class Unauthorized(DomainError):
    """The caller is not authenticated: bad credentials or a bad token (HTTP 401)."""

    code = "unauthorized"


class Forbidden(DomainError):
    """The caller is authenticated but may not do this (HTTP 403)."""

    code = "forbidden"


class PayloadTooLarge(DomainError):
    """An upload or body exceeds a size limit (HTTP 413)."""

    code = "payload_too_large"
