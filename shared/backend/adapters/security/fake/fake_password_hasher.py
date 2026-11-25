# canonical: backend/adapters/security/fake/fake_password_hasher.py v1
"""Instant stand-in for bcrypt — tests only (Blueprint v2, D7)."""

from domain.ports.password_hasher import PasswordHasher


class FakePasswordHasher(PasswordHasher):
    """Instant, reversible stand-in for bcrypt — tests only.

    Real hashing costs ~300 ms per call by design, which a unit suite that logs in on
    every test cannot afford. It provides no security and is never wired into the app:
    the app's `get_password_hasher` always builds the bcrypt adapter.
    """

    _PREFIX = "fake-hash:"

    async def hash(self, plain: str) -> str:
        return f"{self._PREFIX}{plain}"

    async def verify(self, plain: str, hashed: str) -> bool:
        return hashed == f"{self._PREFIX}{plain}"
