import anyio
import pytest

from adapters.security.bcrypt.bcrypt_password_hasher import BcryptPasswordHasher
from adapters.security.fake.fake_password_hasher import FakePasswordHasher
from domain.ports.password_hasher import PasswordHasher

HASHERS = [
    pytest.param(BcryptPasswordHasher(rounds=4), id="bcrypt"),
    pytest.param(FakePasswordHasher(), id="fake"),
]


def _hash(hasher: PasswordHasher, plain: str) -> str:
    return anyio.run(hasher.hash, plain)


def _verify(hasher: PasswordHasher, plain: str, hashed: str) -> bool:
    return anyio.run(hasher.verify, plain, hashed)


@pytest.mark.parametrize("hasher", HASHERS)
def test_hashed_password_verifies(hasher: PasswordHasher) -> None:
    hashed = _hash(hasher, "correct horse")

    ok = _verify(hasher, "correct horse", hashed)

    assert ok is True


@pytest.mark.parametrize("hasher", HASHERS)
def test_wrong_password_does_not_verify(hasher: PasswordHasher) -> None:
    hashed = _hash(hasher, "correct horse")

    ok = _verify(hasher, "battery staple", hashed)

    assert ok is False


@pytest.mark.parametrize("hasher", HASHERS)
def test_hash_is_not_the_plain_password(hasher: PasswordHasher) -> None:
    hashed = _hash(hasher, "correct horse")

    assert hashed != "correct horse"


@pytest.mark.parametrize("hasher", HASHERS)
def test_malformed_hash_does_not_verify(hasher: PasswordHasher) -> None:
    ok = _verify(hasher, "correct horse", "not-a-hash")

    assert ok is False


def test_bcrypt_hash_is_a_bcrypt_digest_with_the_given_cost() -> None:
    hashed = _hash(BcryptPasswordHasher(rounds=4), "correct horse")

    assert hashed.startswith("$2b$04$")


@pytest.mark.parametrize("hasher", HASHERS)
def test_password_over_72_bytes_hashes_and_verifies(hasher: PasswordHasher) -> None:
    long_password = "ä" * 50  # 100 UTF-8 bytes

    hashed = _hash(hasher, long_password)

    assert _verify(hasher, long_password, hashed) is True
