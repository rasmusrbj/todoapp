"""Lists, sharing, membership roles, and labels."""

from __future__ import annotations

from typing import Any

from tests.conftest import Client, reason_of


async def make_list(client: Client, **overrides: Any) -> dict[str, Any]:
    """Creates a list and returns it."""
    body: dict[str, Any] = {"name": "Indkøb", "color": "LIST_COLOR_GREEN"}
    body.update(overrides)
    result = await client.call("ListService/CreateList", body)
    assert "list" in result, result
    return result["list"]


async def test_create_list_makes_the_caller_owner(user: Client) -> None:
    todo_list = await make_list(user, description="Ugens indkøb")

    assert todo_list["owner"]["email"] == "owner@example.com"
    assert todo_list["viewerRole"] == "MEMBER_ROLE_OWNER"
    assert todo_list["visibility"] == "LIST_VISIBILITY_PRIVATE"
    assert todo_list["color"] == "LIST_COLOR_GREEN"
    assert todo_list["stats"]["memberCount"] == 1
    # An empty list has nothing outstanding, so it reads as complete.
    assert todo_list["stats"]["completionPercent"] == 100
    assert len(todo_list["members"]) == 1
    assert todo_list["members"][0]["role"] == "MEMBER_ROLE_OWNER"


async def test_create_list_validates_the_name(user: Client) -> None:
    blank = await user.call("ListService/CreateList", {"name": "   "})
    assert reason_of(blank) == "ERROR_REASON_FIELD_REQUIRED"
    too_long = await user.call("ListService/CreateList", {"name": "x" * 121})
    assert reason_of(too_long) == "ERROR_REASON_FIELD_TOO_LONG"


async def test_unknown_enum_value_is_rejected(user: Client) -> None:
    """A number outside the enum must fail loudly rather than store a default."""
    result = await user.call("ListService/CreateList", {"name": "Test", "color": 99})
    assert reason_of(result) == "ERROR_REASON_INVALID_ENUM_VALUE"


async def test_update_list_is_partial(user: Client) -> None:
    todo_list = await make_list(user, description="Oprindelig")

    result = await user.call("ListService/UpdateList", {"id": todo_list["id"], "name": "Storkøb"})
    assert result["list"]["name"] == "Storkøb"
    # An untouched field keeps its value.
    assert result["list"]["description"] == "Oprindelig"
    assert result["list"]["color"] == "LIST_COLOR_GREEN"

    empty = await user.call("ListService/UpdateList", {"id": todo_list["id"]})
    assert reason_of(empty) == "ERROR_REASON_NO_CHANGE_REQUESTED"


async def test_archive_hides_a_list_from_the_default_listing(user: Client) -> None:
    todo_list = await make_list(user)

    archived = await user.call(
        "ListService/SetListArchived", {"id": todo_list["id"], "archived": True}
    )
    assert archived["list"]["archived"] is True
    assert "archivedAt" in archived["list"]

    # proto3 JSON omits an empty repeated field entirely.
    assert (await user.call("ListService/ListLists")).get("lists", []) == []
    with_archived = await user.call("ListService/ListLists", {"includeArchived": True})
    assert len(with_archived["lists"]) == 1

    restored = await user.call(
        "ListService/SetListArchived", {"id": todo_list["id"], "archived": False}
    )
    assert "archived" not in restored["list"]


async def test_list_listing_filters_and_sorts(user: Client) -> None:
    await make_list(user, name="Aarhus")
    await make_list(user, name="Berlin", visibility="LIST_VISIBILITY_PUBLIC")
    await make_list(user, name="København")

    by_name = await user.call(
        "ListService/ListLists",
        {"sortField": "LIST_SORT_FIELD_NAME", "sortDirection": "SORT_DIRECTION_ASC"},
    )
    assert [item["name"] for item in by_name["lists"]] == ["Aarhus", "Berlin", "København"]

    public = await user.call("ListService/ListLists", {"visibilities": ["LIST_VISIBILITY_PUBLIC"]})
    assert [item["name"] for item in public["lists"]] == ["Berlin"]

    searched = await user.call("ListService/ListLists", {"query": "havn"})
    assert [item["name"] for item in searched["lists"]] == ["København"]

    assert by_name["page"]["totalCount"] == 3


