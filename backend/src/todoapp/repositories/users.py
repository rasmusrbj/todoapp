"""User and account queries."""

from __future__ import annotations

from typing import Any, Final

import psycopg
from psycopg import sql

from todoapp.repositories.pagination import Page

# Selected everywhere a full user is returned. `password_hash` is deliberately
# absent — only :func:`get_credentials_by_email` reads it, and only to verify.
_USER_COLUMNS: Final = """
    u.id, u.email, u.display_name, u.bio, u.avatar_url, u.time_zone,
    u.role, u.status, u.locale, u.theme, u.email_verified, u.status_reason,
    u.last_seen_at, u.created_at, u.updated_at
"""

# Correlated counters, so a profile or admin row needs no second round-trip.
# Task counters follow the *assignee*, which is what "my open tasks" means.
_USER_STATS: Final = """
    (SELECT count(*) FROM lists l
      WHERE l.owner_id = u.id AND l.archived_at IS NULL)          AS owned_list_count,
    (SELECT count(*) FROM list_members m
      WHERE m.user_id = u.id AND m.role <> 'owner')               AS shared_list_count,
    (SELECT count(*) FROM tasks t
      WHERE t.assignee_id = u.id
        AND t.status NOT IN ('done', 'cancelled'))                AS open_task_count,
    (SELECT count(*) FROM tasks t
      WHERE t.assignee_id = u.id AND t.status = 'done')           AS completed_task_count,
    (SELECT count(*) FROM tasks t
      WHERE t.assignee_id = u.id
        AND t.status NOT IN ('done', 'cancelled')
        AND t.due_at < now())                                     AS overdue_task_count
"""

# Columns :func:`update_user` may write, mapped to their PostgreSQL cast where the
# value is an enum. Anything outside this allowlist cannot be reached from a
# request, which is what keeps the dynamic UPDATE below safe.
_UPDATABLE_COLUMNS: Final[dict[str, str | None]] = {
    "display_name": None,
    "bio": None,
    "avatar_url": None,
    "time_zone": None,
    "locale": "locale",
    "theme": "theme_preference",
    "role": "user_role",
}


async def get_by_id(conn: psycopg.AsyncConnection, user_id: str) -> dict[str, Any] | None:
    """Returns one user with stats, or ``None``."""
    async with conn.cursor() as cur:
        await cur.execute(
            sql.SQL("SELECT {cols}, {stats} FROM users u WHERE u.id = %s").format(
                cols=sql.SQL(_USER_COLUMNS), stats=sql.SQL(_USER_STATS)
            ),
            (user_id,),
        )
        return await cur.fetchone()


async def get_by_email(conn: psycopg.AsyncConnection, email: str) -> dict[str, Any] | None:
    """Returns one user with stats by email, case-insensitively, or ``None``."""
    async with conn.cursor() as cur:
        await cur.execute(
            sql.SQL("SELECT {cols}, {stats} FROM users u WHERE u.email = %s").format(
                cols=sql.SQL(_USER_COLUMNS), stats=sql.SQL(_USER_STATS)
            ),
            (email,),
        )
        return await cur.fetchone()


async def get_credentials_by_email(
    conn: psycopg.AsyncConnection, email: str
) -> dict[str, Any] | None:
    """Returns the columns login needs: id, hash, status, and verification flag.

    Kept separate from :func:`get_by_email` so the password hash is only ever read
    on the one code path that has a reason to.
    """
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id, email, password_hash, status, email_verified, locale, role, display_name
            FROM users
            WHERE email = %s
            """,
            (email,),
        )
        return await cur.fetchone()


async def email_exists(conn: psycopg.AsyncConnection, email: str) -> bool:
    """Whether an account already uses ``email``."""
    async with conn.cursor() as cur:
        await cur.execute("SELECT 1 FROM users WHERE email = %s", (email,))
        return await cur.fetchone() is not None


async def create(
    conn: psycopg.AsyncConnection,
    *,
    email: str,
    password_hash: str,
    display_name: str,
    role: str,
    status: str,
    locale: str,
    time_zone: str,
) -> dict[str, Any]:
    """Inserts a user and returns it with stats.

    Raises:
        psycopg.errors.UniqueViolation: If the email is already registered. The
            service layer translates this into ``ALREADY_EXISTS``.
    """
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO users (
                email, password_hash, display_name, role, status, locale, time_zone
            )
            VALUES (%s, %s, %s, %s::user_role, %s::user_status, %s::locale, %s)
            RETURNING id
            """,
            (email, password_hash, display_name, role, status, locale, time_zone),
        )
        row = await cur.fetchone()
    assert row is not None
    created = await get_by_id(conn, str(row["id"]))
    assert created is not None
    return created


