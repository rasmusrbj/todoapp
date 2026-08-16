"""``todoapp users …`` — profile, preferences, and admin account management."""

from __future__ import annotations

import argparse
import getpass
from typing import Any

from todo.v1 import common_pb2, user_pb2
from todoapp.cli import args as enum_args
from todoapp.cli import display, lookup, output
from todoapp.cli.client import Api, CliError, resolve_id


def register(subparsers: Any) -> None:
    """Adds the ``users`` command group."""
    parser = subparsers.add_parser(
        "users",
        aliases=["user"],
        help="profiles, preferences, and (for admins) accounts",
        description="Users. Listing and status changes need the admin role.",
    )
    commands = parser.add_subparsers(
        dest="users_command",
        metavar="<command>",
        required=True,
        parser_class=enum_args.LeafParser,
    )

    ls = commands.add_parser("list", aliases=["ls"], help="list accounts (admin only)")
    ls.add_argument("--query", "-q", default="", help="search name and email")
    ls.add_argument("--role", action="append", choices=enum_args.USER_ROLE.choices)
    ls.add_argument("--status", action="append", choices=enum_args.USER_STATUS.choices)
    ls.add_argument("--sort", choices=enum_args.USER_SORT.choices, default="created-at")
    ls.add_argument("--asc", action="store_true", help="oldest first")
    ls.add_argument("--limit", type=int, default=25)
    ls.add_argument("--cursor", default="")
    ls.set_defaults(handler=_list)

    get = commands.add_parser("get", help="show one account (yourself, or admin for anyone)")
    get.add_argument("id", help="user id or prefix; 'me' for yourself")
    get.set_defaults(handler=_get)

    search = commands.add_parser("search", help="find people to share a list with")
    search.add_argument("query", help="name or email fragment")
    search.add_argument("--limit", type=int, default=10)
    search.set_defaults(handler=_search)

    create = commands.add_parser("create", help="create an account (admin only)")
    create.add_argument("--email", "-e", required=True)
    create.add_argument("--name", "-n", required=True)
    create.add_argument("--password", "-p", help="omit to be prompted")
    create.add_argument("--role", choices=enum_args.USER_ROLE.choices, default="member")
    create.add_argument(
        "--language",
        choices=enum_args.LOCALE.choices,
        default="da",
        help="the account's interface language",
    )
    create.add_argument("--time-zone", default="Europe/Copenhagen")
    create.set_defaults(handler=_create)

    update = commands.add_parser("update", help="change a profile or preference")
    update.add_argument("id", help="user id or prefix; 'me' for yourself")
    update.add_argument("--name", help="display name")
    update.add_argument("--bio")
    update.add_argument("--avatar-url")
    update.add_argument("--time-zone")
    update.add_argument(
        "--language",
        choices=enum_args.LOCALE.choices,
        help="the account's interface language",
    )
    update.add_argument("--theme", choices=enum_args.THEME.choices)
    update.add_argument("--role", choices=enum_args.USER_ROLE.choices, help="admin only")
    update.set_defaults(handler=_update)

    status = commands.add_parser("set-status", help="suspend or reactivate (admin only)")
    status.add_argument("id")
    status.add_argument("status", choices=enum_args.USER_STATUS.choices)
    status.add_argument("--reason", default="", help="shown to the user and recorded")
    status.set_defaults(handler=_set_status)

    delete = commands.add_parser("delete", aliases=["rm"], help="delete an account")
    delete.add_argument("id", help="user id or prefix; 'me' for yourself")
    delete.add_argument("--yes", "-y", action="store_true")
    delete.set_defaults(handler=_delete)


def _me(api: Api) -> user_pb2.User:
    return api.users.get_current_user(
        user_pb2.GetCurrentUserRequest(), headers=api.require_token()
    ).user


def _resolve_user(api: Api, prefix: str) -> str:
    """Resolves ``me``, a full id, or a prefix.

    A prefix is matched against the admin listing when the caller is an admin, and
    otherwise against the people they share a list with — a member has no way to
    enumerate the whole directory, and should not.
    """
    if prefix == "me":
        return _me(api).id

    return resolve_id(prefix, lookup.users(api), kind="user")


def _print_user(user: user_pb2.User, *, locale: str, server: str | None = None) -> None:
    pairs = [
        ("ID", user.id),
        ("Email", user.email),
        ("Role", display.enum_name(enum_args.USER_ROLE.value_name(user.role), locale=locale)),
        ("Status", display.enum_name(enum_args.USER_STATUS.value_name(user.status), locale=locale)),
        ("Confirmed", "yes" if user.email_verified else "no"),
        ("Language", display.enum_name(enum_args.LOCALE.value_name(user.locale), locale=locale)),
        ("Theme", display.enum_name(enum_args.THEME.value_name(user.theme), locale=locale)),
        ("Time zone", user.time_zone),
        ("Own lists", str(user.stats.owned_list_count)),
        ("Shared with them", str(user.stats.shared_list_count)),
        ("Open tasks", str(user.stats.open_task_count)),
        ("Completed", str(user.stats.completed_task_count)),
        ("Overdue", str(user.stats.overdue_task_count)),
        ("Created", display.timestamp(user.created_at, locale=locale, with_time=False)),
        (
            "Last seen",
            display.timestamp(user.last_seen_at, locale=locale)
            if user.HasField("last_seen_at")
            else "—",
        ),
    ]
    if user.bio:
        pairs.insert(2, ("Bio", user.bio))
    if server:
        pairs.append(("Server", server))
    print(output.detail(pairs, title=user.display_name))


