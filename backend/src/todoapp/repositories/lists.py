"""List, membership, and label queries.

Access control lives here, in SQL. Every read is filtered by an ``EXISTS`` over
``list_members`` (widened for public lists and platform admins) rather than by a
Python check after the fact, so there is no query shape that can return a list the
caller may not see.
"""

from __future__ import annotations

from typing import Any, Final

import psycopg
from psycopg import sql

from todoapp.repositories.pagination import Page

_LIST_COLUMNS: Final = """
    l.id, l.name, l.description, l.color, l.visibility, l.position,
    l.archived_at, l.created_at, l.updated_at,
    l.owner_id,
    o.display_name AS owner_display_name,
    o.email        AS owner_email,
    o.avatar_url   AS owner_avatar_url
"""

# Counters for the list card. `next_due_at` drives the "next up" line.
_LIST_STATS: Final = """
    (SELECT count(*) FROM tasks t WHERE t.list_id = l.id)          AS total_task_count,
    (SELECT count(*) FROM tasks t WHERE t.list_id = l.id
       AND t.status NOT IN ('done', 'cancelled'))                  AS open_task_count,
    (SELECT count(*) FROM tasks t WHERE t.list_id = l.id
       AND t.status = 'done')                                      AS completed_task_count,
    (SELECT count(*) FROM tasks t WHERE t.list_id = l.id
       AND t.status NOT IN ('done', 'cancelled')
       AND t.due_at < now())                                       AS overdue_task_count,
    (SELECT count(*) FROM list_members m WHERE m.list_id = l.id)   AS member_count,
    (SELECT min(t.due_at) FROM tasks t WHERE t.list_id = l.id
       AND t.status NOT IN ('done', 'cancelled')
       AND t.due_at IS NOT NULL)                                   AS next_due_at
"""

# The caller's role, or NULL when they only reach the list because it is public.
_VIEWER_ROLE: Final = """
    (SELECT m.role FROM list_members m
      WHERE m.list_id = l.id AND m.user_id = %(viewer_id)s)        AS viewer_role
"""

# Readable when a member, when the list is public, or when the caller is an admin.
_READABLE: Final = """
    (
        EXISTS (SELECT 1 FROM list_members m
                 WHERE m.list_id = l.id AND m.user_id = %(viewer_id)s)
        OR l.visibility = 'public'
        OR %(viewer_is_admin)s
    )
"""

_UPDATABLE_COLUMNS: Final[dict[str, str | None]] = {
    "name": None,
    "description": None,
    "color": "list_color",
    "visibility": "list_visibility",
}

_SORT_EXPRESSIONS: Final[dict[str, str]] = {
    "position": "l.position",
    "created_at": "l.created_at",
    "updated_at": "l.updated_at",
    "name": "lower(l.name)",
}


async def get(
    conn: psycopg.AsyncConnection, list_id: str, *, viewer_id: str, viewer_is_admin: bool
) -> dict[str, Any] | None:
    """Returns one list with owner, stats, and the caller's role, or ``None``.

    ``None`` covers both "does not exist" and "not visible to this caller"; the
    service layer reports both as ``NOT_FOUND`` so the API does not disclose that
    someone else's list exists.
    """
    async with conn.cursor() as cur:
        await cur.execute(
            sql.SQL(
                """
                SELECT {cols}, {stats}, {viewer_role}
                FROM lists l
                JOIN users o ON o.id = l.owner_id
                WHERE l.id = %(list_id)s AND {readable}
                """
            ).format(
                cols=sql.SQL(_LIST_COLUMNS),
                stats=sql.SQL(_LIST_STATS),
                viewer_role=sql.SQL(_VIEWER_ROLE),
                readable=sql.SQL(_READABLE),
            ),
            {"list_id": list_id, "viewer_id": viewer_id, "viewer_is_admin": viewer_is_admin},
        )
        return await cur.fetchone()


async def viewer_role(conn: psycopg.AsyncConnection, list_id: str, user_id: str) -> str | None:
    """Returns the caller's ``member_role`` on a list, or ``None`` if not a member.

    This is the cheap check the write paths use before doing anything: it reads one
    indexed row and does not build the full list payload.
    """
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT role FROM list_members WHERE list_id = %s AND user_id = %s",
            (list_id, user_id),
        )
        row = await cur.fetchone()
        return row["role"] if row else None


