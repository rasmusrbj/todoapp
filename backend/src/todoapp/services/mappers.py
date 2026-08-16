"""Row-to-proto conversion.

The single place that knows how a database row becomes a wire message. Keeping it
here means a column rename shows up in one file, and every RPC returns the same
shape for the same entity.

Two conventions run through all of it:

* A ``NULL`` foreign key becomes an *absent* optional message, never a message full
  of empty strings — the client can then distinguish "no assignee" from "an
  assignee whose name we failed to load".
* Enum labels always travel through :mod:`todoapp.domain.enums`, so an unexpected
  label raises instead of quietly serialising as ``UNSPECIFIED``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from google.protobuf.timestamp_pb2 import Timestamp

from todo.v1 import auth_pb2, common_pb2, list_pb2, task_pb2, user_pb2
from todoapp.domain import enums


def to_timestamp(value: datetime | None) -> Timestamp | None:
    """Converts a ``timestamptz`` to a proto timestamp, preserving ``None``."""
    if value is None:
        return None
    stamp = Timestamp()
    stamp.FromDatetime(value)
    return stamp


def user_ref(
    row: dict[str, Any],
    *,
    prefix: str = "",
    id_key: str | None = None,
) -> common_pb2.UserRef | None:
    """Builds a :class:`UserRef` from ``<prefix>id``/``display_name``/… columns.

    Args:
        row: The database row.
        prefix: Column-name prefix, e.g. ``assignee_`` for ``assignee_display_name``.
        id_key: Column holding the *user* id, when it is not ``<prefix>id``. Needed
            wherever the row's own ``id`` belongs to something else — a membership
            row's ``id`` is the membership, and using it as the user id silently
            produces a reference that resolves to nothing.

    Returns:
        The reference, or ``None`` when the id column is ``NULL`` — which is how a
        deleted user surfaces after ``ON DELETE SET NULL``.
    """
    user_id = row.get(id_key or f"{prefix}id")
    if user_id is None:
        return None
    return common_pb2.UserRef(
        id=str(user_id),
        display_name=row.get(f"{prefix}display_name") or "",
        email=row.get(f"{prefix}email") or "",
        avatar_url=row.get(f"{prefix}avatar_url") or "",
    )


def list_ref(row: dict[str, Any], *, prefix: str = "list_") -> common_pb2.ListRef | None:
    """Builds a :class:`ListRef` from ``<prefix>id``/``name``/``color``/… columns."""
    list_id = row.get(f"{prefix}id")
    if list_id is None:
        return None
    return common_pb2.ListRef(
        id=str(list_id),
        name=row.get(f"{prefix}name") or "",
        color=enums.LIST_COLOR.from_db(row.get(f"{prefix}color")),
        visibility=enums.LIST_VISIBILITY.from_db(row.get(f"{prefix}visibility")),
    )


def label_ref(row: dict[str, Any]) -> common_pb2.LabelRef:
    """Builds a :class:`LabelRef` from an ``id``/``name``/``color`` row."""
    return common_pb2.LabelRef(
        id=str(row["id"]),
        name=row["name"],
        color=enums.LIST_COLOR.from_db(row["color"]),
    )


def user(row: dict[str, Any]) -> user_pb2.User:
    """Builds a full :class:`User` from a row selected by the users repository."""
    return user_pb2.User(
        id=str(row["id"]),
        email=str(row["email"]),
        display_name=row["display_name"],
        bio=row["bio"],
        avatar_url=row["avatar_url"],
        time_zone=row["time_zone"],
        role=enums.USER_ROLE.from_db(row["role"]),
        status=enums.USER_STATUS.from_db(row["status"]),
        locale=enums.LOCALE.from_db(row["locale"]),
        theme=enums.THEME_PREFERENCE.from_db(row["theme"]),
        email_verified=row["email_verified"],
        stats=user_pb2.UserStats(
            owned_list_count=int(row.get("owned_list_count") or 0),
            shared_list_count=int(row.get("shared_list_count") or 0),
            open_task_count=int(row.get("open_task_count") or 0),
            completed_task_count=int(row.get("completed_task_count") or 0),
            overdue_task_count=int(row.get("overdue_task_count") or 0),
        ),
        created_at=to_timestamp(row["created_at"]),
        updated_at=to_timestamp(row["updated_at"]),
        last_seen_at=to_timestamp(row.get("last_seen_at")),
    )


def session(row: dict[str, Any], *, current_session_id: str | None = None) -> auth_pb2.Session:
    """Builds a :class:`Session`, flagging the one making the current call."""
    return auth_pb2.Session(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        client=enums.SESSION_CLIENT.from_db(row["client"]),
        user_agent=row.get("user_agent") or "",
        ip_address=row.get("ip_address") or "",
        created_at=to_timestamp(row["created_at"]),
        expires_at=to_timestamp(row["expires_at"]),
        last_used_at=to_timestamp(row["last_used_at"]),
        is_current=str(row["id"]) == current_session_id,
    )


def list_member(row: dict[str, Any]) -> list_pb2.ListMember:
    """Builds a :class:`ListMember` from a membership row joined to its users."""
    return list_pb2.ListMember(
        id=str(row["id"]),
        list_id=str(row["list_id"]),
        # `row["id"]` is the membership; the user is in `user_id`.
        user=user_ref(row, prefix="", id_key="user_id"),
        role=enums.MEMBER_ROLE.from_db(row["role"]),
        invited_by=user_ref(row, prefix="invited_by_"),
        created_at=to_timestamp(row["created_at"]),
        updated_at=to_timestamp(row["updated_at"]),
    )


def label(row: dict[str, Any]) -> list_pb2.Label:
    """Builds a full :class:`Label` from a labels row with its usage count."""
    return list_pb2.Label(
        id=str(row["id"]),
        list_id=str(row["list_id"]),
        name=row["name"],
        color=enums.LIST_COLOR.from_db(row["color"]),
        task_count=int(row.get("task_count") or 0),
        created_at=to_timestamp(row["created_at"]),
        updated_at=to_timestamp(row["updated_at"]),
    )


def todo_list(
    row: dict[str, Any],
    *,
    members: list[dict[str, Any]] | None = None,
    labels: list[dict[str, Any]] | None = None,
) -> list_pb2.TodoList:
    """Builds a :class:`TodoList` from a row plus its pre-loaded children.

    ``members`` and ``labels`` are passed in rather than fetched, because the list
    endpoints load them for the whole page in one query each.
    """
    total = int(row.get("total_task_count") or 0)
    completed = int(row.get("completed_task_count") or 0)
    # An empty list counts as complete: there is nothing left to do in it.
    completion = 100 if total == 0 else round(completed * 100 / total)

    return list_pb2.TodoList(
        id=str(row["id"]),
        name=row["name"],
        description=row["description"],
        color=enums.LIST_COLOR.from_db(row["color"]),
        visibility=enums.LIST_VISIBILITY.from_db(row["visibility"]),
        position=int(row["position"]),
        archived=row.get("archived_at") is not None,
        owner=user_ref(row, prefix="owner_") or common_pb2.UserRef(id=str(row["owner_id"])),
        viewer_role=enums.MEMBER_ROLE.from_db(row.get("viewer_role")),
        members=[list_member(member) for member in members or []],
        labels=[label_ref(item) for item in labels or []],
        stats=list_pb2.ListStats(
            total_task_count=total,
            open_task_count=int(row.get("open_task_count") or 0),
            completed_task_count=completed,
            overdue_task_count=int(row.get("overdue_task_count") or 0),
            member_count=int(row.get("member_count") or 0),
            completion_percent=completion,
            next_due_at=to_timestamp(row.get("next_due_at")),
        ),
        created_at=to_timestamp(row["created_at"]),
        updated_at=to_timestamp(row["updated_at"]),
        archived_at=to_timestamp(row.get("archived_at")),
    )


def subtask(row: dict[str, Any]) -> task_pb2.Subtask:
    """Builds a :class:`Subtask`. ``completed`` is derived from the timestamp."""
    return task_pb2.Subtask(
        id=str(row["id"]),
        task_id=str(row["task_id"]),
        title=row["title"],
        completed=row.get("completed_at") is not None,
        position=int(row["position"]),
        created_at=to_timestamp(row["created_at"]),
        updated_at=to_timestamp(row["updated_at"]),
        completed_at=to_timestamp(row.get("completed_at")),
    )


def recurrence(row: dict[str, Any]) -> task_pb2.Recurrence:
    """Builds a :class:`Recurrence` from the three ``recurrence_*`` columns."""
    return task_pb2.Recurrence(
        frequency=enums.RECURRENCE_FREQUENCY.from_db(row["recurrence_frequency"]),
        interval=int(row["recurrence_interval"]),
        until=to_timestamp(row.get("recurrence_until")),
    )


def task(
    row: dict[str, Any],
    *,
    labels: list[dict[str, Any]] | None = None,
    subtasks: list[dict[str, Any]] | None = None,
) -> task_pb2.Task:
    """Builds a :class:`Task` from a row plus its pre-loaded children."""
    return task_pb2.Task(
        id=str(row["id"]),
        title=row["title"],
        description=row["description"],
        status=enums.TASK_STATUS.from_db(row["status"]),
        priority=enums.TASK_PRIORITY.from_db(row["priority"]),
        position=int(row["position"]),
        list=list_ref(row),
        created_by=user_ref(row, prefix="created_by_"),
        assignee=user_ref(row, prefix="assignee_"),
        labels=[label_ref(item) for item in labels or []],
        subtasks=[subtask(item) for item in subtasks or []],
        recurrence=recurrence(row),
        due_at=to_timestamp(row.get("due_at")),
        due_has_time=row["due_has_time"],
        starts_at=to_timestamp(row.get("starts_at")),
        completed_at=to_timestamp(row.get("completed_at")),
        completed_by=user_ref(row, prefix="completed_by_"),
        created_at=to_timestamp(row["created_at"]),
        updated_at=to_timestamp(row["updated_at"]),
        overdue=bool(row.get("overdue")),
        comment_count=int(row.get("comment_count") or 0),
        subtask_count=int(row.get("subtask_count") or 0),
        completed_subtask_count=int(row.get("completed_subtask_count") or 0),
        estimate_minutes=int(row["estimate_minutes"]),
    )


def comment(row: dict[str, Any]) -> task_pb2.Comment:
    """Builds a :class:`Comment` from a row joined to its author."""
    return task_pb2.Comment(
        id=str(row["id"]),
        task_id=str(row["task_id"]),
        author=user_ref(row, prefix="author_"),
        body=row["body"],
        edited=row["edited"],
        created_at=to_timestamp(row["created_at"]),
        updated_at=to_timestamp(row["updated_at"]),
    )


def activity(row: dict[str, Any]) -> task_pb2.Activity:
    """Builds an :class:`Activity` entry, including its structured diff."""
    change = None
    if row.get("field"):
        change = task_pb2.ActivityChange(
            field=row["field"],
            from_value=row.get("from_value") or "",
            to_value=row.get("to_value") or "",
        )
    return task_pb2.Activity(
        id=str(row["id"]),
        action=enums.ACTIVITY_ACTION.from_db(row["action"]),
        target_type=enums.ACTIVITY_TARGET_TYPE.from_db(row["target_type"]),
        target_id=str(row["target_id"]),
        target_label=row["target_label"],
        actor=user_ref(row, prefix="actor_"),
        list=list_ref(row),
        change=change,
        created_at=to_timestamp(row["created_at"]),
    )
