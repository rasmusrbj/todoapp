"""Task, subtask, and comment queries.

A task is reachable exactly when its parent list is, so every statement here joins
``lists`` and reuses the same readability predicate as
:mod:`todoapp.repositories.lists`. Nothing trusts a list id that arrived in a
request without re-deriving it from the task row.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Final

import psycopg
from psycopg import sql

from todoapp.repositories.pagination import Page

_TASK_COLUMNS: Final = """
    t.id, t.title, t.description, t.status, t.priority, t.position,
    t.due_at, t.due_has_time, t.starts_at, t.completed_at,
    t.estimate_minutes,
    t.recurrence_frequency, t.recurrence_interval, t.recurrence_until,
    t.created_at, t.updated_at,
    l.id AS list_id, l.name AS list_name, l.color AS list_color,
    l.visibility AS list_visibility,
    creator.id           AS created_by_id,
    creator.display_name AS created_by_display_name,
    creator.email        AS created_by_email,
    creator.avatar_url   AS created_by_avatar_url,
    assignee.id           AS assignee_id,
    assignee.display_name AS assignee_display_name,
    assignee.email        AS assignee_email,
    assignee.avatar_url   AS assignee_avatar_url,
    completer.id           AS completed_by_id,
    completer.display_name AS completed_by_display_name,
    completer.email        AS completed_by_email,
    completer.avatar_url   AS completed_by_avatar_url,
    (t.status NOT IN ('done', 'cancelled') AND t.due_at IS NOT NULL AND t.due_at < now())
        AS overdue,
    (SELECT count(*) FROM comments c WHERE c.task_id = t.id)  AS comment_count,
    (SELECT count(*) FROM subtasks s WHERE s.task_id = t.id)  AS subtask_count,
    (SELECT count(*) FROM subtasks s
      WHERE s.task_id = t.id AND s.completed_at IS NOT NULL)  AS completed_subtask_count
"""

_JOINS: Final = """
    FROM tasks t
    JOIN lists l          ON l.id = t.list_id
    LEFT JOIN users creator   ON creator.id = t.created_by_id
    LEFT JOIN users assignee  ON assignee.id = t.assignee_id
    LEFT JOIN users completer ON completer.id = t.completed_by_id
"""

# Same rule as lists.py: member, public list, or platform admin.
_READABLE: Final = """
    (
        EXISTS (SELECT 1 FROM list_members m
                 WHERE m.list_id = l.id AND m.user_id = %(viewer_id)s)
        OR l.visibility = 'public'
        OR %(viewer_is_admin)s
    )