async def exists_readable(
    conn: psycopg.AsyncConnection, list_id: str, *, viewer_id: str, viewer_is_admin: bool
) -> bool:
    """Whether the list exists and the caller may read it."""
    async with conn.cursor() as cur:
        await cur.execute(
            sql.SQL("SELECT 1 FROM lists l WHERE l.id = %(list_id)s AND {readable}").format(
                readable=sql.SQL(_READABLE)
            ),
            {"list_id": list_id, "viewer_id": viewer_id, "viewer_is_admin": viewer_is_admin},
        )
        return await cur.fetchone() is not None


async def create(
    conn: psycopg.AsyncConnection,
    *,
    owner_id: str,
    name: str,
    description: str,
    color: str,
    visibility: str,
) -> str:
    """Inserts a list plus its owner membership and returns the new id.

    Both rows are written here rather than by a trigger so the ``owner`` membership
    is visible to the same transaction that created the list — the caller's very
    next read has to find it.

    The new list is placed at the top of the owner's board.
    """
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO lists (owner_id, name, description, color, visibility, position)
            VALUES (
                %s, %s, %s, %s::list_color, %s::list_visibility,
                COALESCE((SELECT min(position) - 1 FROM lists WHERE owner_id = %s), 0)
            )
            RETURNING id
            """,
            (owner_id, name, description, color, visibility, owner_id),
        )
        row = await cur.fetchone()
        assert row is not None
        # psycopg returns uuid.UUID; ids are used as dict keys, so normalise to str.
        list_id = str(row["id"])

        await cur.execute(
            """
            INSERT INTO list_members (list_id, user_id, role, invited_by_id)
            VALUES (%s, %s, 'owner', %s)
            """,
            (list_id, owner_id, owner_id),
        )
    return list_id


async def update(conn: psycopg.AsyncConnection, list_id: str, changes: dict[str, Any]) -> bool:
    """Applies a partial update. Returns whether the row still existed.

    Raises:
        ValueError: If ``changes`` names a column that is not updatable.
    """
    if not changes:
        return True
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
            sql.SQL("UPDATE lists SET {assignments} WHERE id = {id} RETURNING id").format(
                assignments=sql.SQL(", ").join(assignments), id=sql.Placeholder()
            ),
            (*changes.values(), list_id),
        )
        return await cur.fetchone() is not None


async def set_archived(conn: psycopg.AsyncConnection, list_id: str, *, archived: bool) -> bool:
    """Archives or restores a list. Returns whether the row existed."""
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE lists SET archived_at = CASE WHEN %s THEN now() ELSE NULL END "
            "WHERE id = %s RETURNING id",
            (archived, list_id),
        )
        return await cur.fetchone() is not None


async def delete(conn: psycopg.AsyncConnection, list_id: str) -> bool:
    """Hard-deletes a list. Tasks, labels and memberships cascade with it."""
    async with conn.cursor() as cur:
        await cur.execute("DELETE FROM lists WHERE id = %s RETURNING id", (list_id,))
        return await cur.fetchone() is not None


async def reorder(conn: psycopg.AsyncConnection, *, owner_id: str, list_ids: list[str]) -> int:
    """Writes a new manual order for lists the caller owns.

    Ids that the caller does not own are ignored rather than rejected: the client
    sends the board it can see, and a concurrent unshare should not fail the drag.

    Returns:
        How many rows were repositioned.
    """
    if not list_ids:
        return 0
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE lists AS l
            SET position = new_order.position
            FROM (SELECT id, ordinality - 1 AS position
                    FROM unnest(%s::uuid[]) WITH ORDINALITY AS t(id, ordinality)) AS new_order
            WHERE l.id = new_order.id AND l.owner_id = %s
            """,
            (list_ids, owner_id),
        )
        return cur.rowcount


