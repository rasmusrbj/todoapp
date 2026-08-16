"""``todoapp lists …`` — lists, members, and labels."""

from __future__ import annotations

import argparse
from typing import Any

from todo.v1 import common_pb2, list_pb2
from todoapp.cli import args as enum_args
from todoapp.cli import display, lookup, output
from todoapp.cli.client import Api, CliError, resolve_id


def register(subparsers: Any) -> None:
    """Adds the ``lists`` command group."""
    parser = subparsers.add_parser(
        "lists",
        aliases=["list"],
        help="create, read, update, and share lists",
        description="Lists, their members, and their labels.",
    )
    commands = parser.add_subparsers(
        dest="lists_command",
        metavar="<command>",
        required=True,
        parser_class=enum_args.LeafParser,
    )

    ls = commands.add_parser("list", aliases=["ls"], help="list the lists you can see")
    ls.add_argument("--query", "-q", default="", help="search name and description")
    ls.add_argument(
        "--visibility",
        action="append",
        choices=enum_args.LIST_VISIBILITY.choices,
        help="repeatable; matches any of the given values",
    )
    ls.add_argument(
        "--role",
        action="append",
        choices=enum_args.MEMBER_ROLE.choices,
        help="only lists where you hold one of these roles",
    )
    ls.add_argument("--archived", action="store_true", help="include archived lists")
    ls.add_argument("--sort", choices=enum_args.LIST_SORT.choices, default="position")
    ls.add_argument("--desc", action="store_true", help="reverse the sort")
    ls.add_argument("--limit", type=int, default=25, help="page size (max 100)")
    ls.add_argument("--cursor", default="", help="cursor from a previous page")
    ls.set_defaults(handler=_list)

    get = commands.add_parser("get", help="show one list in full")
    get.add_argument("id", help="list id, or a unique prefix of one")
    get.set_defaults(handler=_get)

    create = commands.add_parser("create", help="create a list")
    create.add_argument("name", help="list name")
    create.add_argument("--description", "-d", default="")
    create.add_argument("--color", choices=enum_args.LIST_COLOR.choices, default="zinc")
    create.add_argument(
        "--visibility", choices=enum_args.LIST_VISIBILITY.choices, default="private"
    )
    create.set_defaults(handler=_create)

    update = commands.add_parser("update", help="change a list (only the flags you pass)")
    update.add_argument("id")
    update.add_argument("--name")
    update.add_argument("--description")
    update.add_argument("--color", choices=enum_args.LIST_COLOR.choices)
    update.add_argument(
        "--visibility",
        choices=enum_args.LIST_VISIBILITY.choices,
        help="owner only — this decides who can reach the list",
    )
    update.set_defaults(handler=_update)

    archive = commands.add_parser("archive", help="archive a list")
    archive.add_argument("id")
    archive.set_defaults(handler=_archive, archived=True)

    restore = commands.add_parser("restore", help="restore an archived list")
    restore.add_argument("id")
    restore.set_defaults(handler=_archive, archived=False)

    delete = commands.add_parser("delete", aliases=["rm"], help="delete a list and its tasks")
    delete.add_argument("id")
    delete.add_argument("--yes", "-y", action="store_true", help="skip the confirmation")
    delete.set_defaults(handler=_delete)

    reorder = commands.add_parser("reorder", help="set the order of your own lists")
    reorder.add_argument("ids", nargs="+", help="list ids, top to bottom")
    reorder.set_defaults(handler=_reorder)

    # --- Members ---
    members = commands.add_parser("members", help="show who can reach a list")
    members.add_argument("id")
    members.set_defaults(handler=_members)

    share = commands.add_parser("share", help="give someone access")
    share.add_argument("id", help="list id")
    share.add_argument("--email", "-e", required=True, help="the person's email address")
    share.add_argument(
        "--role",
        choices=[r for r in enum_args.MEMBER_ROLE.choices if r != "owner"],
        default="editor",
    )
    share.set_defaults(handler=_share)

    set_role = commands.add_parser("set-role", help="change a member's role")
    set_role.add_argument("id", help="list id")
    set_role.add_argument("--user", "-u", required=True, help="the member's user id")
    set_role.add_argument(
        "--role",
        required=True,
        choices=[r for r in enum_args.MEMBER_ROLE.choices if r != "owner"],
    )
    set_role.set_defaults(handler=_set_role)

    unshare = commands.add_parser("unshare", help="revoke someone's access")
    unshare.add_argument("id", help="list id")
    unshare.add_argument("--user", "-u", required=True, help="the member's user id")
    unshare.set_defaults(handler=_unshare)

    # --- Labels ---
    labels = commands.add_parser("labels", help="show a list's labels")
    labels.add_argument("id")
    labels.set_defaults(handler=_labels)

    add_label = commands.add_parser("add-label", help="create a label on a list")
    add_label.add_argument("id", help="list id")
    add_label.add_argument("name", help="label name")
    add_label.add_argument("--color", choices=enum_args.LIST_COLOR.choices, default="zinc")
    add_label.set_defaults(handler=_add_label)

    update_label = commands.add_parser("update-label", help="rename or recolour a label")
    update_label.add_argument("label_id")
    update_label.add_argument("--name")
    update_label.add_argument("--color", choices=enum_args.LIST_COLOR.choices)
    update_label.set_defaults(handler=_update_label)

    delete_label = commands.add_parser("delete-label", help="delete a label")
    delete_label.add_argument("label_id")
    delete_label.set_defaults(handler=_delete_label)


