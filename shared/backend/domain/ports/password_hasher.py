"""Reference shape for the canonical security adapters. Not canonical: each app writes
its own port (D5, §15).

The canonical `BcryptPasswordHasher` and `FakePasswordHasher` subclass this so they can
be tested here; in an app their import line points to the app's own port instead.
"""

from abc import ABC, abstractmethod


class PasswordHasher(ABC):
    """Port: one-way hashing and verification of user passwords.

    Async because a real hasher is deliberately slow (~300 ms at bcrypt's default
    cost); adapters run the work in a thread so it doesn't stall the event loop.
    """

    @abstractmethod
    async def hash(self, plain: str) -> str:
        """A self-describing hash (salt included) of a plaintext password."""

    @abstractmethod
    async def verify(self, plain: str, hashed: str) -> bool:
        """Whether the plaintext matches the hash. False on a malformed hash."""