async def search(
    conn: psycopg.AsyncConnection,
    *,
    page: Page,
    viewer_id: str,
    viewer_is_admin: bool,
    query: str,
    visibilities: list[str],
    roles: list[str],
    include_archived: bool,
    sort_field: str,
    descending: bool,
) -> tuple[list[dict[str, Any]], int]:
    """Lists the lists a caller can see, filtered and sorted.

    Returns:
        The page of rows (with one sentinel row still attached) and the total count.
    """
    conditions: list[sql.Composable] = [sql.SQL(_READABLE)]
    params: dict[str, Any] = {"viewer_id": viewer_id, "viewer_is_admin": viewer_is_admin}

    if not include_archived:
        conditions.append(sql.SQL("l.archived_at IS NULL"))
    if query.strip():
        conditions.append(sql.SQL("(l.name ILIKE %(query)s OR l.description ILIKE %(query)s)"))
        params["query"] = f"%{query.strip()}%"
    if visibilities:
        conditions.append(sql.SQL("l.visibility = ANY(%(visibilities)s::list_visibility[])"))
        params["visibilities"] = visibilities
    if roles:
        # Narrowing by role implies membership, so a public non-member list drops out.
        conditions.append(
            sql.SQL(
                "EXISTS (SELECT 1 FROM list_members m2 WHERE m2.list_id = l.id "
                "AND m2.user_id = %(viewer_id)s AND m2.role = ANY(%(roles)s::member_role[]))"
            )
        )
        params["roles"] = roles

    where = sql.SQL(" AND ").join(conditions)
    order = sql.SQL(_SORT_EXPRESSIONS.get(sort_field, _SORT_EXPRESSIONS["position"]))
    direction = sql.SQL("DESC" if descending else "ASC")

    async with conn.cursor() as cur:
        await cur.execute(
            sql.SQL("SELECT count(*) AS total FROM lists l WHERE {where}").format(where=where),
            params,
        )
        total_row = await cur.fetchone()
        total = int(total_row["total"]) if total_row else 0

        await cur.execute(
            sql.SQL(
                """
                SELECT {cols}, {stats}, {viewer_role}
                FROM lists l
                JOIN users o ON o.id = l.owner_id
                WHERE {where}
                ORDER BY {order} {direction} NULLS LAST, l.created_at DESC, l.id
                LIMIT %(limit)s OFFSET %(offset)s
                """
            ).format(
                cols=sql.SQL(_LIST_COLUMNS),
                stats=sql.SQL(_LIST_STATS),
                viewer_role=sql.SQL(_VIEWER_ROLE),
                where=where,
                order=order,
                direction=direction,
            ),
            {**params, "limit": page.sql_limit, "offset": page.offset},
        )
        return list(await cur.fetchall()), total


# --- Membership -------------------------------------------------------------


async def list_members(conn: psycopg.AsyncConnection, list_id: str) -> list[dict[str, Any]]:
    """Lists a list's members, owner first, then by role and name."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT m.id, m.list_id, m.role, m.created_at, m.updated_at,
                   u.id AS user_id, u.display_name, u.email, u.avatar_url,
                   inviter.id           AS invited_by_id,
                   inviter.display_name AS invited_by_display_name,
                   inviter.email        AS invited_by_email,
                   inviter.avatar_url   AS invited_by_avatar_url
            FROM list_members m
            JOIN users u ON u.id = m.user_id
            LEFT JOIN users inviter ON inviter.id = m.invited_by_id
            WHERE m.list_id = %s
            ORDER BY m.role, lower(u.display_name)
            """,
            (list_id,),
        )
        return list(await cur.fetchall())


async def members_for_lists(
    conn: psycopg.AsyncConnection, list_ids: list[str]
) -> dict[str, list[dict[str, Any]]]:
    """Loads members for many lists at once, grouped by list id.

    One query for the whole page instead of one per list — the N+1 this avoids is
    the difference between 1 and 26 round-trips on the board screen.
    """
    if not list_ids:
        return {}
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT m.id, m.list_id, m.role, m.created_at, m.updated_at,
                   u.id AS user_id, u.display_name, u.email, u.avatar_url,
                   inviter.id           AS invited_by_id,
                   inviter.display_name AS invited_by_display_name,
                   inviter.email        AS invited_by_email,
                   inviter.avatar_url   AS invited_by_avatar_url
            FROM list_members m
            JOIN users u ON u.id = m.user_id
            LEFT JOIN users inviter ON inviter.id = m.invited_by_id
            WHERE m.list_id = ANY(%s::uuid[])
            ORDER BY m.list_id, m.role, lower(u.display_name)
            """,
            (list_ids,),
        )
        grouped: dict[str, list[dict[str, Any]]] = {str(list_id): [] for list_id in list_ids}
        for row in await cur.fetchall():
            grouped.setdefault(str(row["list_id"]), []).append(row)
        return grouped


async def get_member(
    conn: psycopg.AsyncConnection, *, list_id: str, user_id: str
) -> dict[str, Any] | None:
    """Returns one membership row with its user, or ``None``."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT m.id, m.list_id, m.role, m.created_at, m.updated_at,
                   u.id AS user_id, u.display_name, u.email, u.avatar_url,
                   inviter.id           AS invited_by_id,
                   inviter.display_name AS invited_by_display_name,
                   inviter.email        AS invited_by_email,
                   inviter.avatar_url   AS invited_by_avatar_url
            FROM list_members m
            JOIN users u ON u.id = m.user_id
            LEFT JOIN users inviter ON inviter.id = m.invited_by_id
            WHERE m.list_id = %s AND m.user_id = %s
            """,
            (list_id, user_id),
        )
        return await cur.fetchone()


async def add_member(
    conn: psycopg.AsyncConnection,
    *,
    list_id: str,
    user_id: str,
    role: str,
    invited_by_id: str,
) -> None:
    """Grants ``user_id`` access to a list.

    Raises:
        psycopg.errors.UniqueViolation: If the user is already a member, or the
            role is ``owner`` and the list already has one.
    """
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO list_members (list_id, user_id, role, invited_by_id)
            VALUES (%s, %s, %s::member_role, %s)
            """,
            (list_id, user_id, role, invited_by_id),
        )


