"""Tasks, subtasks, comments, filters, and the activity feed."""

from __future__ import annotations

from typing import Any

from tests.conftest import Client, reason_of
from tests.test_lists import make_list


async def make_task(client: Client, list_id: str, **overrides: Any) -> dict[str, Any]:
    """Creates a task on ``list_id`` and returns it."""
    body: dict[str, Any] = {"listId": list_id, "title": "Køb mælk"}
    body.update(overrides)
    result = await client.call("TaskService/CreateTask", body)
    assert "task" in result, result
    return result["task"]


async def test_create_task_is_rich_in_context(user: Client) -> None:
    todo_list = await make_list(user)
    label = (
        await user.call("ListService/CreateLabel", {"listId": todo_list["id"], "name": "Haster"})
    )["label"]

    task = await make_task(
        user,
        todo_list["id"],
        description="Letmælk",
        priority="TASK_PRIORITY_HIGH",
        labelIds=[label["id"]],
        dueAt="2026-08-20T10:00:00Z",
        dueHasTime=True,
        estimateMinutes=15,
        subtaskTitles=["Tjek køleskabet", "Find kvittering"],
    )

    assert task["status"] == "TASK_STATUS_TODO"
    assert task["priority"] == "TASK_PRIORITY_HIGH"
    assert task["estimateMinutes"] == 15
    assert task["dueHasTime"] is True
    assert task["list"]["name"] == "Indkøb"
    assert task["list"]["color"] == "LIST_COLOR_GREEN"
    assert task["createdBy"]["email"] == "owner@example.com"
    assert [item["name"] for item in task["labels"]] == ["Haster"]
    assert [item["title"] for item in task["subtasks"]] == [
        "Tjek køleskabet",
        "Find kvittering",
    ]
    assert task["subtaskCount"] == 2
    # Absent rather than an empty object, so "unassigned" is unambiguous.
    assert "assignee" not in task
    assert "completedAt" not in task


async def test_create_task_validation(user: Client) -> None:
    todo_list = await make_list(user)

    assert (
        reason_of(
            await user.call("TaskService/CreateTask", {"listId": todo_list["id"], "title": "  "})
        )
        == "ERROR_REASON_FIELD_REQUIRED"
    )

    assert (
        reason_of(await user.call("TaskService/CreateTask", {"listId": "not-a-uuid", "title": "x"}))
        == "ERROR_REASON_VALIDATION_FAILED"
    )

    assert (
        reason_of(
            await user.call(
                "TaskService/CreateTask",
                {"listId": todo_list["id"], "title": "x", "estimateMinutes": 999_999},
            )
        )
        == "ERROR_REASON_VALIDATION_FAILED"
    )

    assert (
        reason_of(
            await user.call(
                "TaskService/CreateTask",
                {"listId": todo_list["id"], "title": "x", "dueHasTime": True},
            )
        )
        == "ERROR_REASON_VALIDATION_FAILED"
    )

    assert (
        reason_of(
            await user.call(
                "TaskService/CreateTask",
                {
                    "listId": todo_list["id"],
                    "title": "x",
                    "dueAt": "2026-08-01T00:00:00Z",
                    "startsAt": "2026-09-01T00:00:00Z",
                },
            )
        )
        == "ERROR_REASON_INVALID_DATE_RANGE"
    )


async def test_labels_are_scoped_to_their_list(user: Client) -> None:
    first = await make_list(user, name="En")
    second = await make_list(user, name="To")
    label = (await user.call("ListService/CreateLabel", {"listId": first["id"], "name": "Haster"}))[
        "label"
    ]

    result = await user.call(
        "TaskService/CreateTask",
        {"listId": second["id"], "title": "Forkert mærke", "labelIds": [label["id"]]},
    )
    assert reason_of(result) == "ERROR_REASON_LABEL_NOT_ON_LIST"


async def test_update_task_is_partial_and_dates_need_an_explicit_clear(user: Client) -> None:
    todo_list = await make_list(user)
    task = await make_task(
        user, todo_list["id"], description="Original", dueAt="2026-08-20T10:00:00Z"
    )

    renamed = await user.call(
        "TaskService/UpdateTask", {"id": task["id"], "title": "Køb havremælk"}
    )
    assert renamed["task"]["title"] == "Køb havremælk"
    assert renamed["task"]["description"] == "Original"
    # An untouched due date survives.
    assert renamed["task"]["dueAt"].startswith("2026-08-20")

    cleared = await user.call("TaskService/UpdateTask", {"id": task["id"], "clearDueAt": True})
    assert "dueAt" not in cleared["task"]

    assert reason_of(await user.call("TaskService/UpdateTask", {"id": task["id"]})) == (
        "ERROR_REASON_NO_CHANGE_REQUESTED"
    )


