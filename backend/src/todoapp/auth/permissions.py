"""List-level authorization.

Four capabilities, checked against the caller's ``member_role`` on one list:

==========  =================================================================
capability  granted to
==========  =================================================================
read        owner, editor, commenter, viewer — plus anyone, if the list is public
comment     owner, editor, commenter
write       owner, editor
administer  owner
==========  =================================================================

A platform admin passes every check. Each function raises rather than returning a
boolean, so a handler cannot forget to look at the result.
"""

from __future__ import annotations

import psycopg

from todoapp.auth.context import Principal
from todoapp.domain import enums
from todoapp.errors import Reason, not_found, permission_denied
from todoapp.repositories import lists as lists_repo


async def _role_on(conn: psycopg.AsyncConnection, list_id: str, principal: Principal) -> str | None:
    return await lists_repo.viewer_role(conn, list_id, principal.user_id)


async def require_read(
    conn: psycopg.AsyncConnection, list_id: str, principal: Principal
) -> str | None:
    """Requires that the caller may read the list.

    Returns:
        The caller's role, or ``None`` when access comes from the list being public
        or from the admin role rather than from a membership.

    Raises:
        ConnectError: ``NOT_FOUND`` when the list does not exist *or* is invisible.
            Both are reported the same way on purpose — a distinct
            ``PERMISSION_DENIED`` would confirm that a given id exists.
    """
    role = await _role_on(conn, list_id, principal)
    if role is not None and role in enums.READ_ROLES:
        return role
    if await lists_repo.exists_readable(
        conn, list_id, viewer_id=principal.user_id, viewer_is_admin=principal.is_admin
    ):
        return role
    raise not_found(Reason.ERROR_REASON_LIST_NOT_FOUND, f"list {list_id} not found")


async def require_comment(conn: psycopg.AsyncConnection, list_id: str, principal: Principal) -> str:
    """Requires that the caller may comment on the list.

    Returns:
        The caller's effective role.

    Raises:
        ConnectError: ``NOT_FOUND`` if the list is invisible, ``PERMISSION_DENIED``
            if the caller can read it but only as a viewer.
    """
    role = await require_read(conn, list_id, principal)
    if principal.is_admin:
        return role or "owner"
    if role is None or role not in enums.COMMENT_ROLES:
        raise permission_denied(
            Reason.ERROR_REASON_PERMISSION_DENIED, "commenting on this list is not allowed"
        )
    return role


async def require_write(conn: psycopg.AsyncConnection, list_id: str, principal: Principal) -> str:
    """Requires that the caller may change the list's content.

    Returns:
        The caller's effective role.

    Raises:
        ConnectError: ``NOT_FOUND`` if the list is invisible, ``PERMISSION_DENIED``
            if the caller may only read or comment.
    """
    role = await require_read(conn, list_id, principal)
    if principal.is_admin:
        return role or "owner"
    if role is None or role not in enums.WRITE_ROLES:
        raise permission_denied(
            Reason.ERROR_REASON_PERMISSION_DENIED, "editing this list is not allowed"
        )
    return role


async def require_owner(conn: psycopg.AsyncConnection, list_id: str, principal: Principal) -> str:
    """Requires that the caller owns the list.

    Owner-only covers the things that change who can reach the list at all, or
    destroy it: sharing, role changes, visibility, deletion.

    Returns:
        The caller's effective role.

    Raises:
        ConnectError: ``NOT_FOUND`` if the list is invisible, ``PERMISSION_DENIED``
            if the caller is a member but not the owner.
    """
    role = await require_read(conn, list_id, principal)
    if principal.is_admin:
        return role or "owner"
    if role != "owner":
        raise permission_denied(
            Reason.ERROR_REASON_OWNER_REQUIRED, "only the list owner can do this"
        )
    return role
