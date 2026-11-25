# canonical: backend/adapters/security/bcrypt/bcrypt_password_hasher.py v1
"""bcrypt behind the app's `PasswordHasher` port (Blueprint v2, D7).

Runs in a worker thread, cuts passwords to bcrypt's 72-byte limit instead of raising,
and treats a stored value that isn't a bcrypt hash as a failed login.
"""

import logging

import anyio.to_thread
import bcrypt

from domain.ports.password_hasher import PasswordHasher

logger = logging.getLogger(__name__)

# bcrypt hashes at most 72 bytes of input and (since bcrypt 4.1) raises on longer
# passwords. Truncating keeps a long passphrase usable; older bcrypt versions cut at
# the same 72 bytes, so existing hashes still verify. 72 bytes is ample entropy.
_MAX_PASSWORD_BYTES = 72


def _truncate(plain: str) -> bytes:
    return plain.encode("utf-8")[:_MAX_PASSWORD_BYTES]


class BcryptPasswordHasher(PasswordHasher):
    """Password hashing via bcrypt, run in a worker thread.

    Cost 12 (bcrypt's default) is ~300 ms per call — deliberate, and the reason both
    methods are async: on the event loop it would stall every other request.
    """

    def __init__(self, rounds: int = 12) -> None:
        self._rounds = rounds

    async def hash(self, plain: str) -> str:
        def _hash() -> str:
            salt = bcrypt.gensalt(rounds=self._rounds)
            return bcrypt.hashpw(_truncate(plain), salt).decode("utf-8")

        return await anyio.to_thread.run_sync(_hash)

    async def verify(self, plain: str, hashed: str) -> bool:
        def _verify() -> bool:
            try:
                return bcrypt.checkpw(_truncate(plain), hashed.encode("utf-8"))
            except ValueError:
                # The stored value isn't a bcrypt hash: a failed login, not a 500.
                logger.warning("Rejecting a login against a malformed password hash")
                return False

        return await anyio.to_thread.run_sync(_verify)
