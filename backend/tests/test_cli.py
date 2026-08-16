"""The CLI's surface and its pure logic.

The CLI talks to a live server over HTTP, so its commands are exercised end to end by
``scripts/cli-coverage.sh`` rather than from here. What *this* file locks down is
everything that can be checked without a socket:

* the command tree — every group and leaf, so a command cannot quietly disappear;
* that every module imports, which is where a bad reference to a generated constant now
  surfaces (``lookup`` resolves its enum values at import time for exactly that reason);
* date parsing and enum-word mapping, which are pure functions with real edge cases.

The gap this closes is concrete: ``lookup.users`` once read ``USER_ROLE_ADMIN`` off
``user_pb2``, where it does not exist, and crashed every command that resolved a user by
id prefix. Nothing imported it, so nothing caught it.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta

import pytest

from todoapp.cli import args as enum_args
from todoapp.cli import client, config, display, lookup, output  # noqa: F401 — import check
from todoapp.cli.commands import auth, lists, tasks, users  # noqa: F401 — import check
from todoapp.cli.main import build_parser

# The full surface, group by group. Adding a command means adding it here, which is the
# point: the list is the contract for what the CLI offers.
EXPECTED_COMMANDS = {
    "auth": {
        "login",
        "register",
        "logout",
        "whoami",
        "refresh",
        "sessions",
        "revoke-session",
        "change-password",
        "forgot-password",
        "reset-password",
        "verify-email",
        "resend-verification",
    },
    "lists": {
        "list",
        "get",
        "create",
        "update",
        "archive",
        "restore",
        "delete",
        "reorder",
        "members",
        "share",
        "set-role",
        "unshare",
        "labels",
        "add-label",
        "update-label",
        "delete-label",
    },
    "tasks": {
        "list",
        "get",
        "create",
        "update",
        "status",
        "done",
        "start",
        "reopen",
        "assign",
        "move",
        "delete",
        "bulk",
        "labels",
        "add-subtask",
        "check",
        "uncheck",
        "delete-subtask",
        "comments",
        "comment",
        "edit-comment",
        "delete-comment",
        "activity",
    },
    "users": {"list", "get", "search", "create", "update", "set-status", "delete"},
    "config": {"show", "set", "path"},
}


def _subparsers(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    """Returns a parser's subcommands, keyed by name (aliases included)."""
    # argparse exposes no public accessor for a parser's subcommands.
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    return {}


def test_every_group_is_registered() -> None:
    groups = _subparsers(build_parser())
    for name in EXPECTED_COMMANDS:
        assert name in groups, f"group {name} is missing"


@pytest.mark.parametrize("group", sorted(EXPECTED_COMMANDS))
def test_every_command_is_registered(group: str) -> None:
    commands = set(_subparsers(_subparsers(build_parser())[group]))
    missing = EXPECTED_COMMANDS[group] - commands
    assert not missing, f"{group} is missing: {sorted(missing)}"


@pytest.mark.parametrize("group", sorted(EXPECTED_COMMANDS))
def test_every_command_has_a_handler(group: str) -> None:
    """A command with no handler parses fine and then does nothing."""
    for name, parser in _subparsers(_subparsers(build_parser())[group]).items():
        assert parser.get_default("handler") is not None, f"{group} {name} has no handler"


@pytest.mark.parametrize("group", sorted(EXPECTED_COMMANDS))
def test_every_command_accepts_the_global_flags(group: str) -> None:
    """`todoapp tasks list --json` has to work, not just `todoapp --json tasks list`."""
    for name, parser in _subparsers(_subparsers(build_parser())[group]).items():
        flags = {option for action in parser._actions for option in action.option_strings}
        for flag in ("--json", "--locale", "--server"):
            assert flag in flags, f"{group} {name} does not accept {flag}"


def test_total_command_count() -> None:
    """Guards against a group being registered but left empty."""
    total = sum(len(commands) for commands in EXPECTED_COMMANDS.values())
    assert total == 60


# --- Enum words --------------------------------------------------------------


def test_enum_words_are_derived_from_the_proto() -> None:
    assert enum_args.TASK_STATUS.choices == [
        "todo",
        "in-progress",
        "blocked",
        "done",
        "cancelled",
    ]
    # Least to most urgent, matching the proto and the PostgreSQL type.
    assert enum_args.TASK_PRIORITY.choices == ["none", "low", "medium", "high", "urgent"]


