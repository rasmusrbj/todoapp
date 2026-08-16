"""The CLI's `--json` contract.

The CLI is meant to be driven by programs as well as people — scripts, CI, and coding
agents. That only works if the machine-readable mode is machine-readable on *every*
path, including the failures, so a caller never has to fall back to matching localized
prose.

The contract, and what each test here pins:

* exit 0 → the payload on stdout, nothing on stderr;
* non-zero → nothing on stdout, exactly one JSON object on stderr;
* that object carries `reason` — a stable `todo.v1.ErrorReason` name — whenever the
  failure maps onto one, because `message` is localized and may be reworded;
* exit codes mean something: 2 bad usage, 3 not allowed, 1 everything else.

These run the parser and the error renderers directly rather than spawning a process, so
they need no server. `scripts/cli-coverage.sh` covers the live side.
"""

from __future__ import annotations

import argparse
import json

import pytest
from connectrpc.errors import ConnectError

from todo.v1.errors_pb2 import ErrorReason
from todoapp.cli import client, output
from todoapp.cli.config import Config
from todoapp.cli.main import build_parser
from todoapp.errors import invalid_argument, not_found, permission_denied


def parse_error(captured: str) -> dict[str, object]:
    """The error object out of a captured stderr, failing loudly if it is not JSON."""
    payload = json.loads(captured)
    assert set(payload) == {"error"}, f"unexpected top level: {list(payload)}"
    error = payload["error"]
    assert isinstance(error, dict)
    return error


# --- Shape -------------------------------------------------------------------


def test_json_error_is_one_object_on_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    output.fail("something went wrong", as_json_output=True, exit_code=1)
    captured = capsys.readouterr()
    assert captured.out == "", "a failure must not write to stdout"
    error = parse_error(captured.err)
    assert error["message"] == "something went wrong"
    assert error["exit_code"] == 1


def test_human_mode_is_unchanged(capsys: pytest.CaptureFixture[str]) -> None:
    """The prose form is what a person sees; it must not become JSON for everyone."""
    output.fail("something went wrong", as_json_output=False, hint="try this")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "something went wrong" in captured.err
    assert "try this" in captured.err
    with pytest.raises(json.JSONDecodeError):
        json.loads(captured.err)