def _page(options: argparse.Namespace) -> common_pb2.PageRequest:
    return common_pb2.PageRequest(limit=options.limit, cursor=options.cursor)


def _direction(options: argparse.Namespace) -> int:
    return enum_args.SORT_DIRECTION.to_number("desc" if options.desc else "asc")


def _resolve_list(api: Api, prefix: str) -> str:
    return resolve_id(prefix, lookup.lists(api), kind="list")


def _list(api: Api, options: argparse.Namespace) -> int:
    response = api.lists.list_lists(
        list_pb2.ListListsRequest(
            page=_page(options),
            query=options.query,
            visibilities=enum_args.LIST_VISIBILITY.to_numbers(options.visibility),
            roles=enum_args.MEMBER_ROLE.to_numbers(options.role),
            include_archived=options.archived,
            sort_field=enum_args.LIST_SORT.to_number(options.sort),
            sort_direction=_direction(options),
        ),
        headers=api.require_token(),
    )
    if options.json:
        print(output.as_json(response))
        return 0

    rows = [
        [
            output.short_id(item.id),
            output.truncate(item.name, 32) + (" (arkiveret)" if item.archived else ""),
            display.enum_name(
                enum_args.LIST_VISIBILITY.value_name(item.visibility), locale=options.locale
            ),
            display.enum_name(
                enum_args.MEMBER_ROLE.value_name(item.viewer_role), locale=options.locale
            )
            if item.viewer_role
            else "—",
            f"{item.stats.open_task_count}/{item.stats.total_task_count}",
            f"{item.stats.completion_percent}%",
            str(item.stats.overdue_task_count) if item.stats.overdue_task_count else "",
            display.relative_date(item.stats.next_due_at, locale=options.locale)
            if item.stats.HasField("next_due_at")
            else "—",
        ]
        for item in response.lists
    ]
    print(
        output.table(
            ["ID", "NAME", "VISIBILITY", "YOUR ROLE", "OPEN", "DONE", "LATE", "NEXT DUE"],
            rows,
            empty_message='No lists yet. Create one: todoapp lists create "My list"',
        )
    )
    _print_page_footer(response.page)
    return 0


def _print_page_footer(page: common_pb2.PageResponse) -> None:
    """Prints the count, and how to fetch the next page when there is one."""
    if page.has_more:
        print()
        print(
            output.paint(
                f"Showing {page.total_count} in total. Next page: --cursor {page.next_cursor}",
                "dim",
            )
        )
    elif page.total_count:
        print()
        print(output.paint(f"{page.total_count} in total.", "dim"))


def _get(api: Api, options: argparse.Namespace) -> int:
    list_id = _resolve_list(api, options.id)
    response = api.lists.get_list(list_pb2.GetListRequest(id=list_id), headers=api.require_token())
    if options.json:
        print(output.as_json(response))
        return 0

    item = response.list
    locale = options.locale
    pairs = [
        ("ID", item.id),
        ("Owner", f"{item.owner.display_name} <{item.owner.email}>"),
        (
            "Visibility",
            display.enum_name(enum_args.LIST_VISIBILITY.value_name(item.visibility), locale=locale),
        ),
        ("Colour", display.enum_name(enum_args.LIST_COLOR.value_name(item.color), locale=locale)),
        (
            "Your role",
            display.enum_name(enum_args.MEMBER_ROLE.value_name(item.viewer_role), locale=locale)
            if item.viewer_role
            else "—",
        ),
        ("Archived", "yes" if item.archived else "no"),
        ("Tasks", f"{item.stats.open_task_count} open of {item.stats.total_task_count}"),
        ("Done", f"{item.stats.completion_percent}%"),
        ("Overdue", str(item.stats.overdue_task_count)),
        ("Created", display.timestamp(item.created_at, locale=locale, with_time=False)),
    ]
    if item.description:
        pairs.insert(1, ("Description", item.description))
    print(output.detail(pairs, title=item.name))

    if item.members:
        print()
        print(
            output.table(
                ["MEMBER", "EMAIL", "ROLE"],
                [
                    [
                        member.user.display_name,
                        member.user.email,
                        display.enum_name(
                            enum_args.MEMBER_ROLE.value_name(member.role), locale=locale
                        ),
                    ]
                    for member in item.members
                ],
            )
        )
    if item.labels:
        print()
        print(
            output.paint("Labels: ", "dim")
            + ", ".join(
                f"{label.name} ("
                f"{display.enum_name(enum_args.LIST_COLOR.value_name(label.color), locale=locale)})"
                for label in item.labels
            )
        )
    return 0


