"""Session and one-time-token queries.

Sessions are looked up by the SHA-256 of the presented bearer token. Expiry and
revocation are checked in SQL rather than in Python so a revoked session cannot be
used by a process holding a stale copy of the row.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Final

import psycopg

# Tables that share the one-time-token shape. The name is interpolated as an
# identifier from this frozen set only, never from a request.
_TOKEN_TABLES: Final[frozenset[str]] = frozenset(
    {"password_reset_tokens", "email_verification_tokens"}
)


async def create(
    conn: psycopg.AsyncConnection,
    *,
    user_id: str,
    token_hash: bytes,
    client: str,
    user_agent: str,
    ip_address: str | None,
    ttl: timedelta,
) -> dict[str, Any]:
    """Opens a session and returns the stored row."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO sessions (
                user_id, token_hash, client, user_agent, ip_address, expires_at
            )
            VALUES (%s, %s, %s::session_client, %s, %s::inet, now() + %s)
            RETURNING id, user_id, client, user_agent, host(ip_address) AS ip_address,
                      created_at, expires_at, last_used_at
            """,
            (user_id, token_hash, client, user_agent[:500], ip_address, ttl),
        )
        row = await cur.fetchone()
    assert row is not None
    return row


async def resolve(conn: psycopg.AsyncConnection, token_hash: bytes) -> dict[str, Any] | None:
    """Returns the session and its user for a presented token, or ``None``.

    A single joined read: the interceptor runs this on every authenticated call, so
    it must not cost two round-trips. Expired and revoked sessions do not match.
    """
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT s.id            AS session_id,
                   s.expires_at    AS session_expires_at,
                   u.id            AS user_id,
                   u.email,
                   u.display_name,
                   u.role,
                   u.status,
                   u.locale,
                   u.email_verified
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = %s
              AND s.revoked_at IS NULL
              AND s.expires_at > now()
            """,
            (token_hash,),
        )
        return await cur.fetchone()


async def touch(conn: psycopg.AsyncConnection, session_id: str) -> None:
    """Records that the session was just used."""
    async with conn.cursor() as cur:
        await cur.execute("UPDATE sessions SET last_used_at = now() WHERE id = %s", (session_id,))


async def rotate(
    conn: psycopg.AsyncConnection, *, session_id: str, token_hash: bytes, ttl: timedelta
) -> dict[str, Any] | None:
    """Replaces a session's token and extends its expiry.

    Rotating on refresh means a stolen token has a bounded useful life even if the
    theft is never noticed.
    """
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE sessions
            SET token_hash = %s, expires_at = now() + %s, last_used_at = now()
            WHERE id = %s AND revoked_at IS NULL
            RETURNING id, user_id, client, user_agent, host(ip_address) AS ip_address,
                      created_at, expires_at, last_used_at
            """,
            (token_hash, ttl, session_id),
        )
        return await cur.fetchone()


async def list_for_user(conn: psycopg.AsyncConnection, user_id: str) -> list[dict[str, Any]]:
    """Lists a user's live sessions, most recently used first."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id, user_id, client, user_agent, host(ip_address) AS ip_address,
                   created_at, expires_at, last_used_at
            FROM sessions
            WHERE user_id = %s AND revoked_at IS NULL AND expires_at > now()
            ORDER BY last_used_at DESC
            """,
            (user_id,),
        )
        return list(await cur.fetchall())


async def revoke(conn: psycopg.AsyncConnection, *, session_id: str, user_id: str) -> bool:
    """Revokes one of ``user_id``'s sessions. Returns whether it was live.

    Scoped by ``user_id`` in SQL so a caller cannot revoke someone else's session
    by guessing an id.
    """
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE sessions SET revoked_at = now()
            WHERE id = %s AND user_id = %s AND revoked_at IS NULL
            RETURNING id
            """,
            (session_id, user_id),
        )
        return await cur.fetchone() is not None


async def revoke_all_for_user(
    conn: psycopg.AsyncConnection, user_id: str, *, except_session_id: str | None = None
) -> int:
    """Revokes every live session for a user and returns how many were closed.

    Used after a password change: the point is to lock out anyone holding a token
    that the old password could have produced.
    """
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE sessions SET revoked_at = now()
            WHERE user_id = %s
              AND revoked_at IS NULL
              AND (%s::uuid IS NULL OR id <> %s::uuid)
            """,
            (user_id, except_session_id, except_session_id),
        )
        return cur.rowcount


async def delete_expired(conn: psycopg.AsyncConnection, *, older_than: timedelta) -> int:
    """Purges sessions that expired or were revoked longer than ``older_than`` ago.

    Revoked rows are kept for a grace period so "where was I signed in" history
    survives an immediate sign-out.
    """
    async with conn.cursor() as cur:
        await cur.execute(
            """
            DELETE FROM sessions
            WHERE (expires_at < now() - %s)
               OR (revoked_at IS NOT NULL AND revoked_at < now() - %s)
            """,
            (older_than, older_than),
        )
        return cur.rowcount


# --- One-time tokens --------------------------------------------------------


async def create_one_time_token(
    conn: psycopg.AsyncConnection,
    table: str,
    *,
    user_id: str,
    token_hash: bytes,
    ttl: timedelta,
) -> None:
    """Issues a one-time token in ``table``.

    Any unused token for the same user is invalidated first, so requesting a new
    password-reset link cannot leave two working links behind.

    Raises:
        ValueError: If ``table`` is not one of the known token tables.
    """
    if table not in _TOKEN_TABLES:
        raise ValueError(f"unknown token table {table!r}")
    async with conn.cursor() as cur:
        await cur.execute(
            f"UPDATE {table} SET used_at = now() WHERE user_id = %s AND used_at IS NULL",
            (user_id,),
        )
        await cur.execute(
            f"INSERT INTO {table} (user_id, token_hash, expires_at) VALUES (%s, %s, now() + %s)",
            (user_id, token_hash, ttl),
        )


async def consume_one_time_token(
    conn: psycopg.AsyncConnection, table: str, token_hash: bytes
) -> str | None:
    """Marks a one-time token used and returns its user id, or ``None``.

    The ``used_at IS NULL`` guard is in the ``UPDATE`` itself, so two concurrent
    redemptions of the same link cannot both succeed.

    Raises:
        ValueError: If ``table`` is not one of the known token tables.
    """
    if table not in _TOKEN_TABLES:
        raise ValueError(f"unknown token table {table!r}")
    async with conn.cursor() as cur:
        await cur.execute(
            f"""
            UPDATE {table} SET used_at = now()
            WHERE token_hash = %s AND used_at IS NULL AND expires_at > now()
            RETURNING user_id
            """,
            (token_hash,),
        )
        row = await cur.fetchone()
        return row["user_id"] if row else None


async def recent_failed_login_count(
    conn: psycopg.AsyncConnection, *, email: str, since: datetime
) -> int:
    """Counts failed sign-in attempts for ``email`` since ``since``."""
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT count(*) AS failures FROM login_attempts "
            "WHERE email = %s AND succeeded = false AND created_at >= %s",
            (email, since),
        )
        row = await cur.fetchone()
        return int(row["failures"]) if row else 0


async def record_login_attempt(
    conn: psycopg.AsyncConnection,
    *,
    email: str,
    succeeded: bool,
    ip_address: str | None,
) -> None:
    """Appends a sign-in attempt to the rate-limiting log."""
    async with conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO login_attempts (email, succeeded, ip_address) VALUES (%s, %s, %s::inet)",
            (email, succeeded, ip_address),
        )