def test_enum_word_round_trip() -> None:
    for argument in (enum_args.TASK_STATUS, enum_args.MEMBER_ROLE, enum_args.USER_ROLE):
        for word in argument.choices:
            number = argument.to_number(word)
            assert argument.word(number) == word
            assert argument.value_name(number).endswith(word.upper().replace("-", "_"))


def test_enum_word_rejects_nonsense() -> None:
    with pytest.raises(ValueError, match="not a valid TaskStatus"):
        enum_args.TASK_STATUS.to_number("teleported")


def test_admin_role_constant_resolves() -> None:
    """The exact reference that used to crash `lookup.users`."""
    assert enum_args.USER_ROLE.to_number("admin") > 0


# --- Date parsing ------------------------------------------------------------


def test_date_words() -> None:
    today = datetime.now().astimezone().date()
    assert tasks.parse_date("none") is None
    assert tasks.parse_date("") is None

    tomorrow = tasks.parse_date("tomorrow")
    assert tomorrow is not None
    assert tomorrow.ToDatetime(tzinfo=UTC).astimezone().date() == today + timedelta(days=1)

    yesterday = tasks.parse_date("yesterday")
    assert yesterday is not None
    assert yesterday.ToDatetime(tzinfo=UTC).astimezone().date() == today - timedelta(days=1)


def test_monday_always_moves_forward() -> None:
    """Asking for Monday on a Monday means *next* Monday, not today."""
    stamp = tasks.parse_date("monday")
    assert stamp is not None
    when = stamp.ToDatetime(tzinfo=UTC).astimezone()
    assert when.weekday() == 0
    assert when.date() > datetime.now().astimezone().date()


def test_bare_date_lands_at_nine() -> None:
    """An all-day task due "Tuesday" must not read as overdue at 00:01."""
    stamp = tasks.parse_date("2027-03-14")
    assert stamp is not None
    assert stamp.ToDatetime(tzinfo=UTC).astimezone().hour == 9


def test_explicit_time_is_kept() -> None:
    stamp = tasks.parse_date("2027-03-14T17:30")
    assert stamp is not None
    local = stamp.ToDatetime(tzinfo=UTC).astimezone()
    assert (local.hour, local.minute) == (17, 30)


def test_nonsense_date_is_a_cli_error() -> None:
    with pytest.raises(client.CliError):
        tasks.parse_date("næste tirsdag")


# --- Id prefix resolution ----------------------------------------------------


def test_prefix_resolution() -> None:
    candidates = {"4f2c1234-aaaa": "Køb mælk", "9b7e5678-bbbb": "Betal husleje"}
    assert client.resolve_id("4f2c", candidates, kind="task") == "4f2c1234-aaaa"
    # A full id passes straight through.
    assert client.resolve_id("9b7e5678-bbbb", candidates, kind="task") == "9b7e5678-bbbb"


def test_ambiguous_prefix_is_refused() -> None:
    """Guessing between two matches would eventually delete the wrong thing."""
    candidates = {"4f2c1111": "One", "4f2c2222": "Two"}
    with pytest.raises(client.CliError, match="matches 2 tasks"):
        client.resolve_id("4f2c", candidates, kind="task")


def test_unknown_prefix_is_refused() -> None:
    with pytest.raises(client.CliError, match="No task matches"):
        client.resolve_id("zzzz", {"4f2c1111": "One"}, kind="task")


# --- Display -----------------------------------------------------------------


def test_enum_names_exist_in_both_locales() -> None:
    """A raw enum name must never reach the terminal."""
    for argument in (
        enum_args.TASK_STATUS,
        enum_args.TASK_PRIORITY,
        enum_args.MEMBER_ROLE,
        enum_args.USER_ROLE,
        enum_args.USER_STATUS,
        enum_args.LIST_VISIBILITY,
        enum_args.LIST_COLOR,
        enum_args.RECURRENCE,
        enum_args.SESSION_CLIENT,
        enum_args.LOCALE,
        enum_args.THEME,
        enum_args.ACTIVITY_ACTION,
    ):
        for word in argument.choices:
            name = argument.value_name(argument.to_number(word))
            for locale in ("da", "en"):
                label = display.enum_name(name, locale=locale)
                assert label != name, f"{name} has no {locale} display name"


def test_unknown_locale_falls_back_to_danish() -> None:
    assert display.locale_or_default("de") == "da"
    assert display.locale_or_default(None) == "da"
    assert display.locale_or_default("en-GB") == "en"


def test_truncate_keeps_within_width() -> None:
    assert output.truncate("kort", 10) == "kort"
    long = output.truncate("en meget lang opgavetitel der ikke passer", 12)
    assert len(long) <= 12
    assert long.endswith("…")