async def test_status_transitions_stamp_and_clear_completion(user: Client) -> None:
    todo_list = await make_list(user)
    task = await make_task(user, todo_list["id"])

    done = await user.call(
        "TaskService/SetTaskStatus", {"id": task["id"], "status": "TASK_STATUS_DONE"}
    )
    assert done["task"]["status"] == "TASK_STATUS_DONE"
    assert "completedAt" in done["task"]
    assert done["task"]["completedBy"]["email"] == "owner@example.com"
    assert "nextOccurrence" not in done

    reopened = await user.call(
        "TaskService/SetTaskStatus", {"id": task["id"], "status": "TASK_STATUS_IN_PROGRESS"}
    )
    assert "completedAt" not in reopened["task"]
    assert "completedBy" not in reopened["task"]


async def test_cancelling_also_counts_as_finished(user: Client) -> None:
    """The schema's CHECK ties completed_at to both terminal statuses."""
    todo_list = await make_list(user)
    task = await make_task(user, todo_list["id"])
    cancelled = await user.call(
        "TaskService/SetTaskStatus", {"id": task["id"], "status": "TASK_STATUS_CANCELLED"}
    )
    assert "completedAt" in cancelled["task"]


async def test_completing_a_recurring_task_spawns_the_next_occurrence(user: Client) -> None:
    todo_list = await make_list(user)
    label = (
        await user.call("ListService/CreateLabel", {"listId": todo_list["id"], "name": "Fast"})
    )["label"]
    task = await make_task(
        user,
        todo_list["id"],
        title="Betal husleje",
        dueAt="2026-08-31T00:00:00Z",
        labelIds=[label["id"]],
        recurrence={"frequency": "RECURRENCE_FREQUENCY_MONTHLY", "interval": 1},
    )

    done = await user.call(
        "TaskService/SetTaskStatus", {"id": task["id"], "status": "TASK_STATUS_DONE"}
    )
    following = done["nextOccurrence"]
    assert following["title"] == "Betal husleje"
    assert following["status"] == "TASK_STATUS_TODO"
    # 31 August + 1 month clamps to 30 September.
    assert following["dueAt"].startswith("2026-09-30")
    assert following["recurrence"]["frequency"] == "RECURRENCE_FREQUENCY_MONTHLY"
    # Labels are list-scoped and the occurrence stays put, so they carry over.
    assert [item["name"] for item in following["labels"]] == ["Fast"]
    assert following["id"] != task["id"]


async def test_recompleting_does_not_spawn_a_second_occurrence(user: Client) -> None:
    todo_list = await make_list(user)
    task = await make_task(
        user,
        todo_list["id"],
        recurrence={"frequency": "RECURRENCE_FREQUENCY_DAILY", "interval": 1},
    )
    first = await user.call(
        "TaskService/SetTaskStatus", {"id": task["id"], "status": "TASK_STATUS_DONE"}
    )
    assert "nextOccurrence" in first
    again = await user.call(
        "TaskService/SetTaskStatus", {"id": task["id"], "status": "TASK_STATUS_DONE"}
    )
    assert "nextOccurrence" not in again


async def test_cancelling_a_recurring_task_ends_the_series(user: Client) -> None:
    todo_list = await make_list(user)
    task = await make_task(
        user,
        todo_list["id"],
        recurrence={"frequency": "RECURRENCE_FREQUENCY_WEEKLY", "interval": 1},
    )
    result = await user.call(
        "TaskService/SetTaskStatus", {"id": task["id"], "status": "TASK_STATUS_CANCELLED"}
    )
    assert "nextOccurrence" not in result


async def test_recurrence_past_its_until_bound_stops(user: Client) -> None:
    todo_list = await make_list(user)
    task = await make_task(
        user,
        todo_list["id"],
        dueAt="2026-08-31T00:00:00Z",
        recurrence={
            "frequency": "RECURRENCE_FREQUENCY_MONTHLY",
            "interval": 1,
            "until": "2026-09-01T00:00:00Z",
        },
    )
    result = await user.call(
        "TaskService/SetTaskStatus", {"id": task["id"], "status": "TASK_STATUS_DONE"}
    )
    assert "nextOccurrence" not in result


