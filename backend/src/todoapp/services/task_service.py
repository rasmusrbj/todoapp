"""``todo.v1.TaskService`` — tasks, subtasks, comments, and the activity feed.

Two rules run through the whole module:

* **The parent list is the unit of authorization.** A handler resolves the task's
  ``list_id`` from storage and authorizes against that, never against a list id that
  arrived in the request.
* **A completed recurring task spawns its successor** rather than having its own due
  date moved forward, so "pay rent" completed in March and in April remain two
  records.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from connectrpc.request import RequestContext
from google.protobuf.timestamp_pb2 import Timestamp

from todo.v1 import task_pb2
from todoapp.auth import permissions
from todoapp.auth.context import Principal, require_principal
from todoapp.db.pool import Database
from todoapp.domain import enums, validation
from todoapp.domain.recurrence import Recurrence, next_occurrence, shift
from todoapp.errors import Reason, invalid_argument, not_found, permission_denied
from todoapp.repositories import activity as activity_repo
from todoapp.repositories import lists as lists_repo
from todoapp.repositories import pagination
from todoapp.repositories import tasks as tasks_repo
from todoapp.services import mappers

logger = logging.getLogger("todoapp.services.task")

_MAX_LABEL_IDS_PER_TASK = 25


def _to_datetime(stamp: Timestamp | None) -> datetime | None:
    """Converts a proto timestamp to an aware ``datetime``, preserving ``None``."""
    if stamp is None:
        return None
    return stamp.ToDatetime(tzinfo=UTC)


class TaskService:
    """Implements the generated ``todo.v1.TaskService`` protocol."""

    def __init__(self, *, database: Database) -> None:
        """Wires the service to the connection pool."""
        self._db = database

    # --- Reads --------------------------------------------------------------

    async def get_task(
        self, request: task_pb2.GetTaskRequest, ctx: RequestContext
    ) -> task_pb2.GetTaskResponse:
        """Returns one task with its list, people, labels, and subtasks."""
        principal = require_principal(ctx)
        task_id = validation.uuid_value(request.id, field="id")
        async with self._db.connection() as conn:
            row = await tasks_repo.get(
                conn, task_id, viewer_id=principal.user_id, viewer_is_admin=principal.is_admin
            )
            if row is None:
                raise not_found(Reason.ERROR_REASON_TASK_NOT_FOUND, f"task {task_id} not found")
            labels = await tasks_repo.labels_for_tasks(conn, [task_id])
            subtasks = await tasks_repo.subtasks_for_tasks(conn, [task_id])
        return task_pb2.GetTaskResponse(
            task=mappers.task(
                row, labels=labels.get(task_id, []), subtasks=subtasks.get(task_id, [])
            )
        )

    async def list_tasks(
        self, request: task_pb2.ListTasksRequest, ctx: RequestContext
    ) -> task_pb2.ListTasksResponse:
        """Lists tasks the caller can read, with filters, sorting, and status counts.

        Labels and subtasks for the whole page are loaded in one query each, so a
        50-row list costs four round-trips regardless of how many labels are in play.
        """
        principal = require_principal(ctx)
        page = pagination.resolve_page(request.page)

        due_after = _to_datetime(request.due_after if request.HasField("due_after") else None)
        due_before = _to_datetime(request.due_before if request.HasField("due_before") else None)
        if due_after and due_before and due_after > due_before:
            raise invalid_argument(
                Reason.ERROR_REASON_INVALID_DATE_RANGE,
                "due_after must not be later than due_before",
                field="due_after",
            )

        async with self._db.connection() as conn:
            rows, total, status_counts = await tasks_repo.search(
                conn,
                page=page,
                viewer_id=principal.user_id,
                viewer_is_admin=principal.is_admin,
                list_ids=validation.uuid_values(request.list_ids, field="list_ids", max_count=100),
                query=request.query,
                statuses=enums.TASK_STATUS.many_to_db(request.statuses, field="statuses"),
                priorities=enums.TASK_PRIORITY.many_to_db(request.priorities, field="priorities"),
                label_ids=validation.uuid_values(
                    request.label_ids, field="label_ids", max_count=100
                ),
                assignee_ids=validation.uuid_values(
                    request.assignee_ids, field="assignee_ids", max_count=100
                ),
                unassigned_only=request.unassigned_only,
                due_after=due_after,
                due_before=due_before,
                overdue_only=request.overdue_only,
                sort_field=_task_sort_field(request.sort_field),
                descending=_is_descending(request.sort_direction, default_descending=False),
            )
            trimmed, has_more = pagination.trim(rows, page)
            task_ids = [str(row["id"]) for row in trimmed]
            labels = await tasks_repo.labels_for_tasks(conn, task_ids)
            subtasks = await tasks_repo.subtasks_for_tasks(conn, task_ids)

        return task_pb2.ListTasksResponse(
            tasks=[
                mappers.task(
                    row,
                    labels=labels.get(str(row["id"]), []),
                    subtasks=subtasks.get(str(row["id"]), []),
                )
                for row in trimmed
            ],
            page=pagination.page_response(page, total_count=total, has_more=has_more),
            status_counts=status_counts,
        )

    # --- Writes -------------------------------------------------------------

    async def create_task(
        self, request: task_pb2.CreateTaskRequest, ctx: RequestContext
    ) -> task_pb2.CreateTaskResponse:
        """Creates a task at the top of its list, with optional labels and checklist."""
        principal = require_principal(ctx)
        list_id = validation.uuid_value(request.list_id, field="list_id")
        title = validation.required_text(
            request.title, field="title", max_length=validation.MAX_TASK_TITLE
        )
        description = validation.optional_text(
            request.description, field="description", max_length=validation.MAX_TASK_DESCRIPTION
        )
        status = enums.TASK_STATUS.to_db_or(
            request.status, enums.TASK_STATUS.from_db("todo"), field="status"
        )
        priority = enums.TASK_PRIORITY.to_db_or(
            request.priority, enums.TASK_PRIORITY.from_db("none"), field="priority"
        )
        estimate = validation.bounded_int(
            request.estimate_minutes,
            field="estimate_minutes",
            minimum=0,
            maximum=validation.MAX_ESTIMATE_MINUTES,
        )
        due_at = _to_datetime(request.due_at if request.HasField("due_at") else None)
        starts_at = _to_datetime(request.starts_at if request.HasField("starts_at") else None)
        recurrence = self._read_recurrence(request.recurrence)
        self._check_schedule(due_at=due_at, starts_at=starts_at, due_has_time=request.due_has_time)

        label_ids = validation.uuid_values(
            request.label_ids, field="label_ids", max_count=_MAX_LABEL_IDS_PER_TASK
        )
        subtask_titles = [
            validation.required_text(
                title_, field="subtask_titles", max_length=validation.MAX_TASK_TITLE
            )
            for title_ in list(request.subtask_titles)[: validation.MAX_SUBTASKS_PER_CREATE]
        ]

        async with self._db.transaction() as conn:
            await permissions.require_write(conn, list_id, principal)
            assignee_id = await self._resolve_assignee(
                conn,
                list_id=list_id,
                assignee_id=request.assignee_id if request.HasField("assignee_id") else None,
            )
            if label_ids:
                await self._check_labels_on_list(conn, list_id=list_id, label_ids=label_ids)

            task_id = await tasks_repo.create(
                conn,
                list_id=list_id,
                created_by_id=principal.user_id,
                title=title,
                description=description,
                status=status,
                priority=priority,
                assignee_id=assignee_id,
                due_at=due_at,
                due_has_time=request.due_has_time,
                starts_at=starts_at,
                estimate_minutes=estimate,
                recurrence_frequency=recurrence.frequency,
                recurrence_interval=recurrence.interval,
                recurrence_until=recurrence.until,
            )
            if label_ids:
                await tasks_repo.set_labels(conn, task_id, label_ids)
            if subtask_titles:
                await tasks_repo.create_subtasks(conn, task_id=task_id, titles=subtask_titles)
            await activity_repo.record(
                conn,
                actor_id=principal.user_id,
                action="created",
                target_type="task",
                target_id=task_id,
                target_label=title,
                list_id=list_id,
                task_id=task_id,
            )
        return task_pb2.CreateTaskResponse(task=await self._load(task_id, principal))

    async def update_task(
        self, request: task_pb2.UpdateTaskRequest, ctx: RequestContext
    ) -> task_pb2.UpdateTaskResponse:
        """Applies a partial task update.

        Dates need an explicit clear flag: proto3 cannot distinguish "leave the due
        date alone" from "remove it" through field presence on its own, so
        ``clear_due_at`` and ``clear_starts_at`` say it out loud.
        """
        principal = require_principal(ctx)
        task_id = validation.uuid_value(request.id, field="id")

        changes: dict[str, Any] = {}
        if request.HasField("title"):
            changes["title"] = validation.required_text(
                request.title, field="title", max_length=validation.MAX_TASK_TITLE
            )
        if request.HasField("description"):
            changes["description"] = validation.optional_text(
                request.description,
                field="description",
                max_length=validation.MAX_TASK_DESCRIPTION,
            )
        if request.HasField("priority"):
            changes["priority"] = enums.TASK_PRIORITY.to_db(request.priority, field="priority")
        if request.HasField("estimate_minutes"):
            changes["estimate_minutes"] = validation.bounded_int(
                request.estimate_minutes,
                field="estimate_minutes",
                minimum=0,
                maximum=validation.MAX_ESTIMATE_MINUTES,
            )
        if request.HasField("recurrence"):
            recurrence = self._read_recurrence(request.recurrence)
            changes["recurrence_frequency"] = recurrence.frequency
            changes["recurrence_interval"] = recurrence.interval
            changes["recurrence_until"] = recurrence.until

        if request.clear_due_at:
            changes["due_at"] = None
            changes["due_has_time"] = False
        elif request.HasField("due_at"):
            changes["due_at"] = _to_datetime(request.due_at)
            changes["due_has_time"] = (
                request.due_has_time if request.HasField("due_has_time") else False
            )
        elif request.HasField("due_has_time"):
            changes["due_has_time"] = request.due_has_time

        if request.clear_starts_at:
            changes["starts_at"] = None
        elif request.HasField("starts_at"):
            changes["starts_at"] = _to_datetime(request.starts_at)

        if not changes:
            raise invalid_argument(Reason.ERROR_REASON_NO_CHANGE_REQUESTED, "no fields to update")

        async with self._db.transaction() as conn:
            list_id, before = await self._authorize_write(conn, task_id, principal)
            self._check_schedule(
                due_at=changes.get("due_at", before.get("due_at")),
                starts_at=changes.get("starts_at", before.get("starts_at")),
                due_has_time=bool(changes.get("due_has_time", before.get("due_has_time"))),
            )
            if not await tasks_repo.update(conn, task_id, changes):
                raise not_found(Reason.ERROR_REASON_TASK_NOT_FOUND, f"task {task_id} not found")
            for field, value in changes.items():
                await activity_repo.record(
                    conn,
                    actor_id=principal.user_id,
                    action="updated",
                    target_type="task",
                    target_id=task_id,
                    target_label=str(changes.get("title", before["title"])),
                    list_id=list_id,
                    task_id=task_id,
                    field=field,
                    from_value=_as_text(before.get(field)),
                    to_value=_as_text(value),
                )
        return task_pb2.UpdateTaskResponse(task=await self._load(task_id, principal))

    async def set_task_status(
        self, request: task_pb2.SetTaskStatusRequest, ctx: RequestContext
    ) -> task_pb2.SetTaskStatusResponse:
        """Moves a task to a new status, rolling a recurrence forward when finished.

        Completing a repeating task creates the next occurrence in the same
        transaction, so the follow-up either exists or the completion did not happen.
        """
        principal = require_principal(ctx)
        task_id = validation.uuid_value(request.id, field="id")
        status = enums.TASK_STATUS.to_db(request.status, field="status")

        next_task_id: str | None = None
        async with self._db.transaction() as conn:
            list_id, before = await self._authorize_write(conn, task_id, principal)
            changed = await tasks_repo.set_status(
                conn, task_id, status=status, actor_id=principal.user_id
            )
            if changed is None:
                raise not_found(Reason.ERROR_REASON_TASK_NOT_FOUND, f"task {task_id} not found")

            old_status = changed["old_status"]
            if old_status != status:
                await activity_repo.record(
                    conn,
                    actor_id=principal.user_id,
                    action="status_changed",
                    target_type="task",
                    target_id=task_id,
                    target_label=before["title"],
                    list_id=list_id,
                    task_id=task_id,
                    field="status",
                    from_value=old_status,
                    to_value=status,
                )

            # Only a genuine transition into `done` rolls the rule forward. Cancelling
            # a repeating task ends the series; re-completing an already-done task
            # must not produce a second follow-up.
            if status == "done" and old_status != "done":
                next_task_id = await self._spawn_next_occurrence(
                    conn, before, list_id=list_id, principal=principal
                )

        response = task_pb2.SetTaskStatusResponse(task=await self._load(task_id, principal))
        if next_task_id is not None:
            response.next_occurrence.CopyFrom(await self._load(next_task_id, principal))
        return response

    async def assign_task(
        self, request: task_pb2.AssignTaskRequest, ctx: RequestContext
    ) -> task_pb2.AssignTaskResponse:
        """Sets or clears a task's assignee.

        The assignee must be able to write the list — assigning work to someone who
        cannot open it is never what was meant.
        """
        principal = require_principal(ctx)
        task_id = validation.uuid_value(request.id, field="id")

        async with self._db.transaction() as conn:
            list_id, before = await self._authorize_write(conn, task_id, principal)
            assignee_id = await self._resolve_assignee(
                conn,
                list_id=list_id,
                assignee_id=request.assignee_id if request.HasField("assignee_id") else None,
            )
            if not await tasks_repo.set_assignee(conn, task_id, assignee_id):
                raise not_found(Reason.ERROR_REASON_TASK_NOT_FOUND, f"task {task_id} not found")
            await activity_repo.record(
                conn,
                actor_id=principal.user_id,
                action="assigned" if assignee_id else "unassigned",
                target_type="task",
                target_id=task_id,
                target_label=before["title"],
                list_id=list_id,
                task_id=task_id,
                field="assignee_id",
                from_value=_as_text(before.get("assignee_id")),
                to_value=assignee_id or "",
            )
        return task_pb2.AssignTaskResponse(task=await self._load(task_id, principal))

    async def move_task(
        self, request: task_pb2.MoveTaskRequest, ctx: RequestContext
    ) -> task_pb2.MoveTaskResponse:
        """Reorders a task, optionally moving it to another list.

        Write access to *both* lists is required. Labels do not travel with the task,
        because a label belongs to one list.
        """
        principal = require_principal(ctx)
        task_id = validation.uuid_value(request.id, field="id")
        position = validation.bounded_int(
            request.position, field="position", minimum=0, maximum=100_000
        )
        target_list_id = (
            validation.uuid_value(request.list_id, field="list_id")
            if request.HasField("list_id")
            else None
        )

        async with self._db.transaction() as conn:
            source_list_id, before = await self._authorize_write(conn, task_id, principal)
            if target_list_id is not None and target_list_id != source_list_id:
                await permissions.require_write(conn, target_list_id, principal)
            if not await tasks_repo.move(conn, task_id, list_id=target_list_id, position=position):
                raise not_found(Reason.ERROR_REASON_TASK_NOT_FOUND, f"task {task_id} not found")
            if target_list_id is not None and target_list_id != source_list_id:
                await activity_repo.record(
                    conn,
                    actor_id=principal.user_id,
                    action="updated",
                    target_type="task",
                    target_id=task_id,
                    target_label=before["title"],
                    list_id=target_list_id,
                    task_id=task_id,
                    field="list_id",
                    from_value=source_list_id,
                    to_value=target_list_id,
                )
        return task_pb2.MoveTaskResponse(task=await self._load(task_id, principal))

    async def delete_task(
        self, request: task_pb2.DeleteTaskRequest, ctx: RequestContext
    ) -> task_pb2.DeleteTaskResponse:
        """Deletes a task along with its subtasks and comments."""
        principal = require_principal(ctx)
        task_id = validation.uuid_value(request.id, field="id")
        async with self._db.transaction() as conn:
            list_id, before = await self._authorize_write(conn, task_id, principal)
            # Recorded before the delete, so the entry survives the cascade.
            await activity_repo.record(
                conn,
                actor_id=principal.user_id,
                action="deleted",
                target_type="task",
                target_id=task_id,
                target_label=before["title"],
                list_id=list_id,
            )
            if not await tasks_repo.delete(conn, task_id):
                raise not_found(Reason.ERROR_REASON_TASK_NOT_FOUND, f"task {task_id} not found")
        return task_pb2.DeleteTaskResponse()

    async def bulk_update_tasks(
        self, request: task_pb2.BulkUpdateTasksRequest, ctx: RequestContext
    ) -> task_pb2.BulkUpdateTasksResponse:
        """Applies one change to many tasks.

        Ids the caller cannot write are dropped rather than failing the request: a
        multi-select spanning a list that was just unshared should still apply to
        everything else. ``updated_count`` reports what actually changed.
        """
        principal = require_principal(ctx)
        task_ids = validation.uuid_values(
            request.task_ids, field="task_ids", max_count=validation.MAX_BULK_TASK_IDS
        )
        if not task_ids:
            raise invalid_argument(
                Reason.ERROR_REASON_FIELD_REQUIRED, "task_ids is required", field="task_ids"
            )
        which = request.WhichOneof("change")
        if which is None:
            raise invalid_argument(
                Reason.ERROR_REASON_NO_CHANGE_REQUESTED, "one change field is required"
            )

        async with self._db.transaction() as conn:
            writable = await tasks_repo.readable_task_ids(
                conn, task_ids, viewer_id=principal.user_id, viewer_is_admin=principal.is_admin
            )
            if not writable:
                raise permission_denied(
                    Reason.ERROR_REASON_PERMISSION_DENIED, "none of those tasks can be edited"
                )
            updated = await self._apply_bulk_change(conn, which, request, writable, principal)

        # Read the affected tasks back so the client can replace its rows outright.
        page = pagination.Page(limit=min(len(writable), pagination.MAX_LIMIT), offset=0)
        async with self._db.connection() as conn:
            rows, _, _ = await tasks_repo.search(
                conn,
                page=page,
                viewer_id=principal.user_id,
                viewer_is_admin=principal.is_admin,
                list_ids=[],
                query="",
                statuses=[],
                priorities=[],
                label_ids=[],
                assignee_ids=[],
                unassigned_only=False,
                due_after=None,
                due_before=None,
                overdue_only=False,
                sort_field="updated_at",
                descending=True,
            )
            by_id = {str(row["id"]): row for row in rows}
            selected = [by_id[task_id] for task_id in writable if task_id in by_id]
            labels = await tasks_repo.labels_for_tasks(conn, [str(r["id"]) for r in selected])
            subtasks = await tasks_repo.subtasks_for_tasks(conn, [str(r["id"]) for r in selected])

        return task_pb2.BulkUpdateTasksResponse(
            tasks=[
                mappers.task(
                    row,
                    labels=labels.get(str(row["id"]), []),
                    subtasks=subtasks.get(str(row["id"]), []),
                )
                for row in selected
            ],
            updated_count=updated,
        )

    async def set_task_labels(
        self, request: task_pb2.SetTaskLabelsRequest, ctx: RequestContext
    ) -> task_pb2.SetTaskLabelsResponse:
        """Replaces a task's labels with exactly the requested set."""
        principal = require_principal(ctx)
        task_id = validation.uuid_value(request.task_id, field="task_id")
        label_ids = validation.uuid_values(
            request.label_ids, field="label_ids", max_count=_MAX_LABEL_IDS_PER_TASK
        )
        async with self._db.transaction() as conn:
            list_id, _ = await self._authorize_write(conn, task_id, principal)
            if label_ids:
                await self._check_labels_on_list(conn, list_id=list_id, label_ids=label_ids)
            await tasks_repo.set_labels(conn, task_id, label_ids)
        return task_pb2.SetTaskLabelsResponse(task=await self._load(task_id, principal))

    # --- Subtasks -----------------------------------------------------------

    async def create_subtask(
        self, request: task_pb2.CreateSubtaskRequest, ctx: RequestContext
    ) -> task_pb2.CreateSubtaskResponse:
        """Appends an item to a task's checklist."""
        principal = require_principal(ctx)
        task_id = validation.uuid_value(request.task_id, field="task_id")
        title = validation.required_text(
            request.title, field="title", max_length=validation.MAX_TASK_TITLE
        )
        async with self._db.transaction() as conn:
            await self._authorize_write(conn, task_id, principal)
            subtask_id = await tasks_repo.create_subtask(conn, task_id=task_id, title=title)
            row = await tasks_repo.get_subtask(conn, subtask_id)
        assert row is not None
        return task_pb2.CreateSubtaskResponse(subtask=mappers.subtask(row))

    async def update_subtask(
        self, request: task_pb2.UpdateSubtaskRequest, ctx: RequestContext
    ) -> task_pb2.UpdateSubtaskResponse:
        """Renames, ticks off, or repositions a checklist item."""
        principal = require_principal(ctx)
        subtask_id = validation.uuid_value(request.id, field="id")
        title = (
            validation.required_text(
                request.title, field="title", max_length=validation.MAX_TASK_TITLE
            )
            if request.HasField("title")
            else None
        )
        completed = request.completed if request.HasField("completed") else None
        position = (
            validation.bounded_int(request.position, field="position", minimum=0, maximum=10_000)
            if request.HasField("position")
            else None
        )
        if title is None and completed is None and position is None:
            raise invalid_argument(Reason.ERROR_REASON_NO_CHANGE_REQUESTED, "no fields to update")

        async with self._db.transaction() as conn:
            existing = await tasks_repo.get_subtask(conn, subtask_id)
            if existing is None:
                raise not_found(
                    Reason.ERROR_REASON_SUBTASK_NOT_FOUND, f"subtask {subtask_id} not found"
                )
            await self._authorize_write(conn, str(existing["task_id"]), principal)
            await tasks_repo.update_subtask(
                conn, subtask_id, title=title, completed=completed, position=position
            )
            row = await tasks_repo.get_subtask(conn, subtask_id)
        assert row is not None
        return task_pb2.UpdateSubtaskResponse(subtask=mappers.subtask(row))

    async def delete_subtask(
        self, request: task_pb2.DeleteSubtaskRequest, ctx: RequestContext
    ) -> task_pb2.DeleteSubtaskResponse:
        """Removes a checklist item."""
        principal = require_principal(ctx)
        subtask_id = validation.uuid_value(request.id, field="id")
        async with self._db.transaction() as conn:
            existing = await tasks_repo.get_subtask(conn, subtask_id)
            if existing is None:
                raise not_found(
                    Reason.ERROR_REASON_SUBTASK_NOT_FOUND, f"subtask {subtask_id} not found"
                )
            await self._authorize_write(conn, str(existing["task_id"]), principal)
            await tasks_repo.delete_subtask(conn, subtask_id)
        return task_pb2.DeleteSubtaskResponse()

    # --- Comments -----------------------------------------------------------

    async def list_comments(
        self, request: task_pb2.ListCommentsRequest, ctx: RequestContext
    ) -> task_pb2.ListCommentsResponse:
        """Lists a task's comments, newest first."""
        principal = require_principal(ctx)
        task_id = validation.uuid_value(request.task_id, field="task_id")
        page = pagination.resolve_page(request.page)
        async with self._db.connection() as conn:
            list_id = await tasks_repo.get_list_id(conn, task_id)
            if list_id is None:
                raise not_found(Reason.ERROR_REASON_TASK_NOT_FOUND, f"task {task_id} not found")
            await permissions.require_read(conn, list_id, principal)
            rows, total = await tasks_repo.list_comments(conn, task_id, page=page)
        trimmed, has_more = pagination.trim(rows, page)
        return task_pb2.ListCommentsResponse(
            comments=[mappers.comment(row) for row in trimmed],
            page=pagination.page_response(page, total_count=total, has_more=has_more),
        )

    async def create_comment(
        self, request: task_pb2.CreateCommentRequest, ctx: RequestContext
    ) -> task_pb2.CreateCommentResponse:
        """Adds a comment. Commenters may do this; viewers may not."""
        principal = require_principal(ctx)
        task_id = validation.uuid_value(request.task_id, field="task_id")
        body = validation.required_text(
            request.body, field="body", max_length=validation.MAX_COMMENT_BODY
        )
        async with self._db.transaction() as conn:
            list_id = await tasks_repo.get_list_id(conn, task_id)
            if list_id is None:
                raise not_found(Reason.ERROR_REASON_TASK_NOT_FOUND, f"task {task_id} not found")
            await permissions.require_comment(conn, list_id, principal)
            comment_id = await tasks_repo.create_comment(
                conn, task_id=task_id, author_id=principal.user_id, body=body
            )
            await activity_repo.record(
                conn,
                actor_id=principal.user_id,
                action="commented",
                target_type="comment",
                target_id=comment_id,
                target_label=body[:80],
                list_id=list_id,
                task_id=task_id,
            )
            row = await tasks_repo.get_comment(conn, comment_id)
        assert row is not None
        return task_pb2.CreateCommentResponse(comment=mappers.comment(row))

    async def update_comment(
        self, request: task_pb2.UpdateCommentRequest, ctx: RequestContext
    ) -> task_pb2.UpdateCommentResponse:
        """Edits a comment. Authors only — not even the list owner may rewrite one."""
        principal = require_principal(ctx)
        comment_id = validation.uuid_value(request.id, field="id")
        body = validation.required_text(
            request.body, field="body", max_length=validation.MAX_COMMENT_BODY
        )
        async with self._db.transaction() as conn:
            existing = await tasks_repo.get_comment(conn, comment_id)
            if existing is None:
                raise not_found(
                    Reason.ERROR_REASON_COMMENT_NOT_FOUND, f"comment {comment_id} not found"
                )
            list_id = await tasks_repo.get_list_id(conn, str(existing["task_id"]))
            if list_id is None:
                raise not_found(Reason.ERROR_REASON_TASK_NOT_FOUND, "task no longer exists")
            await permissions.require_read(conn, list_id, principal)
            if str(existing.get("author_id")) != principal.user_id:
                raise permission_denied(
                    Reason.ERROR_REASON_PERMISSION_DENIED, "only the author can edit a comment"
                )
            await tasks_repo.update_comment(conn, comment_id, body)
            row = await tasks_repo.get_comment(conn, comment_id)
        assert row is not None
        return task_pb2.UpdateCommentResponse(comment=mappers.comment(row))

    async def delete_comment(
        self, request: task_pb2.DeleteCommentRequest, ctx: RequestContext
    ) -> task_pb2.DeleteCommentResponse:
        """Deletes a comment. The author, or the list owner moderating."""
        principal = require_principal(ctx)
        comment_id = validation.uuid_value(request.id, field="id")
        async with self._db.transaction() as conn:
            existing = await tasks_repo.get_comment(conn, comment_id)
            if existing is None:
                raise not_found(
                    Reason.ERROR_REASON_COMMENT_NOT_FOUND, f"comment {comment_id} not found"
                )
            list_id = await tasks_repo.get_list_id(conn, str(existing["task_id"]))
            if list_id is None:
                raise not_found(Reason.ERROR_REASON_TASK_NOT_FOUND, "task no longer exists")
            if str(existing.get("author_id")) == principal.user_id:
                await permissions.require_read(conn, list_id, principal)
            else:
                await permissions.require_owner(conn, list_id, principal)
            await tasks_repo.delete_comment(conn, comment_id)
        return task_pb2.DeleteCommentResponse()

    # --- Activity -----------------------------------------------------------

    async def list_activity(
        self, request: task_pb2.ListActivityRequest, ctx: RequestContext
    ) -> task_pb2.ListActivityResponse:
        """Lists the activity feed, optionally narrowed to one list or task."""
        principal = require_principal(ctx)
        page = pagination.resolve_page(request.page)
        list_id = (
            validation.uuid_value(request.list_id, field="list_id")
            if request.HasField("list_id")
            else None
        )
        task_id = (
            validation.uuid_value(request.task_id, field="task_id")
            if request.HasField("task_id")
            else None
        )
        async with self._db.connection() as conn:
            if list_id is not None:
                await permissions.require_read(conn, list_id, principal)
            if task_id is not None:
                owning_list = await tasks_repo.get_list_id(conn, task_id)
                if owning_list is None:
                    raise not_found(Reason.ERROR_REASON_TASK_NOT_FOUND, f"task {task_id} not found")
                await permissions.require_read(conn, owning_list, principal)
            rows, total = await activity_repo.search(
                conn,
                page=page,
                viewer_id=principal.user_id,
                viewer_is_admin=principal.is_admin,
                list_id=list_id,
                task_id=task_id,
                actions=enums.ACTIVITY_ACTION.many_to_db(request.actions, field="actions"),
            )
        trimmed, has_more = pagination.trim(rows, page)
        return task_pb2.ListActivityResponse(
            activities=[mappers.activity(row) for row in trimmed],
            page=pagination.page_response(page, total_count=total, has_more=has_more),
        )

    # --- Internals ----------------------------------------------------------

    async def _authorize_write(
        self, conn: Any, task_id: str, principal: Principal
    ) -> tuple[str, dict[str, Any]]:
        """Resolves a task's list, requires write access, and returns the current row.

        Returns:
            The parent list id and the task's row *before* the change, which the
            activity entries need for their ``from_value``.

        Raises:
            ConnectError: ``NOT_FOUND`` if the task is gone or invisible,
                ``PERMISSION_DENIED`` if the caller may only read or comment.
        """
        list_id = await tasks_repo.get_list_id(conn, task_id)
        if list_id is None:
            raise not_found(Reason.ERROR_REASON_TASK_NOT_FOUND, f"task {task_id} not found")
        await permissions.require_write(conn, list_id, principal)
        row = await tasks_repo.get(
            conn, task_id, viewer_id=principal.user_id, viewer_is_admin=principal.is_admin
        )
        if row is None:
            raise not_found(Reason.ERROR_REASON_TASK_NOT_FOUND, f"task {task_id} not found")
        return list_id, row

    async def _load(self, task_id: str, principal: Principal) -> task_pb2.Task:
        """Reads a task back after a write, with labels and subtasks attached."""
        async with self._db.connection() as conn:
            row = await tasks_repo.get(
                conn, task_id, viewer_id=principal.user_id, viewer_is_admin=principal.is_admin
            )
            if row is None:
                raise not_found(Reason.ERROR_REASON_TASK_NOT_FOUND, f"task {task_id} not found")
            labels = await tasks_repo.labels_for_tasks(conn, [task_id])
            subtasks = await tasks_repo.subtasks_for_tasks(conn, [task_id])
        return mappers.task(row, labels=labels.get(task_id, []), subtasks=subtasks.get(task_id, []))

    def _read_recurrence(self, message: task_pb2.Recurrence) -> Recurrence:
        """Validates a repeat rule from the wire.

        An interval is only meaningful alongside a frequency, so a rule of ``none``
        is normalised to interval 1 with no bound rather than rejected.
        """
        frequency = enums.RECURRENCE_FREQUENCY.to_db_or(
            message.frequency,
            enums.RECURRENCE_FREQUENCY.from_db("none"),
            field="recurrence.frequency",
        )
        if frequency == "none":
            return Recurrence(frequency="none", interval=1, until=None)
        interval = validation.bounded_int(
            message.interval or 1,
            field="recurrence.interval",
            minimum=1,
            maximum=validation.MAX_RECURRENCE_INTERVAL,
        )
        until = _to_datetime(message.until if message.HasField("until") else None)
        return Recurrence(frequency=frequency, interval=interval, until=until)

    def _check_schedule(
        self, *, due_at: datetime | None, starts_at: datetime | None, due_has_time: bool
    ) -> None:
        """Enforces the schedule invariants the schema also checks.

        Raises:
            ConnectError: ``INVALID_ARGUMENT`` when a start is after its due date, or
                a time-of-day is claimed without a due date to attach it to.
        """
        if due_has_time and due_at is None:
            raise invalid_argument(
                Reason.ERROR_REASON_VALIDATION_FAILED,
                "due_has_time requires a due date",
                field="due_has_time",
            )
        if due_at is not None and starts_at is not None and starts_at > due_at:
            raise invalid_argument(
                Reason.ERROR_REASON_INVALID_DATE_RANGE,
                "starts_at must not be later than due_at",
                field="starts_at",
            )

    async def _resolve_assignee(
        self, conn: Any, *, list_id: str, assignee_id: str | None
    ) -> str | None:
        """Validates an assignee, requiring them to hold write access to the list.

        Raises:
            ConnectError: ``INVALID_ARGUMENT`` when the person cannot edit the list.
        """
        if assignee_id is None or not assignee_id:
            return None
        user_id = validation.uuid_value(assignee_id, field="assignee_id")
        role = await lists_repo.viewer_role(conn, list_id, user_id)
        if role not in enums.WRITE_ROLES:
            raise invalid_argument(
                Reason.ERROR_REASON_ASSIGNEE_NOT_A_MEMBER,
                "the assignee must be able to edit this list",
                field="assignee_id",
            )
        return user_id

    async def _check_labels_on_list(self, conn: Any, *, list_id: str, label_ids: list[str]) -> None:
        """Rejects label ids that do not belong to ``list_id``.

        Raises:
            ConnectError: ``INVALID_ARGUMENT`` naming the count that did not match.
        """
        valid = await tasks_repo.label_ids_on_list(conn, list_id=list_id, label_ids=label_ids)
        missing = [label_id for label_id in label_ids if label_id not in valid]
        if missing:
            raise invalid_argument(
                Reason.ERROR_REASON_LABEL_NOT_ON_LIST,
                "one or more labels do not belong to this list",
                field="label_ids",
                metadata={"invalid_count": str(len(missing))},
            )

    async def _spawn_next_occurrence(
        self, conn: Any, before: dict[str, Any], *, list_id: str, principal: Principal
    ) -> str | None:
        """Creates the follow-up occurrence of a completed repeating task.

        Returns:
            The new task's id, or ``None`` when the task does not repeat or the rule
            has run past its ``until`` bound.
        """
        rule = Recurrence(
            frequency=before["recurrence_frequency"],
            interval=int(before["recurrence_interval"]),
            until=before.get("recurrence_until"),
        )
        if not rule.repeats:
            return None

        # A repeating task without a due date anchors on "now", so a daily habit
        # ticked off today is next due tomorrow.
        anchor = before.get("due_at") or datetime.now(tz=UTC)
        target_due = next_occurrence(anchor, rule)
        if target_due is None:
            return None

        next_id = await tasks_repo.create(
            conn,
            list_id=list_id,
            created_by_id=principal.user_id,
            title=before["title"],
            description=before["description"],
            status="todo",
            priority=before["priority"],
            assignee_id=(
                str(before["assignee_id"]) if before.get("assignee_id") is not None else None
            ),
            due_at=target_due,
            due_has_time=bool(before["due_has_time"]),
            starts_at=shift(before.get("due_at"), before.get("starts_at"), target_due),
            estimate_minutes=int(before["estimate_minutes"]),
            recurrence_frequency=rule.frequency,
            recurrence_interval=rule.interval,
            recurrence_until=rule.until,
        )
        # Labels are list-scoped and the occurrence stays in the same list, so they
        # carry over.
        labels = await tasks_repo.labels_for_tasks(conn, [str(before["id"])])
        label_ids = [str(item["id"]) for item in labels.get(str(before["id"]), [])]
        if label_ids:
            await tasks_repo.set_labels(conn, next_id, label_ids)

        await activity_repo.record(
            conn,
            actor_id=principal.user_id,
            action="created",
            target_type="task",
            target_id=next_id,
            target_label=before["title"],
            list_id=list_id,
            task_id=next_id,
            field="recurrence",
            from_value=str(before["id"]),
            to_value=rule.frequency,
        )
        return next_id

    async def _apply_bulk_change(
        self,
        conn: Any,
        which: str,
        request: task_pb2.BulkUpdateTasksRequest,
        task_ids: list[str],
        principal: Principal,
    ) -> int:
        """Dispatches the bulk ``change`` oneof to the matching repository call."""
        if which == "status":
            status = enums.TASK_STATUS.to_db(request.status, field="status")
            return await tasks_repo.bulk_set_status(
                conn, task_ids, status=status, actor_id=principal.user_id
            )
        if which == "priority":
            priority = enums.TASK_PRIORITY.to_db(request.priority, field="priority")
            return await tasks_repo.bulk_set_priority(conn, task_ids, priority)
        if which == "list_id":
            target = validation.uuid_value(request.list_id, field="list_id")
            await permissions.require_write(conn, target, principal)
            return await tasks_repo.bulk_move_to_list(conn, task_ids, target)
        if which == "assignee_id":
            # Each task may live in a different list, so authorize per list.
            assignee = validation.uuid_value(request.assignee_id, field="assignee_id")
            for task_id in task_ids:
                list_id = await tasks_repo.get_list_id(conn, task_id)
                if list_id is not None:
                    await self._resolve_assignee(conn, list_id=list_id, assignee_id=assignee)
            return await tasks_repo.bulk_set_assignee(conn, task_ids, assignee)
        if which == "clear_assignee":
            if not request.clear_assignee:
                raise invalid_argument(
                    Reason.ERROR_REASON_NO_CHANGE_REQUESTED,
                    "clear_assignee must be true to take effect",
                    field="clear_assignee",
                )
            return await tasks_repo.bulk_set_assignee(conn, task_ids, None)
        raise invalid_argument(
            Reason.ERROR_REASON_NO_CHANGE_REQUESTED, f"unsupported change {which}"
        )


def _as_text(value: object) -> str:
    """Renders an activity diff value as text, mapping ``None`` to empty."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _is_descending(direction: int, *, default_descending: bool = True) -> bool:
    """Maps a :class:`SortDirection` to a boolean, with a per-listing default."""
    if direction == 1:  # SORT_DIRECTION_ASC
        return False
    if direction == 2:  # SORT_DIRECTION_DESC
        return True
    return default_descending


def _task_sort_field(value: int) -> str:
    """Maps a :class:`TaskSortField` to a repository sort key."""
    return {
        1: "position",
        2: "created_at",
        3: "updated_at",
        4: "due_at",
        5: "priority",
        6: "title",
    }.get(value, "position")
