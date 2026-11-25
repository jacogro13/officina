"""Reference shape for the canonical security adapters. Not canonical: each app writes
its own port (D5, §15).

The canonical `PyJwtTokenService` subclasses this so it can be tested here; in an app
its import line points to the app's own port instead.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping


class TokenService(ABC):
    """Port: minting and verifying bearer tokens.

    It speaks in plain values, not in the app's `User`: a subject (the user id as a
    string) and extra claims. Sync, unlike `PasswordHasher`: signing and verifying an
    HS256 token takes microseconds.
    """

    @abstractmethod
    def issue(self, subject: str, claims: Mapping[str, str | int | bool]) -> str:
        """A signed token carrying the subject, the extra claims and an expiry."""

    @abstractmethod
    def decode(self, token: str) -> str:
        """The token's subject.

        Raises `TokenExpired` if it has expired, `InvalidToken` for anything else
        (bad signature, garbage, no subject).
        """