async def test_assignment_requires_write_access(user: Client, second_client: Client) -> None:
    todo_list = await make_list(user)
    task = await make_task(user, todo_list["id"])
    them = (await second_client.call("UserService/GetCurrentUser"))["user"]["id"]

    # Not a member yet.
    denied = await user.call("TaskService/AssignTask", {"id": task["id"], "assigneeId": them})
    assert reason_of(denied) == "ERROR_REASON_ASSIGNEE_NOT_A_MEMBER"

    await user.call(
        "ListService/AddMember",
        {"listId": todo_list["id"], "email": "partner@example.com", "role": "MEMBER_ROLE_EDITOR"},
    )
    assigned = await user.call("TaskService/AssignTask", {"id": task["id"], "assigneeId": them})
    assert assigned["task"]["assignee"]["displayName"] == "Mette Holm"

    cleared = await user.call("TaskService/AssignTask", {"id": task["id"]})
    assert "assignee" not in cleared["task"]


async def test_a_viewer_cannot_be_assigned(user: Client, second_client: Client) -> None:
    todo_list = await make_list(user)
    task = await make_task(user, todo_list["id"])
    them = (await second_client.call("UserService/GetCurrentUser"))["user"]["id"]
    await user.call(
        "ListService/AddMember",
        {"listId": todo_list["id"], "email": "partner@example.com", "role": "MEMBER_ROLE_VIEWER"},
    )
    result = await user.call("TaskService/AssignTask", {"id": task["id"], "assigneeId": them})
    assert reason_of(result) == "ERROR_REASON_ASSIGNEE_NOT_A_MEMBER"


async def test_move_task_between_lists_drops_foreign_labels(user: Client) -> None:
    source = await make_list(user, name="Kilde")
    target = await make_list(user, name="Mål")
    label = (
        await user.call("ListService/CreateLabel", {"listId": source["id"], "name": "Haster"})
    )["label"]
    task = await make_task(user, source["id"], labelIds=[label["id"]])
    assert len(task["labels"]) == 1

    moved = await user.call(
        "TaskService/MoveTask", {"id": task["id"], "listId": target["id"], "position": 0}
    )
    assert moved["task"]["list"]["name"] == "Mål"
    assert moved["task"].get("labels", []) == []


async def test_move_task_requires_write_on_the_target(user: Client, second_client: Client) -> None:
    mine = await make_list(user, name="Min")
    theirs = await make_list(second_client, name="Deres")
    task = await make_task(user, mine["id"])
    result = await user.call(
        "TaskService/MoveTask", {"id": task["id"], "listId": theirs["id"], "position": 0}
    )
    assert result["code"] == "not_found"


async def test_move_reorders_within_a_list(user: Client) -> None:
    todo_list = await make_list(user)
    # Each new task goes to the top, so creating A then B leaves [B, A].
    first = await make_task(user, todo_list["id"], title="A")
    second = await make_task(user, todo_list["id"], title="B")

    listing = await user.call(
        "TaskService/ListTasks",
        {
            "listIds": [todo_list["id"]],
            "sortField": "TASK_SORT_FIELD_POSITION",
            "sortDirection": "SORT_DIRECTION_ASC",
        },
    )
    assert [t["title"] for t in listing["tasks"]] == ["B", "A"]

    await user.call("TaskService/MoveTask", {"id": first["id"], "position": 0})
    reordered = await user.call(
        "TaskService/ListTasks",
        {
            "listIds": [todo_list["id"]],
            "sortField": "TASK_SORT_FIELD_POSITION",
            "sortDirection": "SORT_DIRECTION_ASC",
        },
    )
    assert [t["title"] for t in reordered["tasks"]] == ["A", "B"]
    assert second["id"]  # keeps the linter honest about the unused binding


# --- Filtering, sorting, pagination -----------------------------------------