def test_optional_fields_are_omitted_rather_than_null(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`"field": null` forces every consumer to handle two empty cases."""
    output.fail("plain", as_json_output=True)
    error = parse_error(capsys.readouterr().err)
    assert set(error) == {"message", "exit_code"}


def test_all_fields_survive(capsys: pytest.CaptureFixture[str]) -> None:
    output.fail(
        "too long",
        as_json_output=True,
        reason="ERROR_REASON_FIELD_TOO_LONG",
        field="title",
        metadata={"max_length": "200"},
        hint="shorten it",
        exit_code=1,
    )
    error = parse_error(capsys.readouterr().err)
    assert error["reason"] == "ERROR_REASON_FIELD_TOO_LONG"
    assert error["field"] == "title"
    assert error["metadata"] == {"max_length": "200"}
    assert error["hint"] == "shorten it"


# --- Server failures ---------------------------------------------------------


def die_json(error: ConnectError, capsys: pytest.CaptureFixture[str]) -> tuple[dict, int]:
    """Runs `client.die` in JSON mode and returns the object plus the exit code."""
    with pytest.raises(SystemExit) as exit_info:
        client.die(error, as_json_output=True)
    return parse_error(capsys.readouterr().err), int(exit_info.value.code or 0)


def test_a_server_reason_reaches_the_caller(capsys: pytest.CaptureFixture[str]) -> None:
    """The whole point: branch on `reason`, not on the sentence."""
    error, code = die_json(
        not_found(ErrorReason.ERROR_REASON_TASK_NOT_FOUND, "no such task"), capsys
    )
    assert error["reason"] == "ERROR_REASON_TASK_NOT_FOUND"
    assert code == 1


def test_the_field_at_fault_is_named(capsys: pytest.CaptureFixture[str]) -> None:
    error, _ = die_json(
        invalid_argument(ErrorReason.ERROR_REASON_INVALID_EMAIL, "bad address", field="email"),
        capsys,
    )
    assert error["field"] == "email"
    assert error["reason"] == "ERROR_REASON_INVALID_EMAIL"


def test_metadata_comes_through(capsys: pytest.CaptureFixture[str]) -> None:
    """`max_length` and friends are how a caller can correct itself and retry."""
    error, _ = die_json(
        invalid_argument(
            ErrorReason.ERROR_REASON_FIELD_TOO_LONG,
            "too long",
            field="title",
            metadata={"max_length": "200"},
        ),
        capsys,
    )
    assert error["metadata"] == {"max_length": "200"}


def test_the_json_message_is_not_decorated(capsys: pytest.CaptureFixture[str]) -> None:
    """The human form appends "(REASON)" and "[field]". A program wants neither."""
    error, _ = die_json(
        invalid_argument(ErrorReason.ERROR_REASON_INVALID_EMAIL, "bad address", field="email"),
        capsys,
    )
    assert error["message"] == "bad address"
    assert "ERROR_REASON" not in str(error["message"])
    assert "[" not in str(error["message"])


# --- Exit codes --------------------------------------------------------------


@pytest.mark.parametrize(
    "reason",
    [
        ErrorReason.ERROR_REASON_NOT_AUTHENTICATED,
        ErrorReason.ERROR_REASON_SESSION_EXPIRED,
        ErrorReason.ERROR_REASON_PERMISSION_DENIED,
        ErrorReason.ERROR_REASON_ADMIN_REQUIRED,
        ErrorReason.ERROR_REASON_OWNER_REQUIRED,
    ],
)
def test_not_allowed_exits_three(
    reason: ErrorReason.ValueType, capsys: pytest.CaptureFixture[str]
) -> None:
    """3 tells a caller that signing in or asking for access would fix it."""
    error, code = die_json(permission_denied(reason, "nope"), capsys)
    assert code == 3
    assert error["exit_code"] == 3


def test_not_signed_in_exits_three(capsys: pytest.CaptureFixture[str]) -> None:
    """This path is a local `CliError`, and it used to exit 1 while the docs said 3."""
    api = client.build(Config(base_url="http://127.0.0.1:8081", token=None, locale="en"))
    with pytest.raises(client.CliError) as raised:
        api.require_token()
    assert raised.value.exit_code == 3
    assert raised.value.reason == "ERROR_REASON_NOT_AUTHENTICATED"


def test_a_locally_detected_not_found_still_carries_a_reason() -> None:
    """So a caller branches on one field whether the check ran here or on the server."""
    with pytest.raises(client.CliError) as raised:
        client.resolve_id("zzzz", {"4f2c1111": "One"}, kind="task")
    assert raised.value.reason == "ERROR_REASON_TASK_NOT_FOUND"


def test_an_ambiguous_prefix_has_no_reason() -> None:
    """There is no server reason for "half an id that fits two things"."""
    with pytest.raises(client.CliError) as raised:
        client.resolve_id("4f2c", {"4f2c1111": "One", "4f2c2222": "Two"}, kind="task")
    assert raised.value.reason is None
    assert raised.value.exit_code == 2 or raised.value.exit_code == 1


# --- Usage errors ------------------------------------------------------------


def test_a_bad_flag_is_json_when_json_was_asked_for(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`argparse` exits before any handler runs, so this was the last prose hole."""
    monkeypatch.setattr("sys.argv", ["todoapp", "lists", "list", "--nope", "--json"])
    with pytest.raises(SystemExit) as exit_info:
        build_parser().parse_args(["lists", "list", "--nope", "--json"])
    assert int(exit_info.value.code or 0) == 2
    error = parse_error(capsys.readouterr().err)
    assert error["exit_code"] == 2
    assert "--nope" in str(error["message"])


def test_a_bad_flag_stays_prose_without_json(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.argv", ["todoapp", "lists", "list", "--nope"])
    with pytest.raises(SystemExit):
        build_parser().parse_args(["lists", "list", "--nope"])
    captured = capsys.readouterr().err
    assert "usage:" in captured
    with pytest.raises(json.JSONDecodeError):
        json.loads(captured)


# --- Discoverability ---------------------------------------------------------


def test_every_command_accepts_json() -> None:
    """A program should never have to know which subcommands support the flag."""
    root = build_parser()
    groups = [action for action in root._actions if isinstance(action, argparse._SubParsersAction)]
    assert groups, "no subcommands found"
    missing: list[str] = []
    for group in groups:
        for group_name, group_parser in group.choices.items():
            for sub in group_parser._actions:
                if not isinstance(sub, argparse._SubParsersAction):
                    continue
                for name, leaf in sub.choices.items():
                    flags = {option for action in leaf._actions for option in action.option_strings}
                    if "--json" not in flags:
                        missing.append(f"{group_name} {name}")
    assert not missing, f"commands without --json: {missing}"
