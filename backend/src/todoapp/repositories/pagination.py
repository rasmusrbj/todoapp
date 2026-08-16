"""Cursor pagination shared by every listing RPC.

The cursor is opaque to clients — deliberately, because it currently encodes an
offset and will later encode a keyset without that being a breaking change. Only
this module may look inside one.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from typing import Final

from todo.v1.common_pb2 import PageRequest, PageResponse
from todoapp.errors import Reason, invalid_argument

DEFAULT_LIMIT: Final = 25
MAX_LIMIT: Final = 100
_CURSOR_VERSION: Final = "o1"


@dataclass(frozen=True, slots=True)
class Page:
    """A resolved, clamped window over a result set."""

    limit: int
    offset: int

    @property
    def sql_limit(self) -> int:
        """One more row than asked for, so ``has_more`` needs no second query."""
        return self.limit + 1


def encode_cursor(offset: int) -> str:
    """Encodes ``offset`` as an opaque cursor."""
    raw = f"{_CURSOR_VERSION}:{offset}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> int:
    """Decodes a cursor produced by :func:`encode_cursor`.

    Raises:
        ConnectError: ``INVALID_ARGUMENT`` if the cursor is not one of ours. A
            client must treat a cursor as opaque, so a malformed one is a bug
            rather than something to silently recover from.
    """
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        version, _, offset = base64.urlsafe_b64decode(padded).decode().partition(":")
        if version != _CURSOR_VERSION:
            raise ValueError(f"unsupported cursor version {version!r}")
        parsed = int(offset)
    except (binascii.Error, UnicodeDecodeError, ValueError) as err:
        raise invalid_argument(
            Reason.ERROR_REASON_VALIDATION_FAILED, "cursor is not valid", field="page.cursor"
        ) from err
    if parsed < 0:
        raise invalid_argument(
            Reason.ERROR_REASON_VALIDATION_FAILED, "cursor is not valid", field="page.cursor"
        )
    return parsed


def resolve_page(request: PageRequest | None) -> Page:
    """Turns a :class:`PageRequest` into a clamped :class:`Page`.

    A zero or absent limit means the default; anything above :data:`MAX_LIMIT` is
    clamped rather than rejected, so a client asking for too much still gets a
    useful answer.
    """
    if request is None:
        return Page(limit=DEFAULT_LIMIT, offset=0)

    limit = DEFAULT_LIMIT if request.limit <= 0 else min(request.limit, MAX_LIMIT)
    offset = decode_cursor(request.cursor) if request.cursor else 0
    return Page(limit=limit, offset=offset)


def trim(rows: list[dict[str, object]], page: Page) -> tuple[list[dict[str, object]], bool]:
    """Drops the sentinel row fetched by :attr:`Page.sql_limit`.

    Returns:
        The rows to return, and whether a further page exists.
    """
    has_more = len(rows) > page.limit
    return (rows[: page.limit], has_more) if has_more else (rows, False)


def page_response(page: Page, *, total_count: int, has_more: bool) -> PageResponse:
    """Builds the :class:`PageResponse` for a page that has already been trimmed."""
    return PageResponse(
        next_cursor=encode_cursor(page.offset + page.limit) if has_more else "",
        total_count=total_count,
        has_more=has_more,
    )