"""

_UPDATABLE_COLUMNS: Final[dict[str, str | None]] = {
    "title": None,
    "description": None,
    "priority": "task_priority",
    "estimate_minutes": None,
    "due_at": "timestamptz",
    "due_has_time": None,
    "starts_at": "timestamptz",
    "recurrence_frequency": "recurrence_frequency",
    "recurrence_interval": None,
    "recurrence_until": "timestamptz",
}

_SORT_EXPRESSIONS: Final[dict[str, str]] = {
    "position": "t.position",
    "created_at": "t.created_at",
    "updated_at": "t.updated_at",
    "due_at": "t.due_at",
    "priority": "t.priority",
    "title": "lower(t.title)",
}

TERMINAL_STATUSES: Final = ("done", "cancelled")


async def get(
    conn: psycopg.AsyncConnection, task_id: str, *, viewer_id: str, viewer_is_admin: bool
) -> dict[str, Any] | None:
    """Returns one task with its list, people, and counters, or ``None``."""
    async with conn.cursor() as cur:
        await cur.execute(
            sql.SQL("SELECT {cols} {joins} WHERE t.id = %(task_id)s AND {readable}").format(
                cols=sql.SQL(_TASK_COLUMNS),
                joins=sql.SQL(_JOINS),
                readable=sql.SQL(_READABLE),
            ),
            {"task_id": task_id, "viewer_id": viewer_id, "viewer_is_admin": viewer_is_admin},
        )
        return await cur.fetchone()


async def get_list_id(conn: psycopg.AsyncConnection, task_id: str) -> str | None:
    """Returns the parent list id, or ``None`` if the task is gone.

    Write paths call this first and then authorize against the list, rather than
    trusting a ``list_id`` supplied alongside the task id in a request.
    """
    async with conn.cursor() as cur:
        await cur.execute("SELECT list_id FROM tasks WHERE id = %s", (task_id,))
        row = await cur.fetchone()
        return str(row["list_id"]) if row else None


async def create(
    conn: psycopg.AsyncConnection,
    *,
    list_id: str,
    created_by_id: str,
    title: str,
    description: str,
    status: str,
    priority: str,
    assignee_id: str | None,
    due_at: datetime | None,
    due_has_time: bool,
    starts_at: datetime | None,
    estimate_minutes: int,
    recurrence_frequency: str,
    recurrence_interval: int,
    recurrence_until: datetime | None,
) -> str:
    """Inserts a task at the top of its list and returns the new id.

    ``completed_at`` is derived from ``status`` here rather than accepted from the
    caller, which is what keeps the ``tasks_completed_at_matches_status`` constraint
    satisfiable from a single create call.

    Every placeholder carries an explicit cast. psycopg collapses repeated named
    parameters into one positional parameter, so a value used once as a ``uuid``
    column and once inside a ``CASE`` branch would otherwise leave PostgreSQL unable
    to deduce a single type for it.
    """
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO tasks (
                list_id, created_by_id, assignee_id, title, description,
                status, priority, position,
                due_at, due_has_time, starts_at, estimate_minutes,
                recurrence_frequency, recurrence_interval, recurrence_until,
                completed_at, completed_by_id
            )
            VALUES (
                %(list_id)s::uuid, %(created_by_id)s::uuid, %(assignee_id)s::uuid,
                %(title)s::text, %(description)s::text,
                %(status)s::task_status, %(priority)s::task_priority,
                COALESCE(
                    (SELECT min(position) - 1 FROM tasks WHERE list_id = %(list_id)s::uuid), 0
                ),
                %(due_at)s::timestamptz, %(due_has_time)s::boolean,
                %(starts_at)s::timestamptz, %(estimate_minutes)s::integer,
                %(recurrence_frequency)s::recurrence_frequency,
                %(recurrence_interval)s::integer, %(recurrence_until)s::timestamptz,
                CASE WHEN %(status)s::task_status IN ('done', 'cancelled') THEN now() END,
                CASE WHEN %(status)s::task_status IN ('done', 'cancelled')
                     THEN %(created_by_id)s::uuid END
            )
            RETURNING id
            """,
            {
                "list_id": list_id,
                "created_by_id": created_by_id,
                "assignee_id": assignee_id,
                "title": title,
                "description": description,
                "status": status,
                "priority": priority,
                "due_at": due_at,
                "due_has_time": due_has_time,
                "starts_at": starts_at,
                "estimate_minutes": estimate_minutes,
                "recurrence_frequency": recurrence_frequency,
                "recurrence_interval": recurrence_interval,
                "recurrence_until": recurrence_until,
            },
        )
        row = await cur.fetchone()
    assert row is not None
    # psycopg returns uuid.UUID; ids are used as dict keys, so normalise to str.
    return str(row["id"])


