"""Terminal rendering: tables, key-value blocks, and machine-readable output.

Two modes. The default is a human table sized to the content; ``--json`` emits the
proto message as JSON so the CLI composes with ``jq`` and shell pipelines. Colour is
suppressed when stdout is not a TTY or ``NO_COLOR`` is set, so redirected output
stays clean.
"""

from __future__ import annotations

import json
import os
import sys
import unicodedata
from collections.abc import Iterable, Sequence
from typing import Any, Final

from google.protobuf.json_format import MessageToDict
from google.protobuf.message import Message

_ANSI: Final[dict[str, str]] = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
}


def colour_enabled() -> bool:
    """Whether to emit ANSI escapes."""
    return sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def paint(text: str, style: str) -> str:
    """Wraps ``text`` in an ANSI style, or returns it unchanged."""
    if not colour_enabled() or style not in _ANSI:
        return text
    return f"{_ANSI[style]}{text}{_ANSI['reset']}"


def _display_width(text: str) -> int:
    """Returns the column width of ``text``.

    Danish content is narrow, but a task title may hold an emoji or CJK character;
    counting those as one column misaligns every row after it.
    """
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - _display_width(text))


def table(
    headers: Sequence[str],
    rows: Iterable[Sequence[str]],
    *,
    empty_message: str = "Nothing here.",
) -> str:
    """Renders a plain table, sized to its content.

    No borders — a header row, a rule, and the data. Borders cost horizontal space
    that task titles need more.
    """
    materialised = [[str(cell) for cell in row] for row in rows]
    if not materialised:
        return paint(empty_message, "dim")

    widths = [_display_width(header) for header in headers]
    for row in materialised:
        for index, cell in enumerate(row):
            if index < len(widths):
                widths[index] = max(widths[index], _display_width(cell))

    lines = [
        "  ".join(paint(_pad(header, widths[i]), "bold") for i, header in enumerate(headers)),
        paint("  ".join("─" * width for width in widths), "dim"),
    ]
    lines += [
        "  ".join(_pad(cell, widths[i]) for i, cell in enumerate(row)) for row in materialised
    ]
    return "\n".join(lines)


def detail(pairs: Sequence[tuple[str, str]], *, title: str | None = None) -> str:
    """Renders a key-value block for a single record."""
    lines: list[str] = []
    if title:
        lines += [paint(title, "bold"), ""]
    label_width = max((_display_width(label) for label, _ in pairs), default=0)
    lines += [f"{paint(_pad(label, label_width), 'dim')}  {value}" for label, value in pairs]
    return "\n".join(lines)


def as_json(message: Message) -> str:
    """Serialises a proto message to indented JSON.

    ``preserving_proto_field_name`` keeps ``due_at`` rather than ``dueAt``, which is
    what a shell script reading the schema would expect, and enum values stay as
    their names so the output is self-describing.
    """
    return json.dumps(
        MessageToDict(
            message,
            preserving_proto_field_name=True,
            always_print_fields_with_no_presence=True,
        ),
        indent=2,
        ensure_ascii=False,
    )


def emit(message: Message | None, human: str, *, as_json_output: bool) -> None:
    """Prints either the JSON form or the prepared human form."""
    if as_json_output and message is not None:
        print(as_json(message))
    else:
        print(human)


def success(text: str) -> None:
    """Prints a confirmation line."""
    print(f"{paint('✓', 'green')} {text}")


def warn(text: str) -> None:
    """Prints a warning to stderr."""
    print(f"{paint('!', 'yellow')} {text}", file=sys.stderr)


def error(text: str) -> None:
    """Prints an error to stderr."""
    print(f"{paint('✗', 'red')} {text}", file=sys.stderr)


def truncate(text: str, width: int) -> str:
    """Shortens ``text`` to ``width`` columns, ending with an ellipsis."""
    if _display_width(text) <= width:
        return text
    out: list[str] = []
    used = 0
    for ch in text:
        step = 2 if unicodedata.east_asian_width(ch) in "WF" else 1
        if used + step > width - 1:
            break
        out.append(ch)
        used += step
    return "".join(out) + "…"


def short_id(value: str) -> str:
    """Returns a UUID's first segment, enough to recognise a row by eye.

    Commands accept these prefixes, so the shortened form stays usable as input.
    """
    return value.split("-")[0] if value else ""


def json_payload(data: Any) -> str:
    """Serialises plain Python data for the ``--json`` form of a non-proto result."""
    return json.dumps(data, indent=2, ensure_ascii=False)


def json_error(
    message: str,
    *,
    reason: str | None = None,
    field: str | None = None,
    metadata: dict[str, str] | None = None,
    hint: str | None = None,
    exit_code: int = 1,
) -> str:
    """Renders a failure as JSON, for `--json` callers that are programs.

    Without this, `--json` printed a machine-readable payload on success and human
    prose on failure — so anything driving the CLI had to parse two formats, and the
    one it needed most was the prose. The contract is now:

    * exit 0 → the payload on stdout, nothing on stderr;
    * non-zero → nothing on stdout, one JSON object on stderr.

    Errors go to stderr rather than stdout on purpose. A command that has already
    written part of a payload and then fails would otherwise leave two concatenated
    objects on stdout, which is not parseable JSON at all.

    `reason` is the `todo.v1.ErrorReason` name, and it is the field to branch on:
    it is stable, while `message` is localized and may be reworded.
    """
    body: dict[str, Any] = {"message": message, "exit_code": exit_code}
    if reason:
        body["reason"] = reason
    if field:
        body["field"] = field
    if metadata:
        body["metadata"] = dict(metadata)
    if hint:
        body["hint"] = hint
    return json.dumps({"error": body}, indent=2, ensure_ascii=False)


def fail(
    message: str,
    *,
    as_json_output: bool,
    reason: str | None = None,
    field: str | None = None,
    metadata: dict[str, str] | None = None,
    hint: str | None = None,
    exit_code: int = 1,
) -> None:
    """Prints a failure in whichever form the caller asked for."""
    if as_json_output:
        print(
            json_error(
                message,
                reason=reason,
                field=field,
                metadata=metadata,
                hint=hint,
                exit_code=exit_code,
            ),
            file=sys.stderr,
        )
        return
    error(message)
    if hint:
        print(f"  {paint(hint, 'dim')}", file=sys.stderr)