async def test_filters_and_status_counts(user: Client) -> None:
    todo_list = await make_list(user)
    label = (
        await user.call("ListService/CreateLabel", {"listId": todo_list["id"], "name": "Haster"})
    )["label"]

    await make_task(user, todo_list["id"], title="Åben", priority="TASK_PRIORITY_LOW")
    tagged = await make_task(
        user,
        todo_list["id"],
        title="Mærket",
        priority="TASK_PRIORITY_URGENT",
        labelIds=[label["id"]],
    )
    finished = await make_task(user, todo_list["id"], title="Færdig")
    await user.call(
        "TaskService/SetTaskStatus", {"id": finished["id"], "status": "TASK_STATUS_DONE"}
    )

    open_only = await user.call("TaskService/ListTasks", {"statuses": ["TASK_STATUS_TODO"]})
    assert {t["title"] for t in open_only["tasks"]} == {"Åben", "Mærket"}
    assert open_only["statusCounts"] == {"todo": 2}

    everything = await user.call("TaskService/ListTasks")
    assert everything["statusCounts"] == {"todo": 2, "done": 1}
    assert everything["page"]["totalCount"] == 3

    by_label = await user.call("TaskService/ListTasks", {"labelIds": [label["id"]]})
    assert [t["id"] for t in by_label["tasks"]] == [tagged["id"]]

    by_priority = await user.call("TaskService/ListTasks", {"priorities": ["TASK_PRIORITY_URGENT"]})
    assert [t["title"] for t in by_priority["tasks"]] == ["Mærket"]

    searched = await user.call("TaskService/ListTasks", {"query": "ærke"})
    assert [t["title"] for t in searched["tasks"]] == ["Mærket"]


async def test_sort_by_priority_descending(user: Client) -> None:
    """Relies on the PostgreSQL enum's declaration order, not on a lookup table."""
    todo_list = await make_list(user)
    await make_task(user, todo_list["id"], title="Lav", priority="TASK_PRIORITY_LOW")
    await make_task(user, todo_list["id"], title="Kritisk", priority="TASK_PRIORITY_URGENT")
    await make_task(user, todo_list["id"], title="Mellem", priority="TASK_PRIORITY_MEDIUM")

    result = await user.call(
        "TaskService/ListTasks",
        {"sortField": "TASK_SORT_FIELD_PRIORITY", "sortDirection": "SORT_DIRECTION_DESC"},
    )
    assert [t["title"] for t in result["tasks"]] == ["Kritisk", "Mellem", "Lav"]


async def test_overdue_and_due_range_filters(user: Client) -> None:
    todo_list = await make_list(user)
    await make_task(user, todo_list["id"], title="Forsinket", dueAt="2020-01-01T00:00:00Z")
    await make_task(user, todo_list["id"], title="Fremtidig", dueAt="2099-01-01T00:00:00Z")

    overdue = await user.call("TaskService/ListTasks", {"overdueOnly": True})
    assert [t["title"] for t in overdue["tasks"]] == ["Forsinket"]
    assert overdue["tasks"][0]["overdue"] is True

    ranged = await user.call(
        "TaskService/ListTasks",
        {"dueAfter": "2098-01-01T00:00:00Z", "dueBefore": "2100-01-01T00:00:00Z"},
    )
    assert [t["title"] for t in ranged["tasks"]] == ["Fremtidig"]

    assert (
        reason_of(
            await user.call(
                "TaskService/ListTasks",
                {"dueAfter": "2100-01-01T00:00:00Z", "dueBefore": "2098-01-01T00:00:00Z"},
            )
        )
        == "ERROR_REASON_INVALID_DATE_RANGE"
    )


async def test_pagination_walks_the_whole_set(user: Client) -> None:
    todo_list = await make_list(user)
    for index in range(5):
        await make_task(user, todo_list["id"], title=f"Opgave {index}")

    seen: list[str] = []
    cursor = ""
    for _ in range(5):
        page = await user.call("TaskService/ListTasks", {"page": {"limit": 2, "cursor": cursor}})
        seen += [t["title"] for t in page["tasks"]]
        if not page["page"].get("hasMore"):
            break
        cursor = page["page"]["nextCursor"]

    assert len(seen) == 5
    assert len(set(seen)) == 5


async def test_page_limit_is_clamped_not_rejected(user: Client) -> None:
    todo_list = await make_list(user)
    await make_task(user, todo_list["id"])
    result = await user.call("TaskService/ListTasks", {"page": {"limit": 5000}})
    assert "tasks" in result


async def test_malformed_cursor_is_rejected(user: Client) -> None:
    result = await user.call("TaskService/ListTasks", {"page": {"cursor": "!!not-a-cursor"}})
    assert reason_of(result) == "ERROR_REASON_VALIDATION_FAILED"


async def test_listing_never_leaks_another_users_tasks(user: Client, second_client: Client) -> None:
    mine = await make_list(user, name="Min")
    await make_task(user, mine["id"], title="Min opgave")
    theirs = await make_list(second_client, name="Deres")
    await make_task(second_client, theirs["id"], title="Deres opgave")

    result = await user.call("TaskService/ListTasks")
    assert [t["title"] for t in result["tasks"]] == ["Min opgave"]