async def update(
    conn: psycopg.AsyncConnection, user_id: str, changes: dict[str, Any]
) -> dict[str, Any] | None:
    """Applies a partial update and returns the user, or ``None`` if it is gone.

    Args:
        conn: Open connection.
        user_id: Target user.
        changes: Column name to value. Keys must be in :data:`_UPDATABLE_COLUMNS`.

    Raises:
        ValueError: If ``changes`` contains a column that is not updatable. That
            is a programming error, not user input — the service layer builds this
            dict from named request fields.
    """
    if not changes:
        return await get_by_id(conn, user_id)

    unknown = set(changes) - set(_UPDATABLE_COLUMNS)
    if unknown:
        raise ValueError(f"columns not updatable: {sorted(unknown)}")

    assignments = [
        sql.SQL("{col} = {value}").format(
            col=sql.Identifier(column),
            value=(
                sql.SQL("{ph}::{cast}").format(ph=sql.Placeholder(), cast=sql.Identifier(cast))
                if (cast := _UPDATABLE_COLUMNS[column])
                else sql.Placeholder()
            ),
        )
        for column in changes
    ]

    async with conn.cursor() as cur:
        await cur.execute(
            sql.SQL("UPDATE users SET {assignments} WHERE id = {user_id} RETURNING id").format(
                assignments=sql.SQL(", ").join(assignments), user_id=sql.Placeholder()
            ),
            (*changes.values(), user_id),
        )
        if await cur.fetchone() is None:
            return None
    return await get_by_id(conn, user_id)


async def set_status(
    conn: psycopg.AsyncConnection, user_id: str, *, status: str, reason: str
) -> dict[str, Any] | None:
    """Transitions an account's status and records why."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE users
            SET status = %s::user_status, status_reason = %s
            WHERE id = %s
            RETURNING id
            """,
            (status, reason, user_id),
        )
        if await cur.fetchone() is None:
            return None
    return await get_by_id(conn, user_id)


async def set_password_hash(
    conn: psycopg.AsyncConnection, user_id: str, password_hash: str
) -> bool:
    """Replaces the stored hash. Returns whether the user existed."""
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s RETURNING id",
            (password_hash, user_id),
        )
        return await cur.fetchone() is not None


async def mark_email_verified(conn: psycopg.AsyncConnection, user_id: str) -> dict[str, Any] | None:
    """Confirms the address and promotes a pending account to active."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE users
            SET email_verified = true,
                status = CASE WHEN status = 'pending_verification'
                              THEN 'active'::user_status ELSE status END
            WHERE id = %s
            RETURNING id
            """,
            (user_id,),
        )
        if await cur.fetchone() is None:
            return None
    return await get_by_id(conn, user_id)


async def touch_last_seen(conn: psycopg.AsyncConnection, user_id: str) -> None:
    """Records that the user was active just now.

    Fire-and-forget: a failure here must never fail the surrounding RPC, so the
    caller runs it outside the request's transaction.
    """
    async with conn.cursor() as cur:
        await cur.execute("UPDATE users SET last_seen_at = now() WHERE id = %s", (user_id,))