async def test_reorder_lists(user: Client) -> None:
    first = await make_list(user, name="En")
    second = await make_list(user, name="To")

    result = await user.call("ListService/ReorderLists", {"listIds": [first["id"], second["id"]]})
    assert [item["name"] for item in result["lists"]] == ["En", "To"]

    flipped = await user.call("ListService/ReorderLists", {"listIds": [second["id"], first["id"]]})
    assert [item["name"] for item in flipped["lists"]] == ["To", "En"]


async def test_delete_list_removes_it(user: Client) -> None:
    todo_list = await make_list(user)
    assert await user.call("ListService/DeleteList", {"id": todo_list["id"]}) == {}
    gone = await user.call("ListService/GetList", {"id": todo_list["id"]})
    assert reason_of(gone) == "ERROR_REASON_LIST_NOT_FOUND"


# --- Sharing and roles -------------------------------------------------------


async def test_another_users_private_list_reads_as_missing(
    user: Client, second_client: Client
) -> None:
    """Not "forbidden" — that would confirm the list exists."""
    todo_list = await make_list(user)
    result = await second_client.call("ListService/GetList", {"id": todo_list["id"]})
    assert result["code"] == "not_found"
    assert reason_of(result) == "ERROR_REASON_LIST_NOT_FOUND"


async def test_public_list_is_readable_by_anyone_signed_in(
    user: Client, second_client: Client
) -> None:
    todo_list = await make_list(user, visibility="LIST_VISIBILITY_PUBLIC")
    result = await second_client.call("ListService/GetList", {"id": todo_list["id"]})
    assert result["list"]["name"] == "Indkøb"
    # Reachable, but with no membership of their own.
    assert "viewerRole" not in result["list"]


async def test_add_member_by_email_and_by_id(user: Client, second_client: Client) -> None:
    todo_list = await make_list(user)

    added = await user.call(
        "ListService/AddMember",
        {"listId": todo_list["id"], "email": "partner@example.com", "role": "MEMBER_ROLE_EDITOR"},
    )
    assert added["member"]["user"]["displayName"] == "Mette Holm"
    assert added["member"]["role"] == "MEMBER_ROLE_EDITOR"
    assert added["member"]["invitedBy"]["email"] == "owner@example.com"

    # Now visible to them, with their own role attached.
    theirs = await second_client.call("ListService/GetList", {"id": todo_list["id"]})
    assert theirs["list"]["viewerRole"] == "MEMBER_ROLE_EDITOR"

    duplicate = await user.call(
        "ListService/AddMember",
        {
            "listId": todo_list["id"],
            "userId": added["member"]["user"]["id"],
            "role": "MEMBER_ROLE_VIEWER",
        },
    )
    assert reason_of(duplicate) == "ERROR_REASON_MEMBER_ALREADY_ADDED"


async def test_add_member_rejects_unknown_person_and_owner_role(user: Client) -> None:
    todo_list = await make_list(user)

    unknown = await user.call(
        "ListService/AddMember",
        {
            "listId": todo_list["id"],
            "email": "findes-ikke@example.com",
            "role": "MEMBER_ROLE_VIEWER",
        },
    )
    assert reason_of(unknown) == "ERROR_REASON_USER_NOT_FOUND"

    as_owner = await user.call(
        "ListService/AddMember",
        {"listId": todo_list["id"], "email": "partner@example.com", "role": "MEMBER_ROLE_OWNER"},
    )
    assert as_owner["code"] == "invalid_argument"


async def test_viewer_cannot_write_and_editor_can(user: Client, second_client: Client) -> None:
    todo_list = await make_list(user)
    await user.call(
        "ListService/AddMember",
        {"listId": todo_list["id"], "email": "partner@example.com", "role": "MEMBER_ROLE_VIEWER"},
    )

    denied = await second_client.call(
        "TaskService/CreateTask", {"listId": todo_list["id"], "title": "Prøver"}
    )
    assert denied["code"] == "permission_denied"

    await user.call(
        "ListService/UpdateMemberRole",
        {
            "listId": todo_list["id"],
            "userId": (await second_client.call("UserService/GetCurrentUser"))["user"]["id"],
            "role": "MEMBER_ROLE_EDITOR",
        },
    )
    allowed = await second_client.call(
        "TaskService/CreateTask", {"listId": todo_list["id"], "title": "Nu virker det"}
    )
    assert allowed["task"]["title"] == "Nu virker det"


