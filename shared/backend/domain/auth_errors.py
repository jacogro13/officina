"""Reference shape for the canonical security adapters. Not canonical: each app writes
its own token errors (D5, §15), with these two codes.

`TokenExpired` is an `InvalidToken`, so code that only cares "is the token usable?"
catches one class, while the API can still answer `token_expired` vs `invalid_token`.
"""

from domain.errors import Unauthorized


class InvalidToken(Unauthorized):
    """The bearer token is malformed, badly signed or has no subject."""

    code = "invalid_token"


class TokenExpired(InvalidToken):
    """The bearer token was valid but its `exp` has passed."""

    code = "token_expired"