async def update(conn: psycopg.AsyncConnection, task_id: str, changes: dict[str, Any]) -> bool:
    """Applies a partial update. Returns whether the row existed.

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
            sql.SQL("UPDATE tasks SET {assignments} WHERE id = {id} RETURNING id").format(
                assignments=sql.SQL(", ").join(assignments), id=sql.Placeholder()
            ),
            (*changes.values(), task_id),
        )
        return await cur.fetchone() is not None


async def set_status(
    conn: psycopg.AsyncConnection, task_id: str, *, status: str, actor_id: str
) -> dict[str, Any] | None:
    """Transitions a task's status, stamping or clearing completion metadata.

    Returns:
        A row with ``old_status`` and ``status``, or ``None`` if the task is gone.
        The service layer needs the old value to write a meaningful activity entry
        and to decide whether a recurrence should roll forward.

    The ``FOR UPDATE`` in the CTE locks the row for the rest of the transaction, so
    two clients ticking the same task off at once cannot both read ``todo`` as the
    previous status and both spawn a next occurrence.
    """
    async with conn.cursor() as cur:
        await cur.execute(
            """
            WITH before AS (
                SELECT id, status FROM tasks WHERE id = %(task_id)s FOR UPDATE
            )
            UPDATE tasks SET
                status = %(status)s::task_status,
                completed_at = CASE
                    WHEN %(status)s::task_status IN ('done', 'cancelled')
                        THEN COALESCE(tasks.completed_at, now())
                    ELSE NULL END,
                completed_by_id = CASE
                    WHEN %(status)s::task_status IN ('done', 'cancelled')
                        THEN COALESCE(tasks.completed_by_id, %(actor_id)s::uuid)
                    ELSE NULL END
            FROM before
            WHERE tasks.id = before.id
            RETURNING tasks.id, tasks.status AS status, before.status AS old_status
            """,
            {"status": status, "actor_id": actor_id, "task_id": task_id},
        )
        return await cur.fetchone()


async def get_status(conn: psycopg.AsyncConnection, task_id: str) -> str | None:
    """Returns a task's current status, or ``None`` if it does not exist."""
    async with conn.cursor() as cur:
        await cur.execute("SELECT status FROM tasks WHERE id = %s", (task_id,))
        row = await cur.fetchone()
        return row["status"] if row else None


async def set_assignee(
    conn: psycopg.AsyncConnection, task_id: str, assignee_id: str | None
) -> bool:
    """Sets or clears the assignee. Returns whether the task existed."""
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE tasks SET assignee_id = %s WHERE id = %s RETURNING id",
            (assignee_id, task_id),
        )
        return await cur.fetchone() is not None


async def move(
    conn: psycopg.AsyncConnection, task_id: str, *, list_id: str | None, position: int
) -> bool:
    """Moves a task to a zero-based index, optionally into another list.

    ``position`` is an *index* in the list as the user sees it, not a raw column
    value, so the target list's positions are renumbered densely from 0 with the
    moved task landing at that index. Renumbering rather than nudging neighbours is
    what makes the operation correct no matter what the stored values look like —
    :func:`create` inserts at ``min(position) - 1``, so they are routinely negative
    and never a tidy sequence. An index past the end clamps to the end.
    """
    async with conn.cursor() as cur:
        await cur.execute("SELECT list_id FROM tasks WHERE id = %s", (task_id,))
        current = await cur.fetchone()
        if current is None:
            return False

        source_list_id = str(current["list_id"])
        target_list_id = list_id or source_list_id

        await cur.execute(
            """
            WITH others AS (
                SELECT id, row_number() OVER (ORDER BY position, created_at, id) - 1 AS idx
                FROM tasks
                WHERE list_id = %(target)s::uuid AND id <> %(task_id)s::uuid
            ),
            target_index AS (
                SELECT LEAST(%(position)s::integer, (SELECT count(*) FROM others))::integer AS idx
            ),
            renumbered AS (
                SELECT id,
                       CASE WHEN others.idx < (SELECT idx FROM target_index)
                            THEN others.idx ELSE others.idx + 1 END AS position
                FROM others
                UNION ALL
                SELECT %(task_id)s::uuid, (SELECT idx FROM target_index)
            )
            UPDATE tasks t
            SET position = r.position, list_id = %(target)s::uuid
            FROM renumbered r
            WHERE t.id = r.id
            """,
            {"target": target_list_id, "task_id": task_id, "position": position},
        )
        moved = cur.rowcount > 0

        if moved and target_list_id != source_list_id:
            # Labels belong to a list, so they cannot follow the task across.
            await cur.execute("DELETE FROM task_labels WHERE task_id = %s", (task_id,))
        return moved


