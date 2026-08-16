"""``todoapp`` — the command-line client.

Nouns then verbs: ``todoapp tasks list``, ``todoapp tasks get <id>``,
``todoapp lists share <id> --email …``. Every command takes ``--json`` for scripting
and accepts short id prefixes wherever a full id would do.

Exit codes are meant to be branched on:

===  ==========================================================
0    success
1    the request failed, or the user declined a confirmation
2    the command line was wrong (argparse)
3    not signed in, or not allowed
===  ==========================================================
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from typing import NoReturn

from connectrpc.errors import ConnectError

from todoapp import __version__
from todoapp.cli import args as enum_args
from todoapp.cli import client, display, output
from todoapp.cli.commands import auth, lists, tasks, users
from todoapp.cli.config import Config, config_path

_EPILOG = """\
examples:
  todoapp auth login --email you@example.com
  todoapp lists create "Indkøb" --color green
  todoapp tasks add "Køb mælk" --list ind --due tomorrow --priority high
  todoapp tasks list --open --overdue
  todoapp tasks get 4f2c
  todoapp tasks done 4f2c
  todoapp lists share 7a1b --email colleague@example.com --role editor
  todoapp tasks list --json | jq '.tasks[].title'

Ids may be shortened to any unique prefix — the prefixes printed in listings work.
"""


class JsonAwareParser(argparse.ArgumentParser):
    """An `ArgumentParser` whose usage errors respect `--json`.

    `argparse` writes usage text to stderr and exits before any handler runs, so a bad
    flag was the one failure a `--json` caller still received as prose. That is the
    difference between a program that can always parse the CLI's answer and one that
    parses it *usually*.

    `sys.argv` is inspected directly because the failure happens during parsing — there
    is no parsed `--json` yet to consult. Subparsers inherit this class from their
    parent, so the whole command tree is covered by constructing the root with it.
    """

    def error(self, message: str) -> NoReturn:
        """Reports a usage error, as JSON when the caller asked for JSON."""
        if "--json" in sys.argv[1:]:
            output.fail(
                message,
                as_json_output=True,
                hint=f"Run: {self.prog} --help",
                exit_code=2,
            )
            raise SystemExit(2)
        super().error(message)


def build_parser() -> argparse.ArgumentParser:
    """Builds the whole command tree."""
    parser = JsonAwareParser(
        prog="todoapp",
        description="Command-line client for the todo app.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"todoapp {__version__}")
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the raw response as JSON instead of a table",
    )
    parser.add_argument(
        "--locale",
        choices=["da", "en"],
        help="language for labels and dates (default: from your profile)",
    )
    parser.add_argument(
        "--server",
        help="server address, overriding the stored one",
    )

    subparsers = parser.add_subparsers(dest="group", metavar="<group>", required=True)
    auth.register(subparsers)
    lists.register(subparsers)
    tasks.register(subparsers)
    users.register(subparsers)
    _register_config(subparsers)
    return parser


def _register_config(subparsers: argparse._SubParsersAction) -> None:
    """Adds the ``config`` group: inspect and change where the CLI points."""
    parser = subparsers.add_parser(
        "config", help="show or change the CLI's own settings", description="CLI settings."
    )
    commands = parser.add_subparsers(
        dest="config_command",
        metavar="<command>",
        required=True,
        parser_class=enum_args.LeafParser,
    )

    show = commands.add_parser("show", help="show the current settings")
    show.set_defaults(handler=_config_show)

    # `--server` and `--locale` come from the global flags every leaf inherits;
    # here they are persisted rather than applied to one command.
    set_cmd = commands.add_parser("set", help="change a setting; pass --server and/or --locale")
    set_cmd.set_defaults(handler=_config_set)

    commands.add_parser("path", help="print the config file's location").set_defaults(
        handler=_config_path
    )


def _config_show(api: client.Api, options: argparse.Namespace) -> int:
    if options.json:
        print(
            output.json_payload(
                {
                    "base_url": api.config.base_url,
                    "locale": api.config.locale,
                    "signed_in": bool(api.config.token),
                    "email": api.config.email,
                    "config_path": str(config_path()),
                }
            )
        )
        return 0
    print(
        output.detail(
            [
                ("Server", api.config.base_url),
                ("Language", api.config.locale),
                ("Signed in", api.config.email or "no"),
                ("Config file", str(config_path())),
            ]
        )
    )
    return 0


def _config_set(api: client.Api, options: argparse.Namespace) -> int:
    # `options.locale` is always populated by the time a handler runs, so the *raw*
    # value is what says whether the user actually asked for a change.
    if not options.server and not options.requested_locale:
        raise client.CliError("Nothing to set.", hint="Pass --server and/or --locale")
    if options.server:
        api.config.base_url = options.server.rstrip("/")
    if options.requested_locale:
        api.config.locale = options.requested_locale
    path = api.config.save()
    if not options.json:
        output.success(f"Saved to {path}")
    return 0


def _config_path(api: client.Api, options: argparse.Namespace) -> int:
    del api, options
    print(config_path())
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the ``todoapp`` console script.

    Returns:
        The process exit code.
    """
    parser = build_parser()
    options = parser.parse_args(argv)

    config = Config.load()
    if options.server:
        config.base_url = options.server.rstrip("/")
    # Keep the raw request separately: handlers need to tell "the user asked for
    # Danish" apart from "Danish is the stored default".
    options.requested_locale = options.locale
    options.locale = display.locale_or_default(options.locale or config.locale)

    api = client.build(config)
    # Every failure below reports in the same shape the caller asked for. A `--json`
    # caller is a program, and it should never have to parse prose.
    as_json = bool(getattr(options, "json", False))
    try:
        return int(options.handler(api, options))
    except client.CliError as err:
        output.fail(
            str(err),
            as_json_output=as_json,
            reason=err.reason,
            hint=err.hint,
            exit_code=err.exit_code,
        )
        return err.exit_code
    except ConnectError as err:
        client.die(err, locale=options.locale, as_json_output=as_json)
    except ValueError as err:
        # Raised by the enum argument parser for a value argparse could not police,
        # e.g. one read from a file.
        output.fail(str(err), as_json_output=as_json, exit_code=2)
        return 2
    except KeyboardInterrupt:
        if as_json:
            output.fail("Cancelled.", as_json_output=True, exit_code=130)
        else:
            output.warn("Cancelled.")
        return 130
    except OSError as err:
        # A connection refused is the single most common failure in development.
        output.fail(
            f"Cannot reach {config.base_url}: {err}",
            as_json_output=as_json,
            hint="Is the server running? Try: make dev-backend",
            exit_code=1,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
