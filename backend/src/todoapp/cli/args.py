"""Turning command-line words into proto enum values.

On the wire an enum value is ``TASK_STATUS_IN_PROGRESS``. Nobody wants to type that,
so the CLI accepts the short form — ``in-progress`` — and derives the mapping from
the generated descriptor, exactly as the server derives its PostgreSQL labels. The
short forms therefore cannot drift from the contract, and ``--help`` lists whatever
the current proto defines.
"""

from __future__ import annotations

import argparse
import re
from typing import Final

from google.protobuf.descriptor import EnumDescriptor

from todo.v1 import enums_pb2

_CAMEL_BOUNDARY: Final = re.compile(r"(?<!^)(?=[A-Z])")


class EnumArgument:
    """Maps between a short command-line word and one proto enum.

    Attributes:
        choices: The accepted words, in the proto's declaration order — which is
            also a meaningful order for ``task-priority`` and ``member-role``.
    """

    def __init__(self, descriptor: EnumDescriptor) -> None:
        """Builds the mapping from ``descriptor``, skipping the zero sentinel."""
        prefix = f"{_CAMEL_BOUNDARY.sub('_', descriptor.name).upper()}_"
        self._descriptor = descriptor
        self._by_word: dict[str, int] = {}
        self._by_number: dict[int, str] = {}
        for value in descriptor.values:
            if value.number == 0:
                continue
            word = value.name.removeprefix(prefix).lower().replace("_", "-")
            self._by_word[word] = value.number
            self._by_number[value.number] = word

    @property
    def choices(self) -> list[str]:
        """The accepted words, in declaration order."""
        return list(self._by_word)

    @property
    def metavar(self) -> str:
        """The ``--help`` placeholder, e.g. ``{todo|in-progress|…}``."""
        return "{" + "|".join(self.choices) + "}"

    def to_number(self, word: str) -> int:
        """Converts a command-line word to its enum number.

        Raises:
            ValueError: If the word is not one of :attr:`choices`. argparse normally
                catches this first; the check matters for values read from a file.
        """
        try:
            return self._by_word[word.lower().replace("_", "-")]
        except KeyError:
            raise ValueError(
                f"{word!r} is not a valid {self._descriptor.name}: "
                f"expected one of {', '.join(self.choices)}"
            ) from None

    def to_numbers(self, words: list[str] | None) -> list[int]:
        """Converts a repeated option's words. ``None`` becomes an empty list."""
        return [self.to_number(word) for word in words or []]

    def value_name(self, number: int) -> str:
        """Returns the full proto value name for a number, e.g. ``TASK_STATUS_DONE``.

        This is the key :func:`todoapp.cli.display.enum_name` localizes.
        """
        return self._descriptor.values_by_number[number].name if number else ""

    def word(self, number: int) -> str:
        """Returns the short word for a number, or empty for the sentinel."""
        return self._by_number.get(number, "")


TASK_STATUS: Final = EnumArgument(enums_pb2.TaskStatus.DESCRIPTOR)
TASK_PRIORITY: Final = EnumArgument(enums_pb2.TaskPriority.DESCRIPTOR)
LIST_VISIBILITY: Final = EnumArgument(enums_pb2.ListVisibility.DESCRIPTOR)
LIST_COLOR: Final = EnumArgument(enums_pb2.ListColor.DESCRIPTOR)
MEMBER_ROLE: Final = EnumArgument(enums_pb2.MemberRole.DESCRIPTOR)
USER_ROLE: Final = EnumArgument(enums_pb2.UserRole.DESCRIPTOR)
USER_STATUS: Final = EnumArgument(enums_pb2.UserStatus.DESCRIPTOR)
LOCALE: Final = EnumArgument(enums_pb2.Locale.DESCRIPTOR)
THEME: Final = EnumArgument(enums_pb2.ThemePreference.DESCRIPTOR)
RECURRENCE: Final = EnumArgument(enums_pb2.RecurrenceFrequency.DESCRIPTOR)
ACTIVITY_ACTION: Final = EnumArgument(enums_pb2.ActivityAction.DESCRIPTOR)
TASK_SORT: Final = EnumArgument(enums_pb2.TaskSortField.DESCRIPTOR)
LIST_SORT: Final = EnumArgument(enums_pb2.ListSortField.DESCRIPTOR)
USER_SORT: Final = EnumArgument(enums_pb2.UserSortField.DESCRIPTOR)
SORT_DIRECTION: Final = EnumArgument(enums_pb2.SortDirection.DESCRIPTOR)
SESSION_CLIENT: Final = EnumArgument(enums_pb2.SessionClient.DESCRIPTOR)


# --- Global flags ------------------------------------------------------------

# `--json`, `--locale` and `--server` are accepted both before and after the
# subcommand, because `todoapp tasks list --json` is how anyone would actually type
# it. The flags live on a parent parser that every leaf command inherits.
#
# `default=argparse.SUPPRESS` is what makes this work: the root parser has already
# put its value in the namespace by the time a subparser runs, and a suppressed
# default means an unspecified leaf flag leaves that value alone instead of
# overwriting it with its own default.
GLOBAL_OPTIONS: Final = argparse.ArgumentParser(add_help=False)
GLOBAL_OPTIONS.add_argument(
    "--json",
    action="store_true",
    default=argparse.SUPPRESS,
    help="print the raw response as JSON instead of a table",
)
GLOBAL_OPTIONS.add_argument(
    "--locale",
    choices=["da", "en"],
    default=argparse.SUPPRESS,
    help="language for labels and dates",
)
GLOBAL_OPTIONS.add_argument(
    "--server", default=argparse.SUPPRESS, help="server address, overriding the stored one"
)


class LeafParser(argparse.ArgumentParser):
    """An :class:`argparse.ArgumentParser` that always accepts the global flags.

    Passed as ``parser_class`` to each group's ``add_subparsers`` so no leaf command
    has to remember to inherit them.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Appends :data:`GLOBAL_OPTIONS` to whatever parents were requested."""
        parents = list(kwargs.get("parents") or [])
        kwargs["parents"] = [*parents, GLOBAL_OPTIONS]
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
