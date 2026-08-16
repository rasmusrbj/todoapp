"""Password hashing and strength rules.

Argon2id via ``argon2-cffi``, with parameters from settings so the test suite can
run cheap rounds while production keeps the OWASP-recommended cost. Hashes are PHC
strings, so the parameters travel with the hash and old hashes stay verifiable
after a cost increase — :func:`needs_rehash` reports when to upgrade one.
"""

from __future__ import annotations

import unicodedata
from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from todoapp.config import Settings, get_settings
from todoapp.errors import Reason, invalid_argument

# Rejected outright regardless of length: these are the passwords that actually
# get tried. A real deployment would check against a leaked-password corpus.
_OBVIOUS_PASSWORDS = frozenset(
    {
        "password",
        "password1",
        "password123",
        "passwordpassword",
        "12345678",
        "1234567890",
        "qwertyuiop",
        "adgangskode",
        "kodeord123",
        "todoapptodo",
        "letmein123",
        "iloveyou123",
    }
)

# The longest input we will hash. Argon2 has no practical limit, but an unbounded
# one turns password verification into a CPU denial-of-service vector.
MAX_PASSWORD_LENGTH = 256


@lru_cache(maxsize=1)
def _hasher() -> PasswordHasher:
    settings = get_settings()
    return PasswordHasher(
        time_cost=settings.argon2_time_cost,
        memory_cost=settings.argon2_memory_cost_kib,
        parallelism=settings.argon2_parallelism,
    )


def normalize(password: str) -> str:
    """Applies NFKC so visually identical passwords hash identically.

    Without this, a password typed with a composed 'å' fails to match the same
    password typed with a combining ring — a real problem for Danish keyboards.
    """
    return unicodedata.normalize("NFKC", password)


def validate_strength(password: str, *, settings: Settings | None = None) -> None:
    """Checks a candidate password against the policy.

    Length is the only hard requirement beyond a blocklist: composition rules
    ("one digit, one symbol") measurably push users towards weaker, more
    predictable passwords.

    Raises:
        ConnectError: ``INVALID_ARGUMENT`` with a reason explaining the failure.
    """
    settings = settings or get_settings()
    candidate = normalize(password)

    if not candidate:
        raise invalid_argument(
            Reason.ERROR_REASON_FIELD_REQUIRED, "password is required", field="password"
        )
    if len(candidate) < settings.min_password_length:
        raise invalid_argument(
            Reason.ERROR_REASON_PASSWORD_TOO_WEAK,
            f"password must be at least {settings.min_password_length} characters",
            field="password",
            metadata={"min_length": str(settings.min_password_length)},
        )
    if len(candidate) > MAX_PASSWORD_LENGTH:
        raise invalid_argument(
            Reason.ERROR_REASON_FIELD_TOO_LONG,
            f"password must be at most {MAX_PASSWORD_LENGTH} characters",
            field="password",
            metadata={"max_length": str(MAX_PASSWORD_LENGTH)},
        )
    if candidate.lower() in _OBVIOUS_PASSWORDS:
        raise invalid_argument(
            Reason.ERROR_REASON_PASSWORD_TOO_WEAK,
            "password is too common",
            field="password",
        )
    # A single repeated character passes a length check but is not a password.
    if len(set(candidate)) < 5:
        raise invalid_argument(
            Reason.ERROR_REASON_PASSWORD_TOO_WEAK,
            "password is too repetitive",
            field="password",
        )


def hash_password(password: str) -> str:
    """Returns an Argon2id PHC string for ``password``."""
    return _hasher().hash(normalize(password))


def verify_password(password_hash: str, password: str) -> bool:
    """Returns whether ``password`` matches ``password_hash``.

    Never raises for a wrong password or a corrupt stored hash — a malformed hash
    in the database must read as "does not match", not as a 500.
    """
    if len(password) > MAX_PASSWORD_LENGTH:
        return False
    try:
        return _hasher().verify(password_hash, normalize(password))
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """Whether ``password_hash`` was made with weaker parameters than current."""
    try:
        return _hasher().check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def dummy_verify() -> None:
    """Burns one Argon2 verification against a throwaway hash.

    Called on the "no such user" path of login so that a wrong email costs the
    same wall-clock time as a wrong password, and the endpoint cannot be used to
    enumerate registered addresses.
    """
    _hasher().verify(_dummy_hash(), "timing-equalizer")


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return _hasher().hash("timing-equalizer")