def _create(api: Api, options: argparse.Namespace) -> int:
    response = api.lists.create_list(
        list_pb2.CreateListRequest(
            name=options.name,
            description=options.description,
            color=enum_args.LIST_COLOR.to_number(options.color),
            visibility=enum_args.LIST_VISIBILITY.to_number(options.visibility),
        ),
        headers=api.require_token(),
    )
    if options.json:
        print(output.as_json(response))
    else:
        output.success(f"Created {response.list.name} ({output.short_id(response.list.id)})")
    return 0


def _update(api: Api, options: argparse.Namespace) -> int:
    list_id = _resolve_list(api, options.id)
    request = list_pb2.UpdateListRequest(id=list_id)
    changed = False
    if options.name is not None:
        request.name = options.name
        changed = True
    if options.description is not None:
        request.description = options.description
        changed = True
    if options.color is not None:
        request.color = enum_args.LIST_COLOR.to_number(options.color)
        changed = True
    if options.visibility is not None:
        request.visibility = enum_args.LIST_VISIBILITY.to_number(options.visibility)
        changed = True
    if not changed:
        raise CliError("Nothing to change.", hint="Pass at least one of --name/--description/…")

    response = api.lists.update_list(request, headers=api.require_token())
    if options.json:
        print(output.as_json(response))
    else:
        output.success(f"Updated {response.list.name}.")
    return 0


def _archive(api: Api, options: argparse.Namespace) -> int:
    list_id = _resolve_list(api, options.id)
    response = api.lists.set_list_archived(
        list_pb2.SetListArchivedRequest(id=list_id, archived=options.archived),
        headers=api.require_token(),
    )
    if options.json:
        print(output.as_json(response))
    else:
        output.success(f"{'Archived' if options.archived else 'Restored'} {response.list.name}.")
    return 0


def _delete(api: Api, options: argparse.Namespace) -> int:
    candidates = lookup.lists(api)
    list_id = resolve_id(options.id, candidates, kind="list")
    name = candidates[list_id]
    if not options.yes and not _confirm(f"Delete {name!r} and every task in it?"):
        output.warn("Cancelled.")
        return 1
    api.lists.delete_list(list_pb2.DeleteListRequest(id=list_id), headers=api.require_token())
    if not options.json:
        output.success(f"Deleted {name}.")
    return 0


def _confirm(question: str) -> bool:
    """Asks for a yes/no on stdin, defaulting to no."""
    answer = input(f"{question} [y/N] ").strip().lower()
    return answer in {"y", "yes", "j", "ja"}


def _reorder(api: Api, options: argparse.Namespace) -> int:
    candidates = lookup.lists(api)
    ids = [resolve_id(prefix, candidates, kind="list") for prefix in options.ids]
    response = api.lists.reorder_lists(
        list_pb2.ReorderListsRequest(list_ids=ids), headers=api.require_token()
    )
    if options.json:
        print(output.as_json(response))
    else:
        output.success("New order: " + " → ".join(item.name for item in response.lists))
    return 0


def _members(api: Api, options: argparse.Namespace) -> int:
    list_id = _resolve_list(api, options.id)
    response = api.lists.list_members(
        list_pb2.ListMembersRequest(list_id=list_id), headers=api.require_token()
    )
    if options.json:
        print(output.as_json(response))
        return 0
    print(
        output.table(
            ["USER ID", "NAME", "EMAIL", "ROLE", "ADDED BY", "SINCE"],
            [
                [
                    output.short_id(member.user.id),
                    member.user.display_name,
                    member.user.email,
                    display.enum_name(
                        enum_args.MEMBER_ROLE.value_name(member.role), locale=options.locale
                    ),
                    member.invited_by.display_name if member.HasField("invited_by") else "—",
                    display.timestamp(member.created_at, locale=options.locale, with_time=False),
                ]
                for member in response.members
            ],
        )
    )
    return 0


