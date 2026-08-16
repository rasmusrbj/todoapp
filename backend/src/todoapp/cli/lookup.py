"""Candidate sets for short-id resolution.

Listings print truncated ids, so every command accepts one back. Expanding a prefix
needs the set of things it could refer to, and that set has to come from the API —
the CLI has no local database to consult. These helpers gather it, each in one call
per resource type rather than one per row.

The cost is real: resolving a task prefix fetches up to 100 tasks. Passing a full id
skips the lookup entirely, which is what scripts should do.
"""

from __future__ import annotations

from todo.v1 import common_pb2, list_pb2, task_pb2, user_pb2
from todoapp.cli import args as enum_args
from todoapp.cli.client import Api

# One page is plenty for prefix matching by a human; anyone with more than this
# should paste a full id.
_LOOKUP_LIMIT = 100

# Resolved at import, not per call. This exact constant was once read off the wrong
# generated module and raised AttributeError deep inside a command; binding it here means
# a rename breaks `import todoapp.cli.lookup`, which the test suite does.
_ADMIN_ROLE = enum_args.USER_ROLE.to_number("admin")


def lists(api: Api) -> dict[str, str]:
    """Every reachable list, id to name. Archived ones included."""
    response = api.lists.list_lists(
        list_pb2.ListListsRequest(
            page=common_pb2.PageRequest(limit=_LOOKUP_LIMIT), include_archived=True
        ),
        headers=api.require_token(),
    )
    return {item.id: item.name for item in response.lists}


def tasks(api: Api) -> dict[str, str]:
    """Every reachable task, id to title."""
    response = api.tasks.list_tasks(
        task_pb2.ListTasksRequest(page=common_pb2.PageRequest(limit=_LOOKUP_LIMIT)),
        headers=api.require_token(),
    )
    return {task.id: task.title for task in response.tasks}


def labels(api: Api) -> dict[str, str]:
    """Every label on every reachable list, id to name."""
    candidates: dict[str, str] = {}
    for list_id in lists(api):
        response = api.lists.list_labels(
            list_pb2.ListLabelsRequest(list_id=list_id), headers=api.require_token()
        )
        candidates.update({label.id: label.name for label in response.labels})
    return candidates


def members(api: Api) -> dict[str, str]:
    """Everyone the caller shares a list with, user id to name.

    This is the directory a non-admin is entitled to see. It deliberately does not
    fall back to a full user listing.
    """
    candidates: dict[str, str] = {}
    for list_id in lists(api):
        response = api.lists.list_members(
            list_pb2.ListMembersRequest(list_id=list_id), headers=api.require_token()
        )
        candidates.update({m.user.id: m.user.display_name for m in response.members})
    return candidates


def subtasks(api: Api, task_id: str) -> dict[str, str]:
    """One task's checklist items, id to title."""
    response = api.tasks.get_task(task_pb2.GetTaskRequest(id=task_id), headers=api.require_token())
    return {subtask.id: subtask.title for subtask in response.task.subtasks}


def comments(api: Api) -> dict[str, str]:
    """Every comment on every reachable task, id to a truncated body."""
    from todoapp.cli import output

    candidates: dict[str, str] = {}
    for task_id in tasks(api):
        response = api.tasks.list_comments(
            task_pb2.ListCommentsRequest(
                task_id=task_id, page=common_pb2.PageRequest(limit=_LOOKUP_LIMIT)
            ),
            headers=api.require_token(),
        )
        candidates.update(
            {comment.id: output.truncate(comment.body, 40) for comment in response.comments}
        )
    return candidates


def sessions(api: Api) -> dict[str, str]:
    """The caller's live sessions, id to a device description."""
    from todo.v1 import auth_pb2

    response = api.auth.list_sessions(auth_pb2.ListSessionsRequest(), headers=api.require_token())
    return {
        session.id: f"{session.user_agent or 'unknown device'} ({session.ip_address})"
        for session in response.sessions
    }


def users(api: Api) -> dict[str, str]:
    """The people the caller may address, id to "name <email>".

    Admins get the full listing; everyone else gets the people they share a list
    with, plus themselves.
    """
    me = api.users.get_current_user(
        user_pb2.GetCurrentUserRequest(), headers=api.require_token()
    ).user

    if me.role == _ADMIN_ROLE:
        listing = api.users.list_users(
            user_pb2.ListUsersRequest(page=common_pb2.PageRequest(limit=_LOOKUP_LIMIT)),
            headers=api.require_token(),
        )
        return {user.id: f"{user.display_name} <{user.email}>" for user in listing.users}

    candidates: dict[str, str] = {me.id: f"{me.display_name} <{me.email}>"}
    for list_id in lists(api):
        response = api.lists.list_members(
            list_pb2.ListMembersRequest(list_id=list_id), headers=api.require_token()
        )
        candidates.update(
            {m.user.id: f"{m.user.display_name} <{m.user.email}>" for m in response.members}
        )
    return candidates