async def delete(conn: psycopg.AsyncConnection, task_id: str) -> bool:
    """Hard-deletes a task. Subtasks, comments and label links cascade with it."""
    async with conn.cursor() as cur:
        await cur.execute("DELETE FROM tasks WHERE id = %s RETURNING id", (task_id,))
        return await cur.fetchone() is not None


async def readable_task_ids(
    conn: psycopg.AsyncConnection, task_ids: list[str], *, viewer_id: str, viewer_is_admin: bool
) -> list[str]:
    """Filters ``task_ids`` down to the ones the caller may write.

    Used by the bulk endpoint: a request naming fifty tasks is authorized with one
    query, and any id the caller cannot write is simply not part of the update.
    """
    if not task_ids:
        return []
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT t.id
            FROM tasks t
            JOIN lists l ON l.id = t.list_id
            WHERE t.id = ANY(%(task_ids)s::uuid[])
              AND (
                EXISTS (SELECT 1 FROM list_members m
                         WHERE m.list_id = l.id AND m.user_id = %(viewer_id)s
                           AND m.role IN ('owner', 'editor'))
                OR %(viewer_is_admin)s
              )
            """,
            {"task_ids": task_ids, "viewer_id": viewer_id, "viewer_is_admin": viewer_is_admin},
        )
        return [str(row["id"]) for row in await cur.fetchall()]


async def bulk_set_status(
    conn: psycopg.AsyncConnection, task_ids: list[str], *, status: str, actor_id: str
) -> int:
    """Applies one status to many tasks. Returns how many rows changed."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE tasks SET
                status = %(status)s::task_status,
                completed_at = CASE
                    WHEN %(status)s::task_status IN ('done', 'cancelled')
                        THEN COALESCE(completed_at, now()) ELSE NULL END,
                completed_by_id = CASE
                    WHEN %(status)s::task_status IN ('done', 'cancelled')
                        THEN COALESCE(completed_by_id, %(actor_id)s::uuid) ELSE NULL END
            WHERE id = ANY(%(task_ids)s::uuid[])
            """,
            {"status": status, "actor_id": actor_id, "task_ids": task_ids},
        )
        return cur.rowcount


async def bulk_set_priority(
    conn: psycopg.AsyncConnection, task_ids: list[str], priority: str
) -> int:
    """Applies one priority to many tasks. Returns how many rows changed."""
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE tasks SET priority = %s::task_priority WHERE id = ANY(%s::uuid[])",
            (priority, task_ids),
        )
        return cur.rowcount


async def bulk_set_assignee(
    conn: psycopg.AsyncConnection, task_ids: list[str], assignee_id: str | None
) -> int:
    """Sets or clears the assignee on many tasks. Returns how many rows changed."""
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE tasks SET assignee_id = %s WHERE id = ANY(%s::uuid[])",
            (assignee_id, task_ids),
        )
        return cur.rowcount


async def bulk_move_to_list(
    conn: psycopg.AsyncConnection, task_ids: list[str], list_id: str
) -> int:
    """Moves many tasks into one list, dropping their now-foreign labels."""
    async with conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM task_labels WHERE task_id = ANY(%s::uuid[])",
            (task_ids,),
        )
        await cur.execute(
            """
            UPDATE tasks SET list_id = %s, position = 0
            WHERE id = ANY(%s::uuid[]) AND list_id <> %s
            """,
            (list_id, task_ids, list_id),
        )
        return cur.rowcount


async def clear_assignee_for_user(
    conn: psycopg.AsyncConnection, *, list_id: str, user_id: str
) -> int:
    """Unassigns a user from every open task on a list.

    Called when someone loses access to a list: leaving them as assignee on work
    they can no longer see would be misleading. Finished tasks keep their assignee
    so the record of who did what stays intact.
    """
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE tasks SET assignee_id = NULL
            WHERE list_id = %s AND assignee_id = %s AND status NOT IN ('done', 'cancelled')
            """,
            (list_id, user_id),
        )
        return cur.rowcount


