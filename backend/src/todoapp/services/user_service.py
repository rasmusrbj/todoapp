"""``todo.v1.UserService`` — profiles, preferences, and admin account management.

Two audiences share one service. Self-service RPCs let a caller read and change
their own profile; the admin RPCs (``ListUsers``, ``CreateUser``,
``UpdateUserStatus``) require the platform admin role. ``UpdateUser`` serves both,
which is why the ``role`` field is checked separately from the rest.
"""

from __future__ import annotations

import logging

import psycopg
from connectrpc.request import RequestContext

from todo.v1 import user_pb2
from todoapp.auth import passwords
from todoapp.auth.context import Principal, require_admin, require_principal
from todoapp.config import Settings
from todoapp.db.pool import Database
from todoapp.domain import enums, validation
from todoapp.errors import (
    Reason,
    already_exists,
    failed_precondition,
    invalid_argument,
    not_found,
    permission_denied,
)
from todoapp.repositories import pagination
from todoapp.repositories import sessions as sessions_repo
from todoapp.repositories import users as users_repo
from todoapp.services import mappers

logger = logging.getLogger("todoapp.services.user")

# Cap on the share-dialog type-ahead.
_MAX_SEARCH_RESULTS = 20


class UserService:
    """Implements the generated ``todo.v1.UserService`` protocol."""

    def __init__(self, *, database: Database, settings: Settings) -> None:
        """Wires the service to its collaborators."""
        self._db = database
        self._settings = settings

    async def get_current_user(
        self, request: user_pb2.GetCurrentUserRequest, ctx: RequestContext
    ) -> user_pb2.GetCurrentUserResponse:
        """Returns the caller's own account with fresh stats."""
        del request
        principal = require_principal(ctx)
        async with self._db.connection() as conn:
            row = await users_repo.get_by_id(conn, principal.user_id)
        if row is None:
            # The session outlived the account it belonged to.
            raise not_found(Reason.ERROR_REASON_USER_NOT_FOUND, "account no longer exists")
        return user_pb2.GetCurrentUserResponse(user=mappers.user(row))

    async def get_user(
        self, request: user_pb2.GetUserRequest, ctx: RequestContext
    ) -> user_pb2.GetUserResponse:
        """Returns one account. Anyone may read themselves; others need admin."""
        principal = require_principal(ctx)
        user_id = validation.uuid_value(request.id, field="id")
        if user_id != principal.user_id and not principal.is_admin:
            raise permission_denied(
                Reason.ERROR_REASON_ADMIN_REQUIRED, "reading another account requires admin"
            )
        async with self._db.connection() as conn:
            row = await users_repo.get_by_id(conn, user_id)
        if row is None:
            raise not_found(Reason.ERROR_REASON_USER_NOT_FOUND, f"user {user_id} not found")
        return user_pb2.GetUserResponse(user=mappers.user(row))

    async def list_users(
        self, request: user_pb2.ListUsersRequest, ctx: RequestContext
    ) -> user_pb2.ListUsersResponse:
        """Lists accounts for the admin screen."""
        require_admin(ctx)
        page = pagination.resolve_page(request.page)
        roles = enums.USER_ROLE.many_to_db(request.roles, field="roles")
        statuses = enums.USER_STATUS.many_to_db(request.statuses, field="statuses")

        async with self._db.connection() as conn:
            rows, total = await users_repo.search(
                conn,
                page=page,
                query=request.query,
                roles=roles,
                statuses=statuses,
                sort_field=_user_sort_field(request.sort_field),
                descending=_is_descending(request.sort_direction),
            )
        trimmed, has_more = pagination.trim(rows, page)
        return user_pb2.ListUsersResponse(
            users=[mappers.user(row) for row in trimmed],
            page=pagination.page_response(page, total_count=total, has_more=has_more),
        )

    async def create_user(
        self, request: user_pb2.CreateUserRequest, ctx: RequestContext
    ) -> user_pb2.CreateUserResponse:
        """Creates an account directly, bypassing self-signup. Admin only.

        The account is created ``active`` with a verified address: an admin adding a
        colleague has already established who they are, and making them chase a
        confirmation email adds nothing.
        """
        require_admin(ctx)
        email = validation.email(request.email)
        display_name = validation.required_text(
            request.display_name, field="display_name", max_length=validation.MAX_DISPLAY_NAME
        )
        passwords.validate_strength(request.password, settings=self._settings)
        time_zone = validation.time_zone(request.time_zone)
        role = enums.USER_ROLE.to_db_or(
            request.role, enums.USER_ROLE.from_db("member"), field="role"
        )
        locale = enums.LOCALE.to_db_or(request.locale, enums.LOCALE.from_db("da"), field="locale")
        password_hash = passwords.hash_password(request.password)

        try:
            async with self._db.transaction() as conn:
                row = await users_repo.create(
                    conn,
                    email=email,
                    password_hash=password_hash,
                    display_name=display_name,
                    role=role,
                    status="active",
                    locale=locale,
                    time_zone=time_zone,
                )
                await users_repo.mark_email_verified(conn, str(row["id"]))
                refreshed = await users_repo.get_by_id(conn, str(row["id"]))
        except psycopg.errors.UniqueViolation as err:
            raise already_exists(
                Reason.ERROR_REASON_EMAIL_ALREADY_REGISTERED,
                "email address is already registered",
                field="email",
            ) from err
        assert refreshed is not None
        return user_pb2.CreateUserResponse(user=mappers.user(refreshed))

    async def update_user(
        self, request: user_pb2.UpdateUserRequest, ctx: RequestContext
    ) -> user_pb2.UpdateUserResponse:
        """Applies a partial profile update. Self, or an admin on anyone.

        Only fields actually present in the request are written, which is what makes
        it safe for the settings screen to send one field at a time.
        """
        principal = require_principal(ctx)
        user_id = validation.uuid_value(request.id, field="id")
        if user_id != principal.user_id and not principal.is_admin:
            raise permission_denied(
                Reason.ERROR_REASON_ADMIN_REQUIRED, "changing another account requires admin"
            )

        changes = self._collect_profile_changes(request, principal)
        if not changes:
            raise invalid_argument(Reason.ERROR_REASON_NO_CHANGE_REQUESTED, "no fields to update")

        async with self._db.transaction() as conn:
            row = await users_repo.update(conn, user_id, changes)
        if row is None:
            raise not_found(Reason.ERROR_REASON_USER_NOT_FOUND, f"user {user_id} not found")
        return user_pb2.UpdateUserResponse(user=mappers.user(row))

    async def update_user_status(
        self, request: user_pb2.UpdateUserStatusRequest, ctx: RequestContext
    ) -> user_pb2.UpdateUserStatusResponse:
        """Suspends, reactivates, or deactivates an account. Admin only.

        Suspending or deactivating also closes every live session, because leaving
        one open would make the status change advisory rather than effective.
        """
        admin = require_admin(ctx)
        user_id = validation.uuid_value(request.id, field="id")
        status = enums.USER_STATUS.to_db(request.status, field="status")
        reason = validation.optional_text(
            request.reason, field="reason", max_length=validation.MAX_STATUS_REASON
        )

        if user_id == admin.user_id and status != "active":
            raise failed_precondition(
                Reason.ERROR_REASON_CANNOT_DEMOTE_SELF,
                "an admin cannot suspend or deactivate their own account",
                field="status",
            )

        async with self._db.transaction() as conn:
            row = await users_repo.set_status(conn, user_id, status=status, reason=reason)
            if row is None:
                raise not_found(Reason.ERROR_REASON_USER_NOT_FOUND, f"user {user_id} not found")
            if status not in enums.SIGNIN_ALLOWED_STATUSES:
                closed = await sessions_repo.revoke_all_for_user(conn, user_id)
                logger.info("closed %d session(s) for %s account %s", closed, status, user_id)
        return user_pb2.UpdateUserStatusResponse(user=mappers.user(row))

    async def delete_user(
        self, request: user_pb2.DeleteUserRequest, ctx: RequestContext
    ) -> user_pb2.DeleteUserResponse:
        """Deletes an account and everything it owns. Self, or admin on anyone.

        Owned lists and their tasks go with the account. Content the user
        contributed to *other* people's lists stays, with the author reference
        nulled — deleting an account should not silently gut a shared list.
        """
        principal = require_principal(ctx)
        user_id = validation.uuid_value(request.id, field="id")
        if user_id != principal.user_id and not principal.is_admin:
            raise permission_denied(
                Reason.ERROR_REASON_ADMIN_REQUIRED, "deleting another account requires admin"
            )
        if user_id == principal.user_id and principal.is_admin:
            # Removing the last admin would leave nobody able to administer anything.
            await self._reject_last_admin_deletion(user_id)

        async with self._db.transaction() as conn:
            deleted = await users_repo.delete(conn, user_id)
        if not deleted:
            raise not_found(Reason.ERROR_REASON_USER_NOT_FOUND, f"user {user_id} not found")
        logger.info("deleted account %s", user_id)
        return user_pb2.DeleteUserResponse()

    async def search_users(
        self, request: user_pb2.SearchUsersRequest, ctx: RequestContext
    ) -> user_pb2.SearchUsersResponse:
        """Type-ahead over active users, for the share dialog.

        Requires a verified address: an unverified account must not be able to
        harvest the user directory.
        """
        principal = require_principal(ctx)
        if not principal.email_verified:
            raise permission_denied(
                Reason.ERROR_REASON_EMAIL_NOT_VERIFIED,
                "verify your email address before searching for people",
            )
        limit = min(request.limit or _MAX_SEARCH_RESULTS, _MAX_SEARCH_RESULTS)
        async with self._db.connection() as conn:
            rows = await users_repo.type_ahead(
                conn, query=request.query, limit=limit, exclude_user_id=principal.user_id
            )
        return user_pb2.SearchUsersResponse(
            users=[ref for row in rows if (ref := mappers.user_ref(row)) is not None]
        )

    # --- Internals ----------------------------------------------------------

    def _collect_profile_changes(
        self, request: user_pb2.UpdateUserRequest, principal: Principal
    ) -> dict[str, object]:
        """Builds the column-to-value map for the fields present in ``request``.

        Raises:
            ConnectError: ``PERMISSION_DENIED`` if a non-admin tries to set ``role``.
        """
        changes: dict[str, object] = {}
        if request.HasField("display_name"):
            changes["display_name"] = validation.required_text(
                request.display_name,
                field="display_name",
                max_length=validation.MAX_DISPLAY_NAME,
            )
        if request.HasField("bio"):
            changes["bio"] = validation.optional_text(
                request.bio, field="bio", max_length=validation.MAX_BIO
            )
        if request.HasField("avatar_url"):
            changes["avatar_url"] = validation.url(request.avatar_url, field="avatar_url")
        if request.HasField("time_zone"):
            changes["time_zone"] = validation.time_zone(request.time_zone)
        if request.HasField("locale"):
            changes["locale"] = enums.LOCALE.to_db(request.locale, field="locale")
        if request.HasField("theme"):
            changes["theme"] = enums.THEME_PREFERENCE.to_db(request.theme, field="theme")
        if request.HasField("role"):
            if not principal.is_admin:
                raise permission_denied(
                    Reason.ERROR_REASON_ADMIN_REQUIRED, "changing a role requires admin"
                )
            changes["role"] = enums.USER_ROLE.to_db(request.role, field="role")
        return changes

    async def _reject_last_admin_deletion(self, user_id: str) -> None:
        """Refuses to delete the only remaining admin account."""
        async with self._db.connection() as conn:
            page = pagination.Page(limit=2, offset=0)
            _, total = await users_repo.search(
                conn,
                page=page,
                query="",
                roles=["admin"],
                statuses=[],
                sort_field="created_at",
                descending=False,
            )
        if total <= 1:
            raise failed_precondition(
                Reason.ERROR_REASON_CANNOT_DEMOTE_SELF,
                "cannot delete the last admin account",
            )
        del user_id  # Only the count matters.


def _is_descending(direction: int) -> bool:
    """Maps a :class:`SortDirection` to a boolean, defaulting to descending.

    Newest-first is the useful default for every listing in this API.
    """
    return direction != 1  # SORT_DIRECTION_ASC


def _user_sort_field(value: int) -> str:
    """Maps a :class:`UserSortField` to a repository sort key."""
    return {
        1: "created_at",
        2: "display_name",
        3: "email",
        4: "last_seen_at",
    }.get(value, "created_at")
