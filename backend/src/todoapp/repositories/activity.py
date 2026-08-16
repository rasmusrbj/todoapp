"""Activity-feed queries.

The table is append-only. Nothing here updates or deletes a row: an audit trail
that can be rewritten is not one.
"""

from __future__ import annotations

from typing import Any, Final

import psycopg
from psycopg import sql

from todoapp.repositories.pagination import Page

_ACTIVITY_COLUMNS: Final = """
    a.id, a.action, a.target_type, a.target_id, a.target_label,
    a.field, a.from_value, a.to_value, a.created_at,
    actor.id           AS actor_id,
    actor.display_name AS actor_display_name,
    actor.email        AS actor_email,
    actor.avatar_url   AS actor_avatar_url,
    l.id         AS list_id,
    l.name       AS list_name,
    l.color      AS list_color,
    l.visibility AS list_visibility
"""


async def record(
    conn: psycopg.AsyncConnection,
    *,
    actor_id: str | None,
    action: str,
    target_type: str,
    target_id: str,
    target_label: str,
    list_id: str | None = None,
    task_id: str | None = None,
    field: str = "",
    from_value: str = "",
    to_value: str = "",
) -> None:
    """Appends one activity entry.

    Called inside the same transaction as the change it describes, so the feed can
    never claim something that was rolled back.

    Args:
        conn: Open connection, inside the caller's transaction.
        actor_id: Who did it, or ``None`` for a system action.
        action: PostgreSQL ``activity_action`` label.
        target_type: PostgreSQL ``activity_target_type`` label.
        target_id: The affected row's id.
        target_label: The target's human-readable name *at this moment*, stored so
            the feed survives a later rename or delete.
        list_id: Owning list, when there is one.
        task_id: Owning task, when there is one.
        field: Changed field name, for ``updated``-style actions.
        from_value: Previous value as an enum label or raw text — never localized.
        to_value: New value, same rules.
    """
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO activities (
                actor_id, list_id, task_id, action, target_type, target_id,
                target_label, field, from_value, to_value
            )
            VALUES (
                %s, %s, %s, %s::activity_action, %s::activity_target_type, %s,
                %s, %s, %s, %s
            )
            """,
            (
                actor_id,
                list_id,
                task_id,
                action,
                target_type,
                target_id,
                target_label[:200],
                field,
                from_value,
                to_value,
            ),
        )


async def search(
    conn: psycopg.AsyncConnection,
    *,
    page: Page,
    viewer_id: str,
    viewer_is_admin: bool,
    list_id: str | None,
    task_id: str | None,
    actions: list[str],
) -> tuple[list[dict[str, Any]], int]:
    """Lists activity the caller may see, newest first.

    Visibility follows the list: an entry whose list has been deleted (``list_id``
    is null) is only shown to the actor themselves, so orphaned history does not
    leak sideways.

    Returns:
        The page of rows (with one sentinel row still attached) and the total count.
    """
    conditions: list[sql.Composable] = [
        sql.SQL(
            """
            (
                (a.list_id IS NOT NULL AND (
                    EXISTS (SELECT 1 FROM list_members m
                             WHERE m.list_id = a.list_id AND m.user_id = %(viewer_id)s)
                    OR l.visibility = 'public'
                    OR %(viewer_is_admin)s
                ))
                OR (a.list_id IS NULL AND (a.actor_id = %(viewer_id)s OR %(viewer_is_admin)s))
            )
            """
        )
    ]
    params: dict[str, Any] = {"viewer_id": viewer_id, "viewer_is_admin": viewer_is_admin}

    if list_id is not None:
        conditions.append(sql.SQL("a.list_id = %(list_id)s"))
        params["list_id"] = list_id
    if task_id is not None:
        conditions.append(sql.SQL("a.task_id = %(task_id)s"))
        params["task_id"] = task_id
    if actions:
        conditions.append(sql.SQL("a.action = ANY(%(actions)s::activity_action[])"))
        params["actions"] = actions

    where = sql.SQL(" AND ").join(conditions)
    joins = sql.SQL(
        """
        FROM activities a
        LEFT JOIN users actor ON actor.id = a.actor_id
        LEFT JOIN lists l     ON l.id = a.list_id
        """
    )

    async with conn.cursor() as cur:
        await cur.execute(
            sql.SQL("SELECT count(*) AS total {joins} WHERE {where}").format(
                joins=joins, where=where
            ),
            params,
        )
        total_row = await cur.fetchone()
        total = int(total_row["total"]) if total_row else 0

        await cur.execute(
            sql.SQL(
                """
                SELECT {cols} {joins}
                WHERE {where}
                ORDER BY a.created_at DESC, a.id DESC
                LIMIT %(limit)s OFFSET %(offset)s
                """
            ).format(cols=sql.SQL(_ACTIVITY_COLUMNS), joins=joins, where=where),
            {**params, "limit": page.sql_limit, "offset": page.offset},
        )
        return list(await cur.fetchall()), total