async def search(
    conn: psycopg.AsyncConnection,
    *,
    page: Page,
    viewer_id: str,
    viewer_is_admin: bool,
    list_ids: list[str],
    query: str,
    statuses: list[str],
    priorities: list[str],
    label_ids: list[str],
    assignee_ids: list[str],
    unassigned_only: bool,
    due_after: datetime | None,
    due_before: datetime | None,
    overdue_only: bool,
    sort_field: str,
    descending: bool,
) -> tuple[list[dict[str, Any]], int, dict[str, int]]:
    """Lists tasks the caller can read, filtered, sorted and counted.

    Returns:
        The page of rows (with one sentinel row still attached), the total count,
        and per-status counts over the whole filtered set for the filter chips.
    """
    conditions: list[sql.Composable] = [sql.SQL(_READABLE)]
    params: dict[str, Any] = {"viewer_id": viewer_id, "viewer_is_admin": viewer_is_admin}

    if list_ids:
        conditions.append(sql.SQL("t.list_id = ANY(%(list_ids)s::uuid[])"))
        params["list_ids"] = list_ids
    if query.strip():
        conditions.append(sql.SQL("(t.title ILIKE %(query)s OR t.description ILIKE %(query)s)"))
        params["query"] = f"%{query.strip()}%"
    if statuses:
        conditions.append(sql.SQL("t.status = ANY(%(statuses)s::task_status[])"))
        params["statuses"] = statuses
    if priorities:
        conditions.append(sql.SQL("t.priority = ANY(%(priorities)s::task_priority[])"))
        params["priorities"] = priorities
    if label_ids:
        # A task matches if it carries *any* of the requested labels.
        conditions.append(
            sql.SQL(
                "EXISTS (SELECT 1 FROM task_labels tl WHERE tl.task_id = t.id "
                "AND tl.label_id = ANY(%(label_ids)s::uuid[]))"
            )
        )
        params["label_ids"] = label_ids
    if unassigned_only:
        conditions.append(sql.SQL("t.assignee_id IS NULL"))
    elif assignee_ids:
        conditions.append(sql.SQL("t.assignee_id = ANY(%(assignee_ids)s::uuid[])"))
        params["assignee_ids"] = assignee_ids
    if due_after is not None:
        conditions.append(sql.SQL("t.due_at >= %(due_after)s"))
        params["due_after"] = due_after
    if due_before is not None:
        conditions.append(sql.SQL("t.due_at <= %(due_before)s"))
        params["due_before"] = due_before
    if overdue_only:
        conditions.append(
            sql.SQL(
                "t.due_at < now() AND t.due_at IS NOT NULL "
                "AND t.status NOT IN ('done', 'cancelled')"
            )
        )

    where = sql.SQL(" AND ").join(conditions)
    order = sql.SQL(_SORT_EXPRESSIONS.get(sort_field, _SORT_EXPRESSIONS["position"]))
    direction = sql.SQL("DESC" if descending else "ASC")

    async with conn.cursor() as cur:
        # One grouped query gives the total and the per-status breakdown together.
        await cur.execute(
            sql.SQL(
                "SELECT t.status, count(*) AS count FROM tasks t "
                "JOIN lists l ON l.id = t.list_id WHERE {where} GROUP BY t.status"
            ).format(where=where),
            params,
        )
        status_counts = {row["status"]: int(row["count"]) for row in await cur.fetchall()}
        total = sum(status_counts.values())

        await cur.execute(
            sql.SQL(
                """
                SELECT {cols} {joins}
                WHERE {where}
                ORDER BY {order} {direction} NULLS LAST, t.created_at DESC, t.id
                LIMIT %(limit)s OFFSET %(offset)s
                """
            ).format(
                cols=sql.SQL(_TASK_COLUMNS),
                joins=sql.SQL(_JOINS),
                where=where,
                order=order,
                direction=direction,
            ),
            {**params, "limit": page.sql_limit, "offset": page.offset},
        )
        return list(await cur.fetchall()), total, status_counts


