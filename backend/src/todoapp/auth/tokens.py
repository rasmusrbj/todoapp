"""Opaque bearer tokens for sessions and one-time links.

Sessions are server-side and opaque rather than self-describing JWTs, so revoking
one is a single ``UPDATE`` instead of a blocklist. Only the SHA-256 of a token is
stored: a database leak therefore does not hand over usable credentials, and
lookup stays a single indexed equality match.

SHA-256 is the right primitive here even though passwords need Argon2 — a 256-bit
random token has no low-entropy guesses to slow down.
"""

from __future__ import annotations

import hashlib
import secrets
from typing import Final

# 32 bytes of entropy, URL-safe base64 (43 characters). Comfortably beyond guessing.
_TOKEN_BYTES: Final = 32

# Prefixes make a leaked token identifiable in a log or a paste, and let secret
# scanners match on them.
SESSION_TOKEN_PREFIX: Final = "tds_"
RESET_TOKEN_PREFIX: Final = "tdr_"
VERIFY_TOKEN_PREFIX: Final = "tdv_"


def generate_token(prefix: str) -> str:
    """Returns a fresh URL-safe token carrying ``prefix``."""
    return f"{prefix}{secrets.token_urlsafe(_TOKEN_BYTES)}"


def hash_token(token: str) -> bytes:
    """Returns the SHA-256 digest stored in place of ``token``.

    The prefix is included in the digest so a token cannot be replayed as a
    different kind of token.
    """
    return hashlib.sha256(token.encode("utf-8")).digest()


def tokens_equal(left: str, right: str) -> bool:
    """Constant-time comparison, for the rare path that compares raw tokens."""
    return secrets.compare_digest(left, right)


def new_session_token() -> tuple[str, bytes]:
    """Returns a new session token and the digest to store."""
    token = generate_token(SESSION_TOKEN_PREFIX)
    return token, hash_token(token)


def new_reset_token() -> tuple[str, bytes]:
    """Returns a new password-reset token and the digest to store."""
    token = generate_token(RESET_TOKEN_PREFIX)
    return token, hash_token(token)


def new_verification_token() -> tuple[str, bytes]:
    """Returns a new email-verification token and the digest to store."""
    token = generate_token(VERIFY_TOKEN_PREFIX)
    return token, hash_token(token)