async def set_member_role(
    conn: psycopg.AsyncConnection, *, list_id: str, user_id: str, role: str
) -> bool:
    """Changes a member's role. Returns whether the membership existed."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE list_members SET role = %s::member_role
            WHERE list_id = %s AND user_id = %s
            RETURNING id
            """,
            (role, list_id, user_id),
        )
        return await cur.fetchone() is not None


async def remove_member(conn: psycopg.AsyncConnection, *, list_id: str, user_id: str) -> bool:
    """Revokes access. Returns whether a membership was removed.

    Tasks assigned to the removed member keep their assignee: dropping it would
    silently lose who was working on what. The service layer decides whether to
    clear assignments, and does so explicitly.
    """
    async with conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM list_members WHERE list_id = %s AND user_id = %s RETURNING id",
            (list_id, user_id),
        )
        return await cur.fetchone() is not None


# --- Labels -----------------------------------------------------------------


async def list_labels(conn: psycopg.AsyncConnection, list_id: str) -> list[dict[str, Any]]:
    """Lists a list's labels with their usage counts."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT lb.id, lb.list_id, lb.name, lb.color, lb.created_at, lb.updated_at,
                   (SELECT count(*) FROM task_labels tl WHERE tl.label_id = lb.id) AS task_count
            FROM labels lb
            WHERE lb.list_id = %s
            ORDER BY lower(lb.name)
            """,
            (list_id,),
        )
        return list(await cur.fetchall())


async def labels_for_lists(
    conn: psycopg.AsyncConnection, list_ids: list[str]
) -> dict[str, list[dict[str, Any]]]:
    """Loads labels for many lists at once, grouped by list id."""
    if not list_ids:
        return {}
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id, list_id, name, color
            FROM labels
            WHERE list_id = ANY(%s::uuid[])
            ORDER BY list_id, lower(name)
            """,
            (list_ids,),
        )
        grouped: dict[str, list[dict[str, Any]]] = {str(list_id): [] for list_id in list_ids}
        for row in await cur.fetchall():
            grouped.setdefault(str(row["list_id"]), []).append(row)
        return grouped


async def get_label(conn: psycopg.AsyncConnection, label_id: str) -> dict[str, Any] | None:
    """Returns one label with its usage count, or ``None``."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT lb.id, lb.list_id, lb.name, lb.color, lb.created_at, lb.updated_at,
                   (SELECT count(*) FROM task_labels tl WHERE tl.label_id = lb.id) AS task_count
            FROM labels lb
            WHERE lb.id = %s
            """,
            (label_id,),
        )
        return await cur.fetchone()


async def create_label(
    conn: psycopg.AsyncConnection, *, list_id: str, name: str, color: str
) -> str:
    """Inserts a label and returns its id.

    Raises:
        psycopg.errors.UniqueViolation: If the name is already used on this list.
    """
    async with conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO labels (list_id, name, color) VALUES (%s, %s, %s::list_color) "
            "RETURNING id",
            (list_id, name, color),
        )
        row = await cur.fetchone()
    assert row is not None
    # psycopg returns uuid.UUID; ids are used as dict keys, so normalise to str.
    return str(row["id"])


async def update_label(
    conn: psycopg.AsyncConnection, label_id: str, *, name: str | None, color: str | None
) -> bool:
    """Applies a partial label update. Returns whether the row existed."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE labels
            SET name  = COALESCE(%s, name),
                color = COALESCE(%s::list_color, color)
            WHERE id = %s
            RETURNING id
            """,
            (name, color, label_id),
        )
        return await cur.fetchone() is not None


async def delete_label(conn: psycopg.AsyncConnection, label_id: str) -> bool:
    """Deletes a label. Its task assignments cascade away."""
    async with conn.cursor() as cur:
        await cur.execute("DELETE FROM labels WHERE id = %s RETURNING id", (label_id,))
        return await cur.fetchone() is not None