async def test_commenter_may_comment_but_not_edit(user: Client, second_client: Client) -> None:
    todo_list = await make_list(user)
    task = (
        await user.call(
            "TaskService/CreateTask", {"listId": todo_list["id"], "title": "Til kommentar"}
        )
    )["task"]
    await user.call(
        "ListService/AddMember",
        {
            "listId": todo_list["id"],
            "email": "partner@example.com",
            "role": "MEMBER_ROLE_COMMENTER",
        },
    )

    commented = await second_client.call(
        "TaskService/CreateComment", {"taskId": task["id"], "body": "Jeg tager den"}
    )
    assert commented["comment"]["author"]["displayName"] == "Mette Holm"

    edit = await second_client.call("TaskService/UpdateTask", {"id": task["id"], "title": "Kapret"})
    assert edit["code"] == "permission_denied"


async def test_viewer_cannot_comment(user: Client, second_client: Client) -> None:
    todo_list = await make_list(user)
    task = (
        await user.call(
            "TaskService/CreateTask", {"listId": todo_list["id"], "title": "Kun læsning"}
        )
    )["task"]
    await user.call(
        "ListService/AddMember",
        {"listId": todo_list["id"], "email": "partner@example.com", "role": "MEMBER_ROLE_VIEWER"},
    )
    result = await second_client.call(
        "TaskService/CreateComment", {"taskId": task["id"], "body": "Må jeg?"}
    )
    assert result["code"] == "permission_denied"


async def test_only_the_owner_may_share_or_change_visibility(
    user: Client, second_client: Client
) -> None:
    todo_list = await make_list(user)
    await user.call(
        "ListService/AddMember",
        {"listId": todo_list["id"], "email": "partner@example.com", "role": "MEMBER_ROLE_EDITOR"},
    )

    # An editor may rename …
    assert "list" in await second_client.call(
        "ListService/UpdateList", {"id": todo_list["id"], "name": "Omdøbt af editor"}
    )
    # … but not change who can reach it.
    visibility = await second_client.call(
        "ListService/UpdateList",
        {"id": todo_list["id"], "visibility": "LIST_VISIBILITY_PUBLIC"},
    )
    assert reason_of(visibility) == "ERROR_REASON_OWNER_REQUIRED"

    share = await second_client.call(
        "ListService/AddMember",
        {"listId": todo_list["id"], "email": "owner@example.com", "role": "MEMBER_ROLE_VIEWER"},
    )
    assert reason_of(share) == "ERROR_REASON_OWNER_REQUIRED"

    delete = await second_client.call("ListService/DeleteList", {"id": todo_list["id"]})
    assert reason_of(delete) == "ERROR_REASON_OWNER_REQUIRED"


async def test_owner_cannot_be_removed_or_demoted(user: Client) -> None:
    todo_list = await make_list(user)
    me = (await user.call("UserService/GetCurrentUser"))["user"]["id"]

    removed = await user.call("ListService/RemoveMember", {"listId": todo_list["id"], "userId": me})
    assert reason_of(removed) == "ERROR_REASON_CANNOT_REMOVE_OWNER"

    demoted = await user.call(
        "ListService/UpdateMemberRole",
        {"listId": todo_list["id"], "userId": me, "role": "MEMBER_ROLE_VIEWER"},
    )
    assert reason_of(demoted) == "ERROR_REASON_CANNOT_DEMOTE_SELF"


async def test_a_member_may_remove_themselves(user: Client, second_client: Client) -> None:
    todo_list = await make_list(user)
    them = (await second_client.call("UserService/GetCurrentUser"))["user"]["id"]
    await user.call(
        "ListService/AddMember",
        {"listId": todo_list["id"], "email": "partner@example.com", "role": "MEMBER_ROLE_EDITOR"},
    )

    assert (
        await second_client.call(
            "ListService/RemoveMember", {"listId": todo_list["id"], "userId": them}
        )
        == {}
    )
    assert (await second_client.call("ListService/GetList", {"id": todo_list["id"]}))[
        "code"
    ] == "not_found"


