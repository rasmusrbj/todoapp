"""``todo.v1.ListService`` — lists, membership, and labels.

Every handler takes the same shape: validate the request, authorize against the
list, do the work and record the activity in one transaction, then read the result
back. The read-back is deliberate — the response always reflects committed state,
including the trigger-maintained ``updated_at`` and the recomputed stats.
"""

from __future__ import annotations

import logging

import psycopg
from connectrpc.request import RequestContext

from todo.v1 import list_pb2
from todoapp.auth import permissions
from todoapp.auth.context import Principal, require_principal, require_verified_email
from todoapp.db.pool import Database
from todoapp.domain import enums, validation
from todoapp.errors import (
    Reason,
    already_exists,
    failed_precondition,
    invalid_argument,
    not_found,
)
from todoapp.repositories import activity as activity_repo
from todoapp.repositories import lists as lists_repo
from todoapp.repositories import pagination
from todoapp.repositories import tasks as tasks_repo
from todoapp.repositories import users as users_repo
from todoapp.services import mappers

logger = logging.getLogger("todoapp.services.list")

# A single drag-and-drop reorder should never carry more ids than a board can show.
_MAX_REORDER_IDS = 500


class ListService:
    """Implements the generated ``todo.v1.ListService`` protocol."""

    def __init__(self, *, database: Database) -> None:
        """Wires the service to the connection pool."""
        self._db = database

    # --- Lists --------------------------------------------------------------

    async def get_list(
        self, request: list_pb2.GetListRequest, ctx: RequestContext
    ) -> list_pb2.GetListResponse:
        """Returns one list with its owner, members, labels, and stats."""
        principal = require_principal(ctx)
        list_id = validation.uuid_value(request.id, field="id")
        async with self._db.connection() as conn:
            row = await lists_repo.get(
                conn, list_id, viewer_id=principal.user_id, viewer_is_admin=principal.is_admin
            )
            if row is None:
                raise not_found(Reason.ERROR_REASON_LIST_NOT_FOUND, f"list {list_id} not found")
            members = await lists_repo.list_members(conn, list_id)
            labels = await lists_repo.list_labels(conn, list_id)
        return list_pb2.GetListResponse(list=mappers.todo_list(row, members=members, labels=labels))

    async def list_lists(
        self, request: list_pb2.ListListsRequest, ctx: RequestContext
    ) -> list_pb2.ListListsResponse:
        """Lists the boards the caller can see, filtered and sorted.

        Members and labels for the whole page are loaded with one query each rather
        than one per list, so rendering 25 cards costs three round-trips, not 51.
        """
        principal = require_principal(ctx)
        page = pagination.resolve_page(request.page)

        async with self._db.connection() as conn:
            rows, total = await lists_repo.search(
                conn,
                page=page,
                viewer_id=principal.user_id,
                viewer_is_admin=principal.is_admin,
                query=request.query,
                visibilities=enums.LIST_VISIBILITY.many_to_db(
                    request.visibilities, field="visibilities"
                ),
                roles=enums.MEMBER_ROLE.many_to_db(request.roles, field="roles"),
                include_archived=request.include_archived,
                sort_field=_list_sort_field(request.sort_field),
                descending=_is_descending(request.sort_direction, default_descending=False),
            )
            trimmed, has_more = pagination.trim(rows, page)
            list_ids = [str(row["id"]) for row in trimmed]
            members = await lists_repo.members_for_lists(conn, list_ids)
            labels = await lists_repo.labels_for_lists(conn, list_ids)

        return list_pb2.ListListsResponse(
            lists=[
                mappers.todo_list(
                    row,
                    members=members.get(str(row["id"]), []),
                    labels=labels.get(str(row["id"]), []),
                )
                for row in trimmed
            ],
            page=pagination.page_response(page, total_count=total, has_more=has_more),
        )

    async def create_list(
        self, request: list_pb2.CreateListRequest, ctx: RequestContext
    ) -> list_pb2.CreateListResponse:
        """Creates a list owned by the caller and places it at the top of the board."""
        principal = require_principal(ctx)
        name = validation.required_text(
            request.name, field="name", max_length=validation.MAX_LIST_NAME
        )
        description = validation.optional_text(
            request.description, field="description", max_length=validation.MAX_LIST_DESCRIPTION
        )
        color = enums.LIST_COLOR.to_db_or(
            request.color, enums.LIST_COLOR.from_db("zinc"), field="color"
        )
        visibility = enums.LIST_VISIBILITY.to_db_or(
            request.visibility, enums.LIST_VISIBILITY.from_db("private"), field="visibility"
        )

        async with self._db.transaction() as conn:
            list_id = await lists_repo.create(
                conn,
                owner_id=principal.user_id,
                name=name,
                description=description,
                color=color,
                visibility=visibility,
            )
            await activity_repo.record(
                conn,
                actor_id=principal.user_id,
                action="created",
                target_type="list",
                target_id=list_id,
                target_label=name,
                list_id=list_id,
            )
        return list_pb2.CreateListResponse(list=await self._load(list_id, principal))

    async def update_list(
        self, request: list_pb2.UpdateListRequest, ctx: RequestContext
    ) -> list_pb2.UpdateListResponse:
        """Applies a partial list update.

        Editors may rename and recolour; only the owner may change visibility, since
        that is what decides who can reach the list at all.
        """
        principal = require_principal(ctx)
        list_id = validation.uuid_value(request.id, field="id")

        changes: dict[str, object] = {}
        if request.HasField("name"):
            changes["name"] = validation.required_text(
                request.name, field="name", max_length=validation.MAX_LIST_NAME
            )
        if request.HasField("description"):
            changes["description"] = validation.optional_text(
                request.description,
                field="description",
                max_length=validation.MAX_LIST_DESCRIPTION,
            )
        if request.HasField("color"):
            changes["color"] = enums.LIST_COLOR.to_db(request.color, field="color")
        if request.HasField("visibility"):
            changes["visibility"] = enums.LIST_VISIBILITY.to_db(
                request.visibility, field="visibility"
            )
        if not changes:
            raise invalid_argument(Reason.ERROR_REASON_NO_CHANGE_REQUESTED, "no fields to update")

        async with self._db.transaction() as conn:
            if "visibility" in changes:
                await permissions.require_owner(conn, list_id, principal)
            else:
                await permissions.require_write(conn, list_id, principal)

            before = await lists_repo.get(
                conn, list_id, viewer_id=principal.user_id, viewer_is_admin=principal.is_admin
            )
            if before is None:
                raise not_found(Reason.ERROR_REASON_LIST_NOT_FOUND, f"list {list_id} not found")
            if not await lists_repo.update(conn, list_id, changes):
                raise not_found(Reason.ERROR_REASON_LIST_NOT_FOUND, f"list {list_id} not found")

            for field, value in changes.items():
                await activity_repo.record(
                    conn,
                    actor_id=principal.user_id,
                    action="updated",
                    target_type="list",
                    target_id=list_id,
                    target_label=str(changes.get("name", before["name"])),
                    list_id=list_id,
                    field=field,
                    from_value=str(before.get(field, "")),
                    to_value=str(value),
                )
        return list_pb2.UpdateListResponse(list=await self._load(list_id, principal))

    async def set_list_archived(
        self, request: list_pb2.SetListArchivedRequest, ctx: RequestContext
    ) -> list_pb2.SetListArchivedResponse:
        """Archives or restores a list without destroying anything."""
        principal = require_principal(ctx)
        list_id = validation.uuid_value(request.id, field="id")

        async with self._db.transaction() as conn:
            await permissions.require_owner(conn, list_id, principal)
            row = await lists_repo.get(
                conn, list_id, viewer_id=principal.user_id, viewer_is_admin=principal.is_admin
            )
            if row is None or not await lists_repo.set_archived(
                conn, list_id, archived=request.archived
            ):
                raise not_found(Reason.ERROR_REASON_LIST_NOT_FOUND, f"list {list_id} not found")
            await activity_repo.record(
                conn,
                actor_id=principal.user_id,
                action="archived" if request.archived else "restored",
                target_type="list",
                target_id=list_id,
                target_label=row["name"],
                list_id=list_id,
            )
        return list_pb2.SetListArchivedResponse(list=await self._load(list_id, principal))

    async def delete_list(
        self, request: list_pb2.DeleteListRequest, ctx: RequestContext
    ) -> list_pb2.DeleteListResponse:
        """Deletes a list and everything in it. Owner only.

        The activity entry is written *before* the delete so it survives the cascade,
        and it keeps the list's name so the feed still reads correctly afterwards.
        """
        principal = require_principal(ctx)
        list_id = validation.uuid_value(request.id, field="id")

        async with self._db.transaction() as conn:
            await permissions.require_owner(conn, list_id, principal)
            row = await lists_repo.get(
                conn, list_id, viewer_id=principal.user_id, viewer_is_admin=principal.is_admin
            )
            if row is None:
                raise not_found(Reason.ERROR_REASON_LIST_NOT_FOUND, f"list {list_id} not found")
            await activity_repo.record(
                conn,
                actor_id=principal.user_id,
                action="deleted",
                target_type="list",
                target_id=list_id,
                target_label=row["name"],
            )
            if not await lists_repo.delete(conn, list_id):
                raise not_found(Reason.ERROR_REASON_LIST_NOT_FOUND, f"list {list_id} not found")
        logger.info("deleted list %s", list_id)
        return list_pb2.DeleteListResponse()

    async def reorder_lists(
        self, request: list_pb2.ReorderListsRequest, ctx: RequestContext
    ) -> list_pb2.ReorderListsResponse:
        """Persists a drag-and-drop ordering of the caller's own lists."""
        principal = require_principal(ctx)
        list_ids = validation.uuid_values(
            request.list_ids, field="list_ids", max_count=_MAX_REORDER_IDS
        )
        if not list_ids:
            raise invalid_argument(
                Reason.ERROR_REASON_FIELD_REQUIRED, "list_ids is required", field="list_ids"
            )
        async with self._db.transaction() as conn:
            await lists_repo.reorder(conn, owner_id=principal.user_id, list_ids=list_ids)

        # Return the board in its new order rather than only the moved rows, so the
        # client can replace its state wholesale instead of reconciling.
        page = pagination.Page(limit=min(len(list_ids), pagination.MAX_LIMIT), offset=0)
        async with self._db.connection() as conn:
            rows, _ = await lists_repo.search(
                conn,
                page=page,
                viewer_id=principal.user_id,
                viewer_is_admin=principal.is_admin,
                query="",
                visibilities=[],
                roles=["owner"],
                include_archived=True,
                sort_field="position",
                descending=False,
            )
            trimmed, _ = pagination.trim(rows, page)
            ids = [str(row["id"]) for row in trimmed]
            members = await lists_repo.members_for_lists(conn, ids)
            labels = await lists_repo.labels_for_lists(conn, ids)
        return list_pb2.ReorderListsResponse(
            lists=[
                mappers.todo_list(
                    row,
                    members=members.get(str(row["id"]), []),
                    labels=labels.get(str(row["id"]), []),
                )
                for row in trimmed
            ]
        )

    # --- Membership ---------------------------------------------------------

    async def list_members(
        self, request: list_pb2.ListMembersRequest, ctx: RequestContext
    ) -> list_pb2.ListMembersResponse:
        """Lists who has access to a list, and at what level."""
        principal = require_principal(ctx)
        list_id = validation.uuid_value(request.list_id, field="list_id")
        async with self._db.connection() as conn:
            await permissions.require_read(conn, list_id, principal)
            rows = await lists_repo.list_members(conn, list_id)
        return list_pb2.ListMembersResponse(members=[mappers.list_member(row) for row in rows])

    async def add_member(
        self, request: list_pb2.AddMemberRequest, ctx: RequestContext
    ) -> list_pb2.AddMemberResponse:
        """Grants someone access to a list. Owner only, verified address required.

        Sharing reaches another person's inbox, so an unverified account cannot do
        it. Adding by email only resolves an *existing* account — this endpoint does
        not create accounts for strangers, which would make it a spam vector.
        """
        principal = require_verified_email(ctx)
        list_id = validation.uuid_value(request.list_id, field="list_id")
        role = enums.MEMBER_ROLE.to_db_or(
            request.role, enums.MEMBER_ROLE.from_db("viewer"), field="role"
        )
        if role == "owner":
            raise invalid_argument(
                Reason.ERROR_REASON_VALIDATION_FAILED,
                "a list has exactly one owner; transfer instead of adding",
                field="role",
            )

        async with self._db.transaction() as conn:
            await permissions.require_owner(conn, list_id, principal)
            list_row = await lists_repo.get(
                conn, list_id, viewer_id=principal.user_id, viewer_is_admin=principal.is_admin
            )
            if list_row is None:
                raise not_found(Reason.ERROR_REASON_LIST_NOT_FOUND, f"list {list_id} not found")

            invitee = await self._resolve_invitee(conn, request)
            try:
                await lists_repo.add_member(
                    conn,
                    list_id=list_id,
                    user_id=invitee["id"],
                    role=role,
                    invited_by_id=principal.user_id,
                )
            except psycopg.errors.UniqueViolation as err:
                raise already_exists(
                    Reason.ERROR_REASON_MEMBER_ALREADY_ADDED,
                    "that person already has access to this list",
                ) from err

            await activity_repo.record(
                conn,
                actor_id=principal.user_id,
                action="member_added",
                target_type="membership",
                target_id=str(invitee["id"]),
                target_label=invitee["display_name"],
                list_id=list_id,
                field="role",
                to_value=role,
            )
            member = await lists_repo.get_member(conn, list_id=list_id, user_id=str(invitee["id"]))
        assert member is not None
        return list_pb2.AddMemberResponse(member=mappers.list_member(member))

    async def update_member_role(
        self, request: list_pb2.UpdateMemberRoleRequest, ctx: RequestContext
    ) -> list_pb2.UpdateMemberRoleResponse:
        """Changes a member's role. Owner only.

        The owner's own role cannot be changed here: a list without an owner would
        violate ``list_members_single_owner_idx`` and leave nobody able to share or
        delete it.
        """
        principal = require_principal(ctx)
        list_id = validation.uuid_value(request.list_id, field="list_id")
        user_id = validation.uuid_value(request.user_id, field="user_id")
        role = enums.MEMBER_ROLE.to_db(request.role, field="role")
        if role == "owner":
            raise invalid_argument(
                Reason.ERROR_REASON_VALIDATION_FAILED,
                "ownership cannot be granted through a role change",
                field="role",
            )

        async with self._db.transaction() as conn:
            await permissions.require_owner(conn, list_id, principal)
            existing = await lists_repo.get_member(conn, list_id=list_id, user_id=user_id)
            if existing is None:
                raise not_found(Reason.ERROR_REASON_MEMBER_NOT_FOUND, "that person is not a member")
            if existing["role"] == "owner":
                raise failed_precondition(
                    Reason.ERROR_REASON_CANNOT_DEMOTE_SELF,
                    "the list owner's role cannot be changed",
                    field="role",
                )
            await lists_repo.set_member_role(conn, list_id=list_id, user_id=user_id, role=role)

            # Losing write access means open assignments no longer make sense.
            if role not in enums.WRITE_ROLES:
                await tasks_repo.clear_assignee_for_user(conn, list_id=list_id, user_id=user_id)

            await activity_repo.record(
                conn,
                actor_id=principal.user_id,
                action="member_role_changed",
                target_type="membership",
                target_id=user_id,
                target_label=existing["display_name"],
                list_id=list_id,
                field="role",
                from_value=existing["role"],
                to_value=role,
            )
            member = await lists_repo.get_member(conn, list_id=list_id, user_id=user_id)
        assert member is not None
        return list_pb2.UpdateMemberRoleResponse(member=mappers.list_member(member))

    async def remove_member(
        self, request: list_pb2.RemoveMemberRequest, ctx: RequestContext
    ) -> list_pb2.RemoveMemberResponse:
        """Revokes someone's access. The owner, or a member removing themselves.

        Letting a member leave on their own is the reason this is not owner-only.
        """
        principal = require_principal(ctx)
        list_id = validation.uuid_value(request.list_id, field="list_id")
        user_id = validation.uuid_value(request.user_id, field="user_id")

        async with self._db.transaction() as conn:
            if user_id == principal.user_id:
                await permissions.require_read(conn, list_id, principal)
            else:
                await permissions.require_owner(conn, list_id, principal)

            existing = await lists_repo.get_member(conn, list_id=list_id, user_id=user_id)
            if existing is None:
                raise not_found(Reason.ERROR_REASON_MEMBER_NOT_FOUND, "that person is not a member")
            if existing["role"] == "owner":
                raise failed_precondition(
                    Reason.ERROR_REASON_CANNOT_REMOVE_OWNER,
                    "the owner cannot be removed from their own list",
                )

            await tasks_repo.clear_assignee_for_user(conn, list_id=list_id, user_id=user_id)
            await lists_repo.remove_member(conn, list_id=list_id, user_id=user_id)
            await activity_repo.record(
                conn,
                actor_id=principal.user_id,
                action="member_removed",
                target_type="membership",
                target_id=user_id,
                target_label=existing["display_name"],
                list_id=list_id,
            )
        return list_pb2.RemoveMemberResponse()

    # --- Labels -------------------------------------------------------------

    async def list_labels(
        self, request: list_pb2.ListLabelsRequest, ctx: RequestContext
    ) -> list_pb2.ListLabelsResponse:
        """Lists a list's labels with how many tasks use each."""
        principal = require_principal(ctx)
        list_id = validation.uuid_value(request.list_id, field="list_id")
        async with self._db.connection() as conn:
            await permissions.require_read(conn, list_id, principal)
            rows = await lists_repo.list_labels(conn, list_id)
        return list_pb2.ListLabelsResponse(labels=[mappers.label(row) for row in rows])

    async def create_label(
        self, request: list_pb2.CreateLabelRequest, ctx: RequestContext
    ) -> list_pb2.CreateLabelResponse:
        """Adds a label to a list. Labels are list-scoped, never global."""
        principal = require_principal(ctx)
        list_id = validation.uuid_value(request.list_id, field="list_id")
        name = validation.required_text(
            request.name, field="name", max_length=validation.MAX_LABEL_NAME
        )
        color = enums.LIST_COLOR.to_db_or(
            request.color, enums.LIST_COLOR.from_db("zinc"), field="color"
        )

        async with self._db.transaction() as conn:
            await permissions.require_write(conn, list_id, principal)
            try:
                label_id = await lists_repo.create_label(
                    conn, list_id=list_id, name=name, color=color
                )
            except psycopg.errors.UniqueViolation as err:
                raise already_exists(
                    Reason.ERROR_REASON_LABEL_NAME_TAKEN,
                    "this list already has a label with that name",
                    field="name",
                ) from err
            await activity_repo.record(
                conn,
                actor_id=principal.user_id,
                action="created",
                target_type="list",
                target_id=label_id,
                target_label=name,
                list_id=list_id,
                field="label",
                to_value=name,
            )
            row = await lists_repo.get_label(conn, label_id)
        assert row is not None
        return list_pb2.CreateLabelResponse(label=mappers.label(row))

    async def update_label(
        self, request: list_pb2.UpdateLabelRequest, ctx: RequestContext
    ) -> list_pb2.UpdateLabelResponse:
        """Renames or recolours a label."""
        principal = require_principal(ctx)
        label_id = validation.uuid_value(request.id, field="id")
        name = (
            validation.required_text(
                request.name, field="name", max_length=validation.MAX_LABEL_NAME
            )
            if request.HasField("name")
            else None
        )
        color = (
            enums.LIST_COLOR.to_db(request.color, field="color")
            if request.HasField("color")
            else None
        )
        if name is None and color is None:
            raise invalid_argument(Reason.ERROR_REASON_NO_CHANGE_REQUESTED, "no fields to update")

        async with self._db.transaction() as conn:
            existing = await lists_repo.get_label(conn, label_id)
            if existing is None:
                raise not_found(Reason.ERROR_REASON_LABEL_NOT_FOUND, f"label {label_id} not found")
            await permissions.require_write(conn, str(existing["list_id"]), principal)
            try:
                await lists_repo.update_label(conn, label_id, name=name, color=color)
            except psycopg.errors.UniqueViolation as err:
                raise already_exists(
                    Reason.ERROR_REASON_LABEL_NAME_TAKEN,
                    "this list already has a label with that name",
                    field="name",
                ) from err
            row = await lists_repo.get_label(conn, label_id)
        assert row is not None
        return list_pb2.UpdateLabelResponse(label=mappers.label(row))

    async def delete_label(
        self, request: list_pb2.DeleteLabelRequest, ctx: RequestContext
    ) -> list_pb2.DeleteLabelResponse:
        """Deletes a label and detaches it from every task that carried it."""
        principal = require_principal(ctx)
        label_id = validation.uuid_value(request.id, field="id")
        async with self._db.transaction() as conn:
            existing = await lists_repo.get_label(conn, label_id)
            if existing is None:
                raise not_found(Reason.ERROR_REASON_LABEL_NOT_FOUND, f"label {label_id} not found")
            await permissions.require_write(conn, str(existing["list_id"]), principal)
            await lists_repo.delete_label(conn, label_id)
            await activity_repo.record(
                conn,
                actor_id=principal.user_id,
                action="deleted",
                target_type="list",
                target_id=label_id,
                target_label=existing["name"],
                list_id=str(existing["list_id"]),
                field="label",
                from_value=existing["name"],
            )
        return list_pb2.DeleteLabelResponse()

    # --- Internals ----------------------------------------------------------

    async def _load(self, list_id: str, principal: Principal) -> list_pb2.TodoList:
        """Reads a list back after a write, with members and labels attached."""
        async with self._db.connection() as conn:
            row = await lists_repo.get(
                conn, list_id, viewer_id=principal.user_id, viewer_is_admin=principal.is_admin
            )
            if row is None:
                raise not_found(Reason.ERROR_REASON_LIST_NOT_FOUND, f"list {list_id} not found")
            members = await lists_repo.list_members(conn, list_id)
            labels = await lists_repo.list_labels(conn, list_id)
        return mappers.todo_list(row, members=members, labels=labels)

    async def _resolve_invitee(
        self, conn: psycopg.AsyncConnection, request: list_pb2.AddMemberRequest
    ) -> dict[str, object]:
        """Resolves the ``invitee`` oneof to an existing active account."""
        which = request.WhichOneof("invitee")
        if which == "user_id":
            user_id = validation.uuid_value(request.user_id, field="user_id")
            row = await users_repo.get_by_id(conn, user_id)
        elif which == "email":
            row = await users_repo.get_by_email(conn, validation.email(request.email))
        else:
            raise invalid_argument(
                Reason.ERROR_REASON_FIELD_REQUIRED,
                "either user_id or email is required",
                field="invitee",
            )
        if row is None:
            raise not_found(Reason.ERROR_REASON_USER_NOT_FOUND, "no account matches that person")
        if row["status"] != "active":
            raise failed_precondition(
                Reason.ERROR_REASON_VALIDATION_FAILED,
                "that account cannot be added to a list right now",
            )
        return {"id": str(row["id"]), "display_name": row["display_name"]}


def _is_descending(direction: int, *, default_descending: bool = True) -> bool:
    """Maps a :class:`SortDirection` to a boolean, with a per-listing default."""
    if direction == 1:  # SORT_DIRECTION_ASC
        return False
    if direction == 2:  # SORT_DIRECTION_DESC
        return True
    return default_descending


def _list_sort_field(value: int) -> str:
    """Maps a :class:`ListSortField` to a repository sort key."""
    return {1: "position", 2: "created_at", 3: "updated_at", 4: "name"}.get(value, "position")