# --- Bulk --------------------------------------------------------------------


async def test_bulk_update_applies_one_change(user: Client) -> None:
    todo_list = await make_list(user)
    first = await make_task(user, todo_list["id"], title="En")
    second = await make_task(user, todo_list["id"], title="To")

    result = await user.call(
        "TaskService/BulkUpdateTasks",
        {"taskIds": [first["id"], second["id"]], "priority": "TASK_PRIORITY_URGENT"},
    )
    assert result["updatedCount"] == 2
    assert all(t["priority"] == "TASK_PRIORITY_URGENT" for t in result["tasks"])

    done = await user.call(
        "TaskService/BulkUpdateTasks",
        {"taskIds": [first["id"], second["id"]], "status": "TASK_STATUS_DONE"},
    )
    assert all("completedAt" in t for t in done["tasks"])


async def test_bulk_update_skips_tasks_the_caller_cannot_write(
    user: Client, second_client: Client
) -> None:
    mine = await make_list(user, name="Min")
    theirs = await make_list(second_client, name="Deres")
    ours = await make_task(user, mine["id"], title="Min")
    not_ours = await make_task(second_client, theirs["id"], title="Deres")

    result = await user.call(
        "TaskService/BulkUpdateTasks",
        {"taskIds": [ours["id"], not_ours["id"]], "priority": "TASK_PRIORITY_HIGH"},
    )
    assert result["updatedCount"] == 1
    assert [t["title"] for t in result["tasks"]] == ["Min"]

    # And the other person's task is untouched.
    untouched = await second_client.call("TaskService/GetTask", {"id": not_ours["id"]})
    assert "priority" not in untouched["task"] or (
        untouched["task"]["priority"] == "TASK_PRIORITY_NONE"
    )


async def test_bulk_update_requires_a_change(user: Client) -> None:
    todo_list = await make_list(user)
    task = await make_task(user, todo_list["id"])
    assert (
        reason_of(await user.call("TaskService/BulkUpdateTasks", {"taskIds": [task["id"]]}))
        == "ERROR_REASON_NO_CHANGE_REQUESTED"
    )
    assert (
        reason_of(await user.call("TaskService/BulkUpdateTasks", {"taskIds": []}))
        == "ERROR_REASON_FIELD_REQUIRED"
    )


# --- Subtasks and comments ---------------------------------------------------


async def test_subtask_lifecycle(user: Client) -> None:
    todo_list = await make_list(user)
    task = await make_task(user, todo_list["id"])

    subtask = (
        await user.call(
            "TaskService/CreateSubtask", {"taskId": task["id"], "title": "Tag pose med"}
        )
    )["subtask"]
    assert "completed" not in subtask

    ticked = await user.call("TaskService/UpdateSubtask", {"id": subtask["id"], "completed": True})
    assert ticked["subtask"]["completed"] is True
    assert "completedAt" in ticked["subtask"]

    counted = await user.call("TaskService/GetTask", {"id": task["id"]})
    assert counted["task"]["subtaskCount"] == 1
    assert counted["task"]["completedSubtaskCount"] == 1

    unticked = await user.call(
        "TaskService/UpdateSubtask", {"id": subtask["id"], "completed": False}
    )
    assert "completedAt" not in unticked["subtask"]

    assert await user.call("TaskService/DeleteSubtask", {"id": subtask["id"]}) == {}
    assert (
        reason_of(
            await user.call("TaskService/UpdateSubtask", {"id": subtask["id"], "title": "Væk"})
        )
        == "ERROR_REASON_SUBTASK_NOT_FOUND"
    )


async def test_comment_lifecycle_and_authorship(user: Client, second_client: Client) -> None:
    todo_list = await make_list(user)
    task = await make_task(user, todo_list["id"])
    await user.call(
        "ListService/AddMember",
        {"listId": todo_list["id"], "email": "partner@example.com", "role": "MEMBER_ROLE_EDITOR"},
    )

    theirs = (
        await second_client.call(
            "TaskService/CreateComment", {"taskId": task["id"], "body": "Jeg tager den"}
        )
    )["comment"]
    assert theirs["author"]["displayName"] == "Mette Holm"
    assert "edited" not in theirs

    # An editor may not rewrite someone else's words.
    hijack = await user.call(
        "TaskService/UpdateComment", {"id": theirs["id"], "body": "Nej, jeg tager den"}
    )
    assert hijack["code"] == "permission_denied"

    edited = await second_client.call(
        "TaskService/UpdateComment", {"id": theirs["id"], "body": "Jeg tager den i morgen"}
    )
    assert edited["comment"]["edited"] is True

    listing = await user.call("TaskService/ListComments", {"taskId": task["id"]})
    assert listing["page"]["totalCount"] == 1
    assert task["id"]

    # The list owner may moderate.
    assert await user.call("TaskService/DeleteComment", {"id": theirs["id"]}) == {}