async def test_losing_write_access_clears_open_assignments(
    user: Client, second_client: Client
) -> None:
    """Work assigned to someone who can no longer edit the list is unassigned."""
    todo_list = await make_list(user)
    them = (await second_client.call("UserService/GetCurrentUser"))["user"]["id"]
    await user.call(
        "ListService/AddMember",
        {"listId": todo_list["id"], "email": "partner@example.com", "role": "MEMBER_ROLE_EDITOR"},
    )
    task = (
        await user.call(
            "TaskService/CreateTask",
            {"listId": todo_list["id"], "title": "Deres opgave", "assigneeId": them},
        )
    )["task"]
    assert task["assignee"]["id"] == them

    await user.call(
        "ListService/UpdateMemberRole",
        {"listId": todo_list["id"], "userId": them, "role": "MEMBER_ROLE_VIEWER"},
    )
    after = await user.call("TaskService/GetTask", {"id": task["id"]})
    assert "assignee" not in after["task"]


async def test_unverified_account_cannot_share(client: Client) -> None:
    """Sharing reaches someone else's inbox, so it needs a confirmed address."""
    await client.register()
    todo_list = await make_list(client)
    result = await client.call(
        "ListService/AddMember",
        {"listId": todo_list["id"], "email": "partner@example.com", "role": "MEMBER_ROLE_VIEWER"},
    )
    assert reason_of(result) == "ERROR_REASON_EMAIL_NOT_VERIFIED"


# --- Labels ------------------------------------------------------------------


async def test_label_crud(user: Client) -> None:
    todo_list = await make_list(user)

    created = await user.call(
        "ListService/CreateLabel",
        {"listId": todo_list["id"], "name": "Haster", "color": "LIST_COLOR_RED"},
    )
    label = created["label"]
    assert label["color"] == "LIST_COLOR_RED"
    assert "taskCount" not in label  # Zero is omitted by proto3 JSON.

    duplicate = await user.call(
        "ListService/CreateLabel", {"listId": todo_list["id"], "name": "haster"}
    )
    assert reason_of(duplicate) == "ERROR_REASON_LABEL_NAME_TAKEN"

    renamed = await user.call("ListService/UpdateLabel", {"id": label["id"], "name": "Vigtigt"})
    assert renamed["label"]["name"] == "Vigtigt"
    assert renamed["label"]["color"] == "LIST_COLOR_RED"

    listed = await user.call("ListService/ListLabels", {"listId": todo_list["id"]})
    assert [item["name"] for item in listed["labels"]] == ["Vigtigt"]

    assert await user.call("ListService/DeleteLabel", {"id": label["id"]}) == {}
    empty = await user.call("ListService/ListLabels", {"listId": todo_list["id"]})
    assert empty.get("labels", []) == []


async def test_label_counts_its_tasks(user: Client) -> None:
    todo_list = await make_list(user)
    label = (
        await user.call("ListService/CreateLabel", {"listId": todo_list["id"], "name": "Haster"})
    )["label"]
    for title in ("En", "To"):
        await user.call(
            "TaskService/CreateTask",
            {"listId": todo_list["id"], "title": title, "labelIds": [label["id"]]},
        )
    listed = await user.call("ListService/ListLabels", {"listId": todo_list["id"]})
    assert listed["labels"][0]["taskCount"] == 2


async def test_deleting_a_label_detaches_it_from_tasks(user: Client) -> None:
    todo_list = await make_list(user)
    label = (
        await user.call("ListService/CreateLabel", {"listId": todo_list["id"], "name": "Haster"})
    )["label"]
    task = (
        await user.call(
            "TaskService/CreateTask",
            {"listId": todo_list["id"], "title": "Mærket", "labelIds": [label["id"]]},
        )
    )["task"]
    assert len(task["labels"]) == 1

    await user.call("ListService/DeleteLabel", {"id": label["id"]})
    after = await user.call("TaskService/GetTask", {"id": task["id"]})
    assert after["task"].get("labels", []) == []
