"""``todoapp tasks …`` — tasks, subtasks, comments, and the activity feed."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from google.protobuf.timestamp_pb2 import Timestamp

from todo.v1 import common_pb2, task_pb2, user_pb2
from todoapp.cli import args as enum_args
from todoapp.cli import display, lookup, output
from todoapp.cli.client import Api, CliError, resolve_id

# Words accepted anywhere a date is: friendlier than an ISO string for the common
# cases, while still accepting an exact timestamp when one is needed.
_DATE_WORDS: Final = ("today", "tomorrow", "yesterday", "next-week", "monday", "none")


def register(subparsers: Any) -> None:
    """Adds the ``tasks`` command group."""
    parser = subparsers.add_parser(
        "tasks",
        aliases=["task"],
        help="create, read, update, and complete tasks",
        description="Tasks, their checklists, and their comments.",
    )
    commands = parser.add_subparsers(
        dest="tasks_command",
        metavar="<command>",
        required=True,
        parser_class=enum_args.LeafParser,
    )

    ls = commands.add_parser("list", aliases=["ls"], help="list tasks you can see")
    ls.add_argument("--list", "-l", action="append", dest="lists", help="restrict to a list")
    ls.add_argument("--query", "-q", default="", help="search title and description")
    ls.add_argument(
        "--status",
        "-s",
        action="append",
        choices=enum_args.TASK_STATUS.choices,
        help="repeatable; matches any of the given statuses",
    )
    ls.add_argument(
        "--priority",
        "-p",
        action="append",
        choices=enum_args.TASK_PRIORITY.choices,
        help="repeatable",
    )
    ls.add_argument("--label", action="append", help="repeatable; label id or prefix")
    ls.add_argument("--assignee", "-a", action="append", help="repeatable; user id or prefix")
    ls.add_argument("--mine", action="store_true", help="only tasks assigned to you")
    ls.add_argument("--unassigned", action="store_true", help="only tasks with no assignee")
    ls.add_argument("--overdue", action="store_true", help="only tasks past their due date")
    ls.add_argument("--open", action="store_true", help="shorthand for unfinished statuses")
    ls.add_argument("--due-after", help=f"date, or one of {'/'.join(_DATE_WORDS)}")
    ls.add_argument("--due-before", help="date, as above")
    ls.add_argument("--sort", choices=enum_args.TASK_SORT.choices, default="position")
    ls.add_argument("--desc", action="store_true", help="reverse the sort")
    ls.add_argument("--limit", type=int, default=25, help="page size (max 100)")
    ls.add_argument("--cursor", default="", help="cursor from a previous page")
    ls.set_defaults(handler=_list)

    get = commands.add_parser("get", help="show one task in full, with its comments")
    get.add_argument("id", help="task id, or a unique prefix of one")
    get.set_defaults(handler=_get)

    create = commands.add_parser("create", aliases=["add"], help="create a task")
    create.add_argument("title", help="what needs doing")
    create.add_argument("--list", "-l", required=True, help="list id or prefix")
    create.add_argument("--description", "-d", default="")
    create.add_argument("--status", "-s", choices=enum_args.TASK_STATUS.choices, default="todo")
    create.add_argument("--priority", "-p", choices=enum_args.TASK_PRIORITY.choices, default="none")
    create.add_argument("--assignee", "-a", help="user id or prefix; must be able to edit the list")
    create.add_argument("--label", action="append", help="repeatable; label id or prefix")
    create.add_argument("--due", help=f"date, or one of {'/'.join(_DATE_WORDS)}")
    create.add_argument("--starts", help="date the work can begin")
    create.add_argument("--estimate", type=int, default=0, help="estimate in minutes")
    create.add_argument("--repeat", choices=enum_args.RECURRENCE.choices, help="repeat rule")
    create.add_argument("--every", type=int, default=1, help="repeat every N periods")
    create.add_argument("--until", help="stop repeating after this date")
    create.add_argument("--subtask", action="append", help="repeatable checklist item")
    create.set_defaults(handler=_create)

    update = commands.add_parser("update", help="change a task (only the flags you pass)")
    update.add_argument("id")
    update.add_argument("--title")
    update.add_argument("--description")
    update.add_argument("--priority", "-p", choices=enum_args.TASK_PRIORITY.choices)
    update.add_argument("--estimate", type=int)
    update.add_argument("--due", help="date, or 'none' to clear it")
    update.add_argument("--starts", help="date, or 'none' to clear it")
    update.add_argument("--repeat", choices=enum_args.RECURRENCE.choices)
    update.add_argument("--every", type=int)
    update.set_defaults(handler=_update)

    status = commands.add_parser("status", help="move a task to a status")
    status.add_argument("id")
    status.add_argument("status", choices=enum_args.TASK_STATUS.choices)
    status.set_defaults(handler=_status)

    done = commands.add_parser("done", help="mark a task done (rolls a repeat forward)")
    done.add_argument("id")
    done.set_defaults(handler=_status, status="done")

    start = commands.add_parser("start", help="mark a task in progress")
    start.add_argument("id")
    start.set_defaults(handler=_status, status="in-progress")

    reopen = commands.add_parser("reopen", help="move a task back to not started")
    reopen.add_argument("id")
    reopen.set_defaults(handler=_status, status="todo")

    assign = commands.add_parser("assign", help="assign a task, or clear the assignee")
    assign.add_argument("id")
    assign.add_argument("--to", help="user id or prefix; omit to unassign")
    assign.set_defaults(handler=_assign)

    move = commands.add_parser("move", help="reorder a task, or move it to another list")
    move.add_argument("id")
    move.add_argument("--to-list", help="target list id or prefix")
    move.add_argument("--position", type=int, default=0, help="zero-based index (default: 0)")
    move.set_defaults(handler=_move)

    delete = commands.add_parser("delete", aliases=["rm"], help="delete a task")
    delete.add_argument("id")
    delete.add_argument("--yes", "-y", action="store_true")
    delete.set_defaults(handler=_delete)

    bulk = commands.add_parser("bulk", help="apply one change to many tasks")
    bulk.add_argument("ids", nargs="+", help="task ids or prefixes")
    change = bulk.add_mutually_exclusive_group(required=True)
    change.add_argument("--status", "-s", choices=enum_args.TASK_STATUS.choices)
    change.add_argument("--priority", "-p", choices=enum_args.TASK_PRIORITY.choices)
    change.add_argument("--to-list", help="move them all to this list")
    change.add_argument("--assign-to", help="assign them all to this user")
    change.add_argument("--unassign", action="store_true", help="clear every assignee")
    bulk.set_defaults(handler=_bulk)

    labels = commands.add_parser("labels", help="replace a task's labels")
    labels.add_argument("id")
    labels.add_argument("--set", action="append", dest="label_ids", help="repeatable; empty clears")
    labels.set_defaults(handler=_set_labels)

    # --- Subtasks ---
    add_subtask = commands.add_parser("add-subtask", help="append a checklist item")
    add_subtask.add_argument("id", help="task id")
    add_subtask.add_argument("title")
    add_subtask.set_defaults(handler=_add_subtask)

    check = commands.add_parser("check", help="tick a checklist item off")
    check.add_argument("id", help="task id")
    check.add_argument("subtask", help="subtask id or prefix")
    check.set_defaults(handler=_check_subtask, completed=True)

    uncheck = commands.add_parser("uncheck", help="untick a checklist item")
    uncheck.add_argument("id", help="task id")
    uncheck.add_argument("subtask")
    uncheck.set_defaults(handler=_check_subtask, completed=False)

    delete_subtask = commands.add_parser("delete-subtask", help="remove a checklist item")
    delete_subtask.add_argument("id", help="task id")
    delete_subtask.add_argument("subtask")
    delete_subtask.set_defaults(handler=_delete_subtask)

    # --- Comments ---
    comments = commands.add_parser("comments", help="show a task's comments")
    comments.add_argument("id")
    comments.add_argument("--limit", type=int, default=25)
    comments.add_argument("--cursor", default="")
    comments.set_defaults(handler=_comments)

    comment = commands.add_parser("comment", help="add a comment")
    comment.add_argument("id")
    comment.add_argument("body", help="what to say")
    comment.set_defaults(handler=_comment)

    edit_comment = commands.add_parser("edit-comment", help="edit your own comment")
    edit_comment.add_argument("comment_id")
    edit_comment.add_argument("body")
    edit_comment.set_defaults(handler=_edit_comment)

    delete_comment = commands.add_parser("delete-comment", help="delete a comment")
    delete_comment.add_argument("comment_id")
    delete_comment.set_defaults(handler=_delete_comment)

    # --- Activity ---
    activity = commands.add_parser("activity", help="show the activity feed")
    activity.add_argument("--list", "-l", dest="list_filter", help="narrow to one list")
    activity.add_argument("--task", "-t", dest="task_filter", help="narrow to one task")
    activity.add_argument(
        "--action", action="append", choices=enum_args.ACTIVITY_ACTION.choices, help="repeatable"
    )
    activity.add_argument("--limit", type=int, default=25)
    activity.add_argument("--cursor", default="")
    activity.set_defaults(handler=_activity)


# --- Shared helpers ----------------------------------------------------------


def parse_date(value: str | None) -> Timestamp | None:
    """Parses a date argument into a proto timestamp.

    Accepts the words in :data:`_DATE_WORDS`, a bare ``YYYY-MM-DD`` (interpreted at
    09:00 local time, which is what "due Tuesday" means to a person), or a full ISO
    timestamp.

    Returns:
        The timestamp, or ``None`` for ``none``/empty — which callers read as "clear
        this field".

    Raises:
        CliError: If the value is not a date this understands.
    """
    if not value or value.lower() == "none":
        return None

    today = datetime.now().astimezone().replace(hour=9, minute=0, second=0, microsecond=0)
    word = value.lower()
    shortcuts = {
        "today": today,
        "tomorrow": today + timedelta(days=1),
        "yesterday": today - timedelta(days=1),
        "next-week": today + timedelta(days=7),
        # Next Monday; today counts as "this" Monday, so it always moves forward.
        "monday": today + timedelta(days=(7 - today.weekday()) or 7),
    }
    if word in shortcuts:
        moment = shortcuts[word]
    else:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            raise CliError(
                f"{value!r} is not a date.",
                hint=f"Use YYYY-MM-DD, an ISO timestamp, or one of: {', '.join(_DATE_WORDS)}",
            ) from None
        moment = (
            (parsed.replace(hour=9) if parsed.hour == parsed.minute == 0 else parsed).astimezone()
            if parsed.tzinfo is None
            else parsed
        )

    stamp = Timestamp()
    stamp.FromDatetime(moment.astimezone(UTC))
    return stamp


def _resolve_task(api: Api, prefix: str) -> str:
    return resolve_id(prefix, lookup.tasks(api), kind="task")


def _resolve_people(api: Api, prefixes: list[str] | None) -> list[str]:
    """Resolves user id prefixes against the people the caller shares a list with."""
    if not prefixes:
        return []
    candidates = lookup.members(api)
    return [resolve_id(prefix, candidates, kind="member") for prefix in prefixes]


# --- Handlers ----------------------------------------------------------------


def _list(api: Api, options: argparse.Namespace) -> int:
    statuses = enum_args.TASK_STATUS.to_numbers(options.status)
    if options.open and not statuses:
        # "Open" is every non-terminal status, derived rather than hard-coded.
        statuses = [
            enum_args.TASK_STATUS.to_number(word)
            for word in enum_args.TASK_STATUS.choices
            if word not in {"done", "cancelled"}
        ]

    assignees = _resolve_people(api, options.assignee)
    if options.mine:
        me = api.users.get_current_user(
            user_pb2.GetCurrentUserRequest(), headers=api.require_token()
        )
        assignees.append(me.user.id)

    label_candidates = lookup.labels(api) if options.label else {}
    label_ids = [
        resolve_id(prefix, label_candidates, kind="label") for prefix in options.label or []
    ]
    list_candidates = lookup.lists(api) if options.lists else {}
    list_ids = [resolve_id(prefix, list_candidates, kind="list") for prefix in options.lists or []]

    request = task_pb2.ListTasksRequest(
        page=common_pb2.PageRequest(limit=options.limit, cursor=options.cursor),
        list_ids=list_ids,
        query=options.query,
        statuses=statuses,
        priorities=enum_args.TASK_PRIORITY.to_numbers(options.priority),
        label_ids=label_ids,
        assignee_ids=assignees,
        unassigned_only=options.unassigned,
        overdue_only=options.overdue,
        sort_field=enum_args.TASK_SORT.to_number(options.sort),
        sort_direction=enum_args.SORT_DIRECTION.to_number("desc" if options.desc else "asc"),
    )
    if (after := parse_date(options.due_after)) is not None:
        request.due_after.CopyFrom(after)
    if (before := parse_date(options.due_before)) is not None:
        request.due_before.CopyFrom(before)

    response = api.tasks.list_tasks(request, headers=api.require_token())
    if options.json:
        print(output.as_json(response))
        return 0

    locale = options.locale
    rows = []
    for task in response.tasks:
        due = display.relative_date(task.due_at, locale=locale) if task.HasField("due_at") else "—"
        rows.append(
            [
                display.status_mark(enum_args.TASK_STATUS.value_name(task.status)),
                display.priority_mark(enum_args.TASK_PRIORITY.value_name(task.priority)),
                output.short_id(task.id),
                output.truncate(task.title, 40),
                output.truncate(task.list.name, 16),
                task.assignee.display_name.split()[0] if task.HasField("assignee") else "—",
                output.paint(due, "red") if task.overdue else due,
                ",".join(label.name for label in task.labels) or "",
                f"{task.completed_subtask_count}/{task.subtask_count}"
                if task.subtask_count
                else "",
                str(task.comment_count) if task.comment_count else "",
            ]
        )
    print(
        output.table(
            ["", "", "ID", "TITLE", "LIST", "WHO", "DUE", "LABELS", "☑", "💬"],
            rows,
            empty_message="No tasks match. Try: todoapp tasks list --open",
        )
    )

    if response.status_counts:
        print()
        summary = "  ".join(
            f"{display.enum_name(f'TASK_STATUS_{label.upper()}', locale=locale)}: {count}"
            for label, count in sorted(response.status_counts.items())
        )
        print(output.paint(summary, "dim"))
    if response.page.has_more:
        print(output.paint(f"Next page: --cursor {response.page.next_cursor}", "dim"))
    return 0


def _get(api: Api, options: argparse.Namespace) -> int:
    task_id = _resolve_task(api, options.id)
    response = api.tasks.get_task(task_pb2.GetTaskRequest(id=task_id), headers=api.require_token())
    if options.json:
        print(output.as_json(response))
        return 0

    task = response.task
    locale = options.locale
    pairs = [
        ("ID", task.id),
        ("List", task.list.name),
        ("Status", display.enum_name(enum_args.TASK_STATUS.value_name(task.status), locale=locale)),
        (
            "Priority",
            display.enum_name(enum_args.TASK_PRIORITY.value_name(task.priority), locale=locale),
        ),
        (
            "Assignee",
            f"{task.assignee.display_name} <{task.assignee.email}>"
            if task.HasField("assignee")
            else "—",
        ),
        (
            "Due",
            (
                display.timestamp(task.due_at, locale=locale, with_time=task.due_has_time)
                + (output.paint("  overdue", "red") if task.overdue else "")
            )
            if task.HasField("due_at")
            else "—",
        ),
        ("Created by", task.created_by.display_name if task.HasField("created_by") else "—"),
        ("Created", display.timestamp(task.created_at, locale=locale)),
    ]
    if task.description:
        pairs.insert(1, ("Description", task.description))
    if task.HasField("starts_at"):
        pairs.append(("Starts", display.timestamp(task.starts_at, locale=locale, with_time=False)))
    if task.estimate_minutes:
        pairs.append(("Estimate", f"{task.estimate_minutes} min"))
    if task.recurrence.frequency and enum_args.RECURRENCE.word(task.recurrence.frequency) != "none":
        rule = display.enum_name(
            enum_args.RECURRENCE.value_name(task.recurrence.frequency), locale=locale
        )
        pairs.append(("Repeats", f"{rule} (every {task.recurrence.interval})"))
    if task.HasField("completed_at"):
        pairs.append(("Completed", display.timestamp(task.completed_at, locale=locale)))
        if task.HasField("completed_by"):
            pairs.append(("Completed by", task.completed_by.display_name))
    if task.labels:
        pairs.append(("Labels", ", ".join(label.name for label in task.labels)))

    print(output.detail(pairs, title=task.title))

    if task.subtasks:
        print()
        print(output.paint("Checklist", "bold"))
        for subtask in task.subtasks:
            mark = "●" if subtask.completed else "○"
            line = f"  {mark} {subtask.title}  {output.paint(output.short_id(subtask.id), 'dim')}"
            print(output.paint(line, "dim") if subtask.completed else line)

    comments = api.tasks.list_comments(
        task_pb2.ListCommentsRequest(task_id=task_id, page=common_pb2.PageRequest(limit=10)),
        headers=api.require_token(),
    )
    if comments.comments:
        print()
        print(output.paint("Comments", "bold"))
        for comment in comments.comments:
            who = comment.author.display_name if comment.HasField("author") else "—"
            when = display.timestamp(comment.created_at, locale=locale)
            edited = " (edited)" if comment.edited else ""
            print(f"  {output.paint(f'{who} · {when}{edited}', 'dim')}")
            print(f"    {comment.body}")
    return 0


def _create(api: Api, options: argparse.Namespace) -> int:
    list_id = resolve_id(options.list, lookup.lists(api), kind="list")
    label_ids = (
        [resolve_id(prefix, lookup.labels(api), kind="label") for prefix in options.label]
        if options.label
        else []
    )
    request = task_pb2.CreateTaskRequest(
        list_id=list_id,
        title=options.title,
        description=options.description,
        status=enum_args.TASK_STATUS.to_number(options.status),
        priority=enum_args.TASK_PRIORITY.to_number(options.priority),
        label_ids=label_ids,
        estimate_minutes=options.estimate,
        subtask_titles=options.subtask or [],
    )
    if options.assignee:
        request.assignee_id = _resolve_people(api, [options.assignee])[0]
    if (due := parse_date(options.due)) is not None:
        request.due_at.CopyFrom(due)
        # A bare date means an all-day task; a real time means the clock matters.
        request.due_has_time = ":" in (options.due or "")
    if (starts := parse_date(options.starts)) is not None:
        request.starts_at.CopyFrom(starts)
    if options.repeat:
        request.recurrence.frequency = enum_args.RECURRENCE.to_number(options.repeat)
        request.recurrence.interval = max(options.every, 1)
        if (until := parse_date(options.until)) is not None:
            request.recurrence.until.CopyFrom(until)

    response = api.tasks.create_task(request, headers=api.require_token())
    if options.json:
        print(output.as_json(response))
    else:
        output.success(
            f"Created {response.task.title} ({output.short_id(response.task.id)}) "
            f"in {response.task.list.name}"
        )
    return 0


def _update(api: Api, options: argparse.Namespace) -> int:
    task_id = _resolve_task(api, options.id)
    request = task_pb2.UpdateTaskRequest(id=task_id)
    changed = False

    if options.title is not None:
        request.title = options.title
        changed = True
    if options.description is not None:
        request.description = options.description
        changed = True
    if options.priority is not None:
        request.priority = enum_args.TASK_PRIORITY.to_number(options.priority)
        changed = True
    if options.estimate is not None:
        request.estimate_minutes = options.estimate
        changed = True
    if options.due is not None:
        # `--due none` clears; anything else sets. Proto3 presence alone cannot say
        # "remove this", which is why the API has an explicit clear flag.
        if options.due.lower() == "none":
            request.clear_due_at = True
        else:
            due = parse_date(options.due)
            assert due is not None
            request.due_at.CopyFrom(due)
            request.due_has_time = ":" in options.due
        changed = True
    if options.starts is not None:
        if options.starts.lower() == "none":
            request.clear_starts_at = True
        else:
            starts = parse_date(options.starts)
            assert starts is not None
            request.starts_at.CopyFrom(starts)
        changed = True
    if options.repeat is not None:
        request.recurrence.frequency = enum_args.RECURRENCE.to_number(options.repeat)
        request.recurrence.interval = max(options.every or 1, 1)
        changed = True

    if not changed:
        raise CliError("Nothing to change.", hint="Pass at least one of --title/--due/--priority/…")

    response = api.tasks.update_task(request, headers=api.require_token())
    if options.json:
        print(output.as_json(response))
    else:
        output.success(f"Updated {response.task.title}.")
    return 0


def _status(api: Api, options: argparse.Namespace) -> int:
    task_id = _resolve_task(api, options.id)
    response = api.tasks.set_task_status(
        task_pb2.SetTaskStatusRequest(
            id=task_id, status=enum_args.TASK_STATUS.to_number(options.status)
        ),
        headers=api.require_token(),
    )
    if options.json:
        print(output.as_json(response))
        return 0

    label = display.enum_name(
        enum_args.TASK_STATUS.value_name(response.task.status), locale=options.locale
    )
    output.success(f"{response.task.title} → {label}")
    if response.HasField("next_occurrence"):
        following = response.next_occurrence
        when = display.timestamp(following.due_at, locale=options.locale, with_time=False)
        print(
            output.paint(
                f"  Next one created: {following.title}, due {when} "
                f"({output.short_id(following.id)})",
                "dim",
            )
        )
    return 0


def _assign(api: Api, options: argparse.Namespace) -> int:
    task_id = _resolve_task(api, options.id)
    request = task_pb2.AssignTaskRequest(id=task_id)
    if options.to:
        request.assignee_id = _resolve_people(api, [options.to])[0]
    response = api.tasks.assign_task(request, headers=api.require_token())
    if options.json:
        print(output.as_json(response))
    elif response.task.HasField("assignee"):
        output.success(f"{response.task.title} → {response.task.assignee.display_name}")
    else:
        output.success(f"{response.task.title} is now unassigned.")
    return 0


def _move(api: Api, options: argparse.Namespace) -> int:
    task_id = _resolve_task(api, options.id)
    request = task_pb2.MoveTaskRequest(id=task_id, position=options.position)
    if options.to_list:
        request.list_id = resolve_id(options.to_list, lookup.lists(api), kind="list")
    response = api.tasks.move_task(request, headers=api.require_token())
    if options.json:
        print(output.as_json(response))
    else:
        output.success(
            f"{response.task.title} is now #{response.task.position + 1} in "
            f"{response.task.list.name}"
        )
    return 0


def _delete(api: Api, options: argparse.Namespace) -> int:
    candidates = lookup.tasks(api)
    task_id = resolve_id(options.id, candidates, kind="task")
    title = candidates[task_id]
    if not options.yes:
        answer = input(f"Delete {title!r}? [y/N] ").strip().lower()
        if answer not in {"y", "yes", "j", "ja"}:
            output.warn("Cancelled.")
            return 1
    api.tasks.delete_task(task_pb2.DeleteTaskRequest(id=task_id), headers=api.require_token())
    if not options.json:
        output.success(f"Deleted {title}.")
    return 0


def _bulk(api: Api, options: argparse.Namespace) -> int:
    candidates = lookup.tasks(api)
    ids = [resolve_id(prefix, candidates, kind="task") for prefix in options.ids]
    request = task_pb2.BulkUpdateTasksRequest(task_ids=ids)

    if options.status:
        request.status = enum_args.TASK_STATUS.to_number(options.status)
    elif options.priority:
        request.priority = enum_args.TASK_PRIORITY.to_number(options.priority)
    elif options.to_list:
        request.list_id = resolve_id(options.to_list, lookup.lists(api), kind="list")
    elif options.assign_to:
        request.assignee_id = _resolve_people(api, [options.assign_to])[0]
    elif options.unassign:
        request.clear_assignee = True

    response = api.tasks.bulk_update_tasks(request, headers=api.require_token())
    if options.json:
        print(output.as_json(response))
        return 0

    output.success(f"Updated {response.updated_count} task(s).")
    if response.updated_count < len(ids):
        output.warn(
            f"{len(ids) - response.updated_count} task(s) were skipped — you cannot edit them."
        )
    return 0


def _set_labels(api: Api, options: argparse.Namespace) -> int:
    task_id = _resolve_task(api, options.id)
    label_ids = (
        [resolve_id(prefix, lookup.labels(api), kind="label") for prefix in options.label_ids]
        if options.label_ids
        else []
    )
    response = api.tasks.set_task_labels(
        task_pb2.SetTaskLabelsRequest(task_id=task_id, label_ids=label_ids),
        headers=api.require_token(),
    )
    if options.json:
        print(output.as_json(response))
    elif response.task.labels:
        output.success("Labels: " + ", ".join(label.name for label in response.task.labels))
    else:
        output.success("Labels cleared.")
    return 0


def _add_subtask(api: Api, options: argparse.Namespace) -> int:
    task_id = _resolve_task(api, options.id)
    response = api.tasks.create_subtask(
        task_pb2.CreateSubtaskRequest(task_id=task_id, title=options.title),
        headers=api.require_token(),
    )
    if options.json:
        print(output.as_json(response))
    else:
        output.success(f"Added {response.subtask.title}.")
    return 0


def _check_subtask(api: Api, options: argparse.Namespace) -> int:
    task_id = _resolve_task(api, options.id)
    subtask_id = resolve_id(options.subtask, lookup.subtasks(api, task_id), kind="subtask")
    response = api.tasks.update_subtask(
        task_pb2.UpdateSubtaskRequest(id=subtask_id, completed=options.completed),
        headers=api.require_token(),
    )
    if options.json:
        print(output.as_json(response))
    else:
        mark = "●" if response.subtask.completed else "○"
        output.success(f"{mark} {response.subtask.title}")
    return 0


def _delete_subtask(api: Api, options: argparse.Namespace) -> int:
    task_id = _resolve_task(api, options.id)
    candidates = lookup.subtasks(api, task_id)
    subtask_id = resolve_id(options.subtask, candidates, kind="subtask")
    api.tasks.delete_subtask(
        task_pb2.DeleteSubtaskRequest(id=subtask_id), headers=api.require_token()
    )
    if not options.json:
        output.success(f"Removed {candidates[subtask_id]}.")
    return 0


def _comments(api: Api, options: argparse.Namespace) -> int:
    task_id = _resolve_task(api, options.id)
    response = api.tasks.list_comments(
        task_pb2.ListCommentsRequest(
            task_id=task_id,
            page=common_pb2.PageRequest(limit=options.limit, cursor=options.cursor),
        ),
        headers=api.require_token(),
    )
    if options.json:
        print(output.as_json(response))
        return 0
    print(
        output.table(
            ["ID", "AUTHOR", "WHEN", "COMMENT"],
            [
                [
                    output.short_id(comment.id),
                    comment.author.display_name if comment.HasField("author") else "—",
                    display.timestamp(comment.created_at, locale=options.locale),
                    output.truncate(comment.body, 60) + (" (edited)" if comment.edited else ""),
                ]
                for comment in response.comments
            ],
            empty_message="No comments yet.",
        )
    )
    return 0


def _comment(api: Api, options: argparse.Namespace) -> int:
    task_id = _resolve_task(api, options.id)
    response = api.tasks.create_comment(
        task_pb2.CreateCommentRequest(task_id=task_id, body=options.body),
        headers=api.require_token(),
    )
    if options.json:
        print(output.as_json(response))
    else:
        output.success(f"Comment added ({output.short_id(response.comment.id)}).")
    return 0


def _edit_comment(api: Api, options: argparse.Namespace) -> int:
    comment_id = resolve_id(options.comment_id, lookup.comments(api), kind="comment")
    response = api.tasks.update_comment(
        task_pb2.UpdateCommentRequest(id=comment_id, body=options.body),
        headers=api.require_token(),
    )
    if options.json:
        print(output.as_json(response))
    else:
        output.success("Comment updated.")
    return 0


def _delete_comment(api: Api, options: argparse.Namespace) -> int:
    comment_id = resolve_id(options.comment_id, lookup.comments(api), kind="comment")
    api.tasks.delete_comment(
        task_pb2.DeleteCommentRequest(id=comment_id), headers=api.require_token()
    )
    if not options.json:
        output.success("Comment deleted.")
    return 0


def _activity(api: Api, options: argparse.Namespace) -> int:
    request = task_pb2.ListActivityRequest(
        page=common_pb2.PageRequest(limit=options.limit, cursor=options.cursor),
        actions=enum_args.ACTIVITY_ACTION.to_numbers(options.action),
    )
    if options.list_filter:
        request.list_id = resolve_id(options.list_filter, lookup.lists(api), kind="list")
    if options.task_filter:
        request.task_id = _resolve_task(api, options.task_filter)

    response = api.tasks.list_activity(request, headers=api.require_token())
    if options.json:
        print(output.as_json(response))
        return 0

    locale = options.locale
    for entry in response.activities:
        who = entry.actor.display_name if entry.HasField("actor") else "—"
        verb = display.enum_name(enum_args.ACTIVITY_ACTION.value_name(entry.action), locale=locale)
        when = display.timestamp(entry.created_at, locale=locale)
        line = f"{output.paint(when, 'dim')}  {who} {verb} {entry.target_label or '—'}"
        if entry.HasField("change") and entry.change.field:
            before = _humanise_change(entry.change.field, entry.change.from_value, locale)
            after = _humanise_change(entry.change.field, entry.change.to_value, locale)
            line += output.paint(f"  ({entry.change.field}: {before} → {after})", "dim")
        print(line)
    if not response.activities:
        print(output.paint("No activity yet.", "dim"))
    if response.page.has_more:
        print(output.paint(f"Next page: --cursor {response.page.next_cursor}", "dim"))
    return 0


def _humanise_change(field: str, value: str, locale: str) -> str:
    """Localizes an activity diff value when it is a known enum label.

    The server stores raw labels precisely so the client can do this; a status change
    should read "Færdig", not "done".
    """
    if not value:
        return "—"
    enum_by_field = {
        "status": ("TASK_STATUS_", enum_args.TASK_STATUS),
        "priority": ("TASK_PRIORITY_", enum_args.TASK_PRIORITY),
        "role": ("MEMBER_ROLE_", enum_args.MEMBER_ROLE),
        "visibility": ("LIST_VISIBILITY_", enum_args.LIST_VISIBILITY),
        "color": ("LIST_COLOR_", enum_args.LIST_COLOR),
    }
    if field in enum_by_field:
        prefix, _ = enum_by_field[field]
        return display.enum_name(f"{prefix}{value.upper()}", locale=locale)
    return output.truncate(value, 24)