def _share(api: Api, options: argparse.Namespace) -> int:
    list_id = _resolve_list(api, options.id)
    response = api.lists.add_member(
        list_pb2.AddMemberRequest(
            list_id=list_id,
            email=options.email,
            role=enum_args.MEMBER_ROLE.to_number(options.role),
        ),
        headers=api.require_token(),
    )
    if options.json:
        print(output.as_json(response))
    else:
        role = display.enum_name(
            enum_args.MEMBER_ROLE.value_name(response.member.role), locale=options.locale
        )
        output.success(f"{response.member.user.display_name} now has access as {role}.")
    return 0


def _set_role(api: Api, options: argparse.Namespace) -> int:
    list_id = _resolve_list(api, options.id)
    members = api.lists.list_members(
        list_pb2.ListMembersRequest(list_id=list_id), headers=api.require_token()
    )
    candidates = {m.user.id: m.user.display_name for m in members.members}
    user_id = resolve_id(options.user, candidates, kind="member")
    response = api.lists.update_member_role(
        list_pb2.UpdateMemberRoleRequest(
            list_id=list_id, user_id=user_id, role=enum_args.MEMBER_ROLE.to_number(options.role)
        ),
        headers=api.require_token(),
    )
    if options.json:
        print(output.as_json(response))
    else:
        role = display.enum_name(
            enum_args.MEMBER_ROLE.value_name(response.member.role), locale=options.locale
        )
        output.success(f"{response.member.user.display_name} is now {role}.")
    return 0


def _unshare(api: Api, options: argparse.Namespace) -> int:
    list_id = _resolve_list(api, options.id)
    members = api.lists.list_members(
        list_pb2.ListMembersRequest(list_id=list_id), headers=api.require_token()
    )
    candidates = {m.user.id: m.user.display_name for m in members.members}
    user_id = resolve_id(options.user, candidates, kind="member")
    api.lists.remove_member(
        list_pb2.RemoveMemberRequest(list_id=list_id, user_id=user_id),
        headers=api.require_token(),
    )
    if not options.json:
        output.success(f"Removed {candidates[user_id]} from the list.")
    return 0


def _labels(api: Api, options: argparse.Namespace) -> int:
    list_id = _resolve_list(api, options.id)
    response = api.lists.list_labels(
        list_pb2.ListLabelsRequest(list_id=list_id), headers=api.require_token()
    )
    if options.json:
        print(output.as_json(response))
        return 0
    print(
        output.table(
            ["ID", "NAME", "COLOUR", "TASKS"],
            [
                [
                    output.short_id(label.id),
                    label.name,
                    display.enum_name(
                        enum_args.LIST_COLOR.value_name(label.color), locale=options.locale
                    ),
                    str(label.task_count),
                ]
                for label in response.labels
            ],
            empty_message="No labels on this list.",
        )
    )
    return 0


def _add_label(api: Api, options: argparse.Namespace) -> int:
    list_id = _resolve_list(api, options.id)
    response = api.lists.create_label(
        list_pb2.CreateLabelRequest(
            list_id=list_id,
            name=options.name,
            color=enum_args.LIST_COLOR.to_number(options.color),
        ),
        headers=api.require_token(),
    )
    if options.json:
        print(output.as_json(response))
    else:
        output.success(f"Added label {response.label.name}.")
    return 0


def _update_label(api: Api, options: argparse.Namespace) -> int:
    label_id = resolve_id(options.label_id, lookup.labels(api), kind="label")
    request = list_pb2.UpdateLabelRequest(id=label_id)
    if options.name is not None:
        request.name = options.name
    if options.color is not None:
        request.color = enum_args.LIST_COLOR.to_number(options.color)
    response = api.lists.update_label(request, headers=api.require_token())
    if options.json:
        print(output.as_json(response))
    else:
        output.success(f"Updated label {response.label.name}.")
    return 0


def _delete_label(api: Api, options: argparse.Namespace) -> int:
    candidates = lookup.labels(api)
    label_id = resolve_id(options.label_id, candidates, kind="label")
    api.lists.delete_label(list_pb2.DeleteLabelRequest(id=label_id), headers=api.require_token())
    if not options.json:
        output.success(f"Deleted label {candidates[label_id]}.")
    return 0