async def test_comment_body_is_required(user: Client) -> None:
    todo_list = await make_list(user)
    task = await make_task(user, todo_list["id"])
    assert (
        reason_of(
            await user.call("TaskService/CreateComment", {"taskId": task["id"], "body": "   "})
        )
        == "ERROR_REASON_FIELD_REQUIRED"
    )


async def test_deleting_a_task_takes_its_children(user: Client) -> None:
    todo_list = await make_list(user)
    task = await make_task(user, todo_list["id"], subtaskTitles=["En"])
    comment = (
        await user.call("TaskService/CreateComment", {"taskId": task["id"], "body": "Note"})
    )["comment"]

    assert await user.call("TaskService/DeleteTask", {"id": task["id"]}) == {}
    assert reason_of(await user.call("TaskService/GetTask", {"id": task["id"]})) == (
        "ERROR_REASON_TASK_NOT_FOUND"
    )
    assert (
        reason_of(
            await user.call(
                "TaskService/UpdateComment", {"id": comment["id"], "body": "Stadig her?"}
            )
        )
        == "ERROR_REASON_COMMENT_NOT_FOUND"
    )


# --- Activity ----------------------------------------------------------------


async def test_activity_records_what_happened(user: Client) -> None:
    todo_list = await make_list(user)
    task = await make_task(user, todo_list["id"], title="Skrevet ned")
    await user.call("TaskService/UpdateTask", {"id": task["id"], "title": "Omdøbt"})
    await user.call("TaskService/SetTaskStatus", {"id": task["id"], "status": "TASK_STATUS_DONE"})

    feed = await user.call("TaskService/ListActivity", {"listId": todo_list["id"]})
    actions = [entry["action"] for entry in feed["activities"]]
    assert "ACTIVITY_ACTION_STATUS_CHANGED" in actions
    assert "ACTIVITY_ACTION_UPDATED" in actions
    assert "ACTIVITY_ACTION_CREATED" in actions
    assert all(entry["actor"]["email"] == "owner@example.com" for entry in feed["activities"])

    status_entry = next(
        entry for entry in feed["activities"] if entry["action"] == "ACTIVITY_ACTION_STATUS_CHANGED"
    )
    # Values are raw enum labels — the client localizes them.
    assert status_entry["change"] == {"field": "status", "fromValue": "todo", "toValue": "done"}
    assert status_entry["targetType"] == "ACTIVITY_TARGET_TYPE_TASK"


async def test_activity_survives_deleting_its_target(user: Client) -> None:
    """The label is denormalised, so the feed still reads correctly afterwards."""
    todo_list = await make_list(user)
    task = await make_task(user, todo_list["id"], title="Bliver slettet")
    await user.call("TaskService/DeleteTask", {"id": task["id"]})

    feed = await user.call("TaskService/ListActivity", {"listId": todo_list["id"]})
    deleted = next(
        entry for entry in feed["activities"] if entry["action"] == "ACTIVITY_ACTION_DELETED"
    )
    assert deleted["targetLabel"] == "Bliver slettet"


async def test_activity_is_scoped_to_lists_the_caller_can_read(
    user: Client, second_client: Client
) -> None:
    theirs = await make_list(second_client, name="Deres")
    await make_task(second_client, theirs["id"], title="Deres opgave")

    result = await user.call("TaskService/ListActivity")
    assert result.get("activities", []) == []

    denied = await user.call("TaskService/ListActivity", {"listId": theirs["id"]})
    assert denied["code"] == "not_found"


async def test_activity_can_be_filtered_by_action(user: Client) -> None:
    todo_list = await make_list(user)
    task = await make_task(user, todo_list["id"])
    await user.call("TaskService/SetTaskStatus", {"id": task["id"], "status": "TASK_STATUS_DONE"})

    result = await user.call(
        "TaskService/ListActivity", {"actions": ["ACTIVITY_ACTION_STATUS_CHANGED"]}
    )
    assert [entry["action"] for entry in result["activities"]] == ["ACTIVITY_ACTION_STATUS_CHANGED"]