async def delete(conn: psycopg.AsyncConnection, user_id: str) -> bool:
    """Hard-deletes the user. Returns whether a row was removed.

    Every dependent row goes with it via ``ON DELETE CASCADE`` — sessions, owned
    lists and their tasks. Rows that merely reference the user (a task they were
    assigned, a comment they wrote) survive with a null reference, so other
    people's lists do not lose content when someone leaves.
    """
    async with conn.cursor() as cur:
        await cur.execute("DELETE FROM users WHERE id = %s RETURNING id", (user_id,))
        return await cur.fetchone() is not None


# Sort field to SQL expression. The ORDER BY is built from this allowlist rather
# than from request text, so no request can inject a sort expression.
_SORT_EXPRESSIONS: Final[dict[str, str]] = {
    "created_at": "u.created_at",
    "display_name": "lower(u.display_name)",
    "email": "u.email",
    "last_seen_at": "u.last_seen_at",
}


async def search(
    conn: psycopg.AsyncConnection,
    *,
    page: Page,
    query: str,
    roles: list[str],
    statuses: list[str],
    sort_field: str,
    descending: bool,
) -> tuple[list[dict[str, Any]], int]:
    """Lists users for the admin screen.

    Args:
        conn: Open connection.
        page: Resolved window.
        query: Free text matched against display name and email. Empty disables it.
        roles: Allowed ``user_role`` labels. Empty means all.
        statuses: Allowed ``user_status`` labels. Empty means all.
        sort_field: Key into :data:`_SORT_EXPRESSIONS`.
        descending: Sort direction.

    Returns:
        The page of rows (with one sentinel row still attached) and the total count.
    """
    conditions: list[sql.Composable] = [sql.SQL("true")]
    params: list[Any] = []

    if query.strip():
        conditions.append(sql.SQL("(u.display_name ILIKE %s OR u.email ILIKE %s)"))
        pattern = f"%{query.strip()}%"
        params += [pattern, pattern]
    if roles:
        conditions.append(sql.SQL("u.role = ANY(%s::user_role[])"))
        params.append(roles)
    if statuses:
        conditions.append(sql.SQL("u.status = ANY(%s::user_status[])"))
        params.append(statuses)

    where = sql.SQL(" AND ").join(conditions)
    order = sql.SQL(_SORT_EXPRESSIONS.get(sort_field, _SORT_EXPRESSIONS["created_at"]))
    direction = sql.SQL("DESC" if descending else "ASC")

    async with conn.cursor() as cur:
        await cur.execute(
            sql.SQL("SELECT count(*) AS total FROM users u WHERE {where}").format(where=where),
            params,
        )
        total_row = await cur.fetchone()
        total = int(total_row["total"]) if total_row else 0

        await cur.execute(
            sql.SQL(
                """
                SELECT {cols}, {stats}
                FROM users u
                WHERE {where}
                ORDER BY {order} {direction} NULLS LAST, u.id
                LIMIT %s OFFSET %s
                """
            ).format(
                cols=sql.SQL(_USER_COLUMNS),
                stats=sql.SQL(_USER_STATS),
                where=where,
                order=order,
                direction=direction,
            ),
            [*params, page.sql_limit, page.offset],
        )
        return list(await cur.fetchall()), total


async def type_ahead(
    conn: psycopg.AsyncConnection, *, query: str, limit: int, exclude_user_id: str
) -> list[dict[str, Any]]:
    """Finds active users by name or email prefix, for the share dialog.

    Only active accounts are returned, and the caller is excluded — inviting
    yourself or a deactivated account is never a useful suggestion. An empty query
    returns nothing rather than the whole table.
    """
    if not query.strip():
        return []
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id, display_name, email, avatar_url
            FROM users
            WHERE status = 'active'
              AND id <> %s
              AND (display_name ILIKE %s OR email ILIKE %s)
            ORDER BY
                -- Prefix matches first, then alphabetically.
                (display_name ILIKE %s OR email ILIKE %s) DESC,
                lower(display_name)
            LIMIT %s
            """,
            (
                exclude_user_id,
                f"%{query.strip()}%",
                f"%{query.strip()}%",
                f"{query.strip()}%",
                f"{query.strip()}%",
                limit,
            ),
        )
        return list(await cur.fetchall())