def _list(api: Api, options: argparse.Namespace) -> int:
    response = api.users.list_users(
        user_pb2.ListUsersRequest(
            page=common_pb2.PageRequest(limit=options.limit, cursor=options.cursor),
            query=options.query,
            roles=enum_args.USER_ROLE.to_numbers(options.role),
            statuses=enum_args.USER_STATUS.to_numbers(options.status),
            sort_field=enum_args.USER_SORT.to_number(options.sort),
            sort_direction=enum_args.SORT_DIRECTION.to_number("asc" if options.asc else "desc"),
        ),
        headers=api.require_token(),
    )
    if options.json:
        print(output.as_json(response))
        return 0

    locale = options.locale
    print(
        output.table(
            ["ID", "NAME", "EMAIL", "ROLE", "STATUS", "LISTS", "OPEN", "LATE", "LAST SEEN"],
            [
                [
                    output.short_id(user.id),
                    output.truncate(user.display_name, 22),
                    user.email,
                    display.enum_name(enum_args.USER_ROLE.value_name(user.role), locale=locale),
                    display.enum_name(enum_args.USER_STATUS.value_name(user.status), locale=locale),
                    str(user.stats.owned_list_count),
                    str(user.stats.open_task_count),
                    str(user.stats.overdue_task_count) if user.stats.overdue_task_count else "",
                    display.relative_date(user.last_seen_at, locale=locale)
                    if user.HasField("last_seen_at")
                    else "—",
                ]
                for user in response.users
            ],
        )
    )
    if response.page.has_more:
        print()
        print(output.paint(f"Next page: --cursor {response.page.next_cursor}", "dim"))
    return 0


def _get(api: Api, options: argparse.Namespace) -> int:
    if options.id == "me":
        response = api.users.get_current_user(
            user_pb2.GetCurrentUserRequest(), headers=api.require_token()
        )
        user = response.user
        message: Any = response
    else:
        got = api.users.get_user(
            user_pb2.GetUserRequest(id=_resolve_user(api, options.id)),
            headers=api.require_token(),
        )
        user = got.user
        message = got

    if options.json:
        print(output.as_json(message))
    else:
        _print_user(user, locale=options.locale, server=api.config.base_url)
    return 0


def _search(api: Api, options: argparse.Namespace) -> int:
    response = api.users.search_users(
        user_pb2.SearchUsersRequest(query=options.query, limit=options.limit),
        headers=api.require_token(),
    )
    if options.json:
        print(output.as_json(response))
        return 0
    print(
        output.table(
            ["ID", "NAME", "EMAIL"],
            [[output.short_id(u.id), u.display_name, u.email] for u in response.users],
            empty_message="Nobody matches.",
        )
    )
    return 0


def _create(api: Api, options: argparse.Namespace) -> int:
    password = options.password or getpass.getpass(f"Password for {options.email}: ")
    if not password:
        raise CliError("A password is required.")
    response = api.users.create_user(
        user_pb2.CreateUserRequest(
            email=options.email,
            password=password,
            display_name=options.name,
            role=enum_args.USER_ROLE.to_number(options.role),
            locale=enum_args.LOCALE.to_number(options.language),
            time_zone=options.time_zone,
        ),
        headers=api.require_token(),
    )
    if options.json:
        print(output.as_json(response))
    else:
        output.success(f"Created {response.user.email} ({output.short_id(response.user.id)}).")
    return 0


def _update(api: Api, options: argparse.Namespace) -> int:
    request = user_pb2.UpdateUserRequest(id=_resolve_user(api, options.id))
    changed = False
    if options.name is not None:
        request.display_name = options.name
        changed = True
    if options.bio is not None:
        request.bio = options.bio
        changed = True
    if options.avatar_url is not None:
        request.avatar_url = options.avatar_url
        changed = True
    if options.time_zone is not None:
        request.time_zone = options.time_zone
        changed = True
    if options.language is not None:
        request.locale = enum_args.LOCALE.to_number(options.language)
        changed = True
    if options.theme is not None:
        request.theme = enum_args.THEME.to_number(options.theme)
        changed = True
    if options.role is not None:
        request.role = enum_args.USER_ROLE.to_number(options.role)
        changed = True
    if not changed:
        raise CliError("Nothing to change.", hint="Pass at least one of --name/--locale/--theme/…")

    response = api.users.update_user(request, headers=api.require_token())
    if options.json:
        print(output.as_json(response))
    else:
        output.success(f"Updated {response.user.display_name}.")
        # A locale change affects this CLI's own output too.
        if options.language:
            api.config.locale = options.language
            api.config.save()
    return 0


def _set_status(api: Api, options: argparse.Namespace) -> int:
    response = api.users.update_user_status(
        user_pb2.UpdateUserStatusRequest(
            id=_resolve_user(api, options.id),
            status=enum_args.USER_STATUS.to_number(options.status),
            reason=options.reason,
        ),
        headers=api.require_token(),
    )
    if options.json:
        print(output.as_json(response))
    else:
        label = display.enum_name(
            enum_args.USER_STATUS.value_name(response.user.status), locale=options.locale
        )
        output.success(f"{response.user.email} → {label}")
    return 0


def _delete(api: Api, options: argparse.Namespace) -> int:
    user_id = _resolve_user(api, options.id)
    if not options.yes:
        answer = (
            input("Delete this account and every list it owns? This cannot be undone. [y/N] ")
            .strip()
            .lower()
        )
        if answer not in {"y", "yes", "j", "ja"}:
            output.warn("Cancelled.")
            return 1
    api.users.delete_user(user_pb2.DeleteUserRequest(id=user_id), headers=api.require_token())
    if user_id == _safe_me_id(api):
        api.config.clear_token()
        api.config.save()
    if not options.json:
        output.success("Account deleted.")
    return 0


def _safe_me_id(api: Api) -> str | None:
    """The signed-in user's id, or ``None`` if the session is already gone."""
    try:
        return _me(api).id
    except Exception:
        return None