# --- Labels on tasks --------------------------------------------------------


async def labels_for_tasks(
    conn: psycopg.AsyncConnection, task_ids: list[str]
) -> dict[str, list[dict[str, Any]]]:
    """Loads labels for many tasks at once, grouped by task id."""
    if not task_ids:
        return {}
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT tl.task_id, lb.id, lb.name, lb.color
            FROM task_labels tl
            JOIN labels lb ON lb.id = tl.label_id
            WHERE tl.task_id = ANY(%s::uuid[])
            ORDER BY tl.task_id, lower(lb.name)
            """,
            (task_ids,),
        )
        grouped: dict[str, list[dict[str, Any]]] = {str(task_id): [] for task_id in task_ids}
        for row in await cur.fetchall():
            grouped.setdefault(str(row["task_id"]), []).append(row)
        return grouped


async def label_ids_on_list(
    conn: psycopg.AsyncConnection, *, list_id: str, label_ids: list[str]
) -> set[str]:
    """Returns the subset of ``label_ids`` that actually belong to ``list_id``.

    Labels are list-scoped, so attaching one from another list has to be rejected
    rather than silently stored.
    """
    if not label_ids:
        return set()
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT id FROM labels WHERE list_id = %s AND id = ANY(%s::uuid[])",
            (list_id, label_ids),
        )
        return {str(row["id"]) for row in await cur.fetchall()}


async def set_labels(conn: psycopg.AsyncConnection, task_id: str, label_ids: list[str]) -> None:
    """Replaces a task's labels with exactly ``label_ids``."""
    async with conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM task_labels WHERE task_id = %s AND NOT (label_id = ANY(%s::uuid[]))",
            (task_id, label_ids),
        )
        if label_ids:
            await cur.execute(
                """
                INSERT INTO task_labels (task_id, label_id)
                SELECT %s, unnest(%s::uuid[])
                ON CONFLICT DO NOTHING
                """,
                (task_id, label_ids),
            )


# --- Subtasks ---------------------------------------------------------------


async def subtasks_for_tasks(
    conn: psycopg.AsyncConnection, task_ids: list[str]
) -> dict[str, list[dict[str, Any]]]:
    """Loads subtasks for many tasks at once, grouped by task id."""
    if not task_ids:
        return {}
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id, task_id, title, completed_at, position, created_at, updated_at
            FROM subtasks
            WHERE task_id = ANY(%s::uuid[])
            ORDER BY task_id, position, created_at
            """,
            (task_ids,),
        )
        grouped: dict[str, list[dict[str, Any]]] = {str(task_id): [] for task_id in task_ids}
        for row in await cur.fetchall():
            grouped.setdefault(str(row["task_id"]), []).append(row)
        return grouped


async def get_subtask(conn: psycopg.AsyncConnection, subtask_id: str) -> dict[str, Any] | None:
    """Returns one subtask, or ``None``."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id, task_id, title, completed_at, position, created_at, updated_at
            FROM subtasks WHERE id = %s
            """,
            (subtask_id,),
        )
        return await cur.fetchone()


async def create_subtask(conn: psycopg.AsyncConnection, *, task_id: str, title: str) -> str:
    """Appends a subtask to a task's checklist and returns its id."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO subtasks (task_id, title, position)
            VALUES (
                %s, %s,
                COALESCE((SELECT max(position) + 1 FROM subtasks WHERE task_id = %s), 0)
            )
            RETURNING id
            """,
            (task_id, title, task_id),
        )
        row = await cur.fetchone()
    assert row is not None
    # psycopg returns uuid.UUID; ids are used as dict keys, so normalise to str.
    return str(row["id"])


async def create_subtasks(
    conn: psycopg.AsyncConnection, *, task_id: str, titles: list[str]
) -> None:
    """Appends several subtasks in the given order."""
    if not titles:
        return
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO subtasks (task_id, title, position)
            SELECT %s, title, ordinality - 1
            FROM unnest(%s::text[]) WITH ORDINALITY AS t(title, ordinality)
            """,
            (task_id, titles),
        )


async def update_subtask(
    conn: psycopg.AsyncConnection,
    subtask_id: str,
    *,
    title: str | None,
    completed: bool | None,
    position: int | None,
) -> bool:
    """Applies a partial subtask update. Returns whether the row existed."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE subtasks SET
                title = COALESCE(%(title)s, title),
                position = COALESCE(%(position)s, position),
                completed_at = CASE
                    WHEN %(completed)s IS NULL THEN completed_at
                    WHEN %(completed)s THEN COALESCE(completed_at, now())
                    ELSE NULL END
            WHERE id = %(id)s
            RETURNING id
            """,
            {"title": title, "position": position, "completed": completed, "id": subtask_id},
        )
        return await cur.fetchone() is not None


async def delete_subtask(conn: psycopg.AsyncConnection, subtask_id: str) -> bool:
    """Deletes a subtask. Returns whether a row was removed."""
    async with conn.cursor() as cur:
        await cur.execute("DELETE FROM subtasks WHERE id = %s RETURNING id", (subtask_id,))
        return await cur.fetchone() is not None


# --- Comments ---------------------------------------------------------------

_COMMENT_COLUMNS: Final = """
    c.id, c.task_id, c.body, c.edited, c.created_at, c.updated_at,
    a.id AS author_id, a.display_name AS author_display_name,
    a.email AS author_email, a.avatar_url AS author_avatar_url
"""


async def get_comment(conn: psycopg.AsyncConnection, comment_id: str) -> dict[str, Any] | None:
    """Returns one comment with its author, or ``None``."""
    async with conn.cursor() as cur:
        await cur.execute(
            sql.SQL(
                "SELECT {cols} FROM comments c LEFT JOIN users a ON a.id = c.author_id "
                "WHERE c.id = %s"
            ).format(cols=sql.SQL(_COMMENT_COLUMNS)),
            (comment_id,),
        )
        return await cur.fetchone()


async def list_comments(
    conn: psycopg.AsyncConnection, task_id: str, *, page: Page
) -> tuple[list[dict[str, Any]], int]:
    """Lists a task's comments, newest first."""
    async with conn.cursor() as cur:
        await cur.execute("SELECT count(*) AS total FROM comments WHERE task_id = %s", (task_id,))
        total_row = await cur.fetchone()
        total = int(total_row["total"]) if total_row else 0

        await cur.execute(
            sql.SQL(
                """
                SELECT {cols}
                FROM comments c
                LEFT JOIN users a ON a.id = c.author_id
                WHERE c.task_id = %s
                ORDER BY c.created_at DESC, c.id
                LIMIT %s OFFSET %s
                """
            ).format(cols=sql.SQL(_COMMENT_COLUMNS)),
            (task_id, page.sql_limit, page.offset),
        )
        return list(await cur.fetchall()), total


async def create_comment(
    conn: psycopg.AsyncConnection, *, task_id: str, author_id: str, body: str
) -> str:
    """Adds a comment and returns its id."""
    async with conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO comments (task_id, author_id, body) VALUES (%s, %s, %s) RETURNING id",
            (task_id, author_id, body),
        )
        row = await cur.fetchone()
    assert row is not None
    # psycopg returns uuid.UUID; ids are used as dict keys, so normalise to str.
    return str(row["id"])


async def update_comment(conn: psycopg.AsyncConnection, comment_id: str, body: str) -> bool:
    """Rewrites a comment body and flags it edited. Returns whether it existed."""
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE comments SET body = %s, edited = true WHERE id = %s RETURNING id",
            (body, comment_id),
        )
        return await cur.fetchone() is not None


async def delete_comment(conn: psycopg.AsyncConnection, comment_id: str) -> bool:
    """Deletes a comment. Returns whether a row was removed."""
    async with conn.cursor() as cur:
        await cur.execute("DELETE FROM comments WHERE id = %s RETURNING id", (comment_id,))
        return await cur.fetchone() is not None
