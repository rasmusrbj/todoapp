"""Request validation.

Every check here mirrors a ``CHECK`` constraint or column type in
``0001_init.sql``. The database is the last line of defence, but a constraint
violation surfaces as an opaque ``INTERNAL``; validating first is what turns it
into an ``INVALID_ARGUMENT`` naming the offending field, which is what a form needs
to highlight the right input.
"""

from __future__ import annotations

import re
import uuid
import zoneinfo
from typing import Final

from todoapp.errors import Reason, invalid_argument

# Deliberately permissive: the authority on whether an address exists is a
# delivered verification email, not a regular expression. This only rejects input
# that cannot be an address at all.
_EMAIL_PATTERN: Final = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")

MAX_EMAIL_LENGTH: Final = 254

# Field length ceilings, matching the CHECK constraints in the schema.
MAX_DISPLAY_NAME: Final = 80
MAX_BIO: Final = 500
MAX_URL: Final = 2048
MAX_LIST_NAME: Final = 120
MAX_LIST_DESCRIPTION: Final = 2000
MAX_LABEL_NAME: Final = 40
MAX_TASK_TITLE: Final = 200
MAX_TASK_DESCRIPTION: Final = 10000
MAX_COMMENT_BODY: Final = 5000
MAX_STATUS_REASON: Final = 500
MAX_ESTIMATE_MINUTES: Final = 100_000
MAX_RECURRENCE_INTERVAL: Final = 365
MAX_SUBTASKS_PER_CREATE: Final = 50
MAX_BULK_TASK_IDS: Final = 200


def required_text(value: str, *, field: str, max_length: int) -> str:
    """Trims ``value`` and requires it to be non-empty and within ``max_length``.

    Returns:
        The trimmed value, which is what should be stored.

    Raises:
        ConnectError: ``INVALID_ARGUMENT`` if empty or too long.
    """
    trimmed = value.strip()
    if not trimmed:
        raise invalid_argument(
            Reason.ERROR_REASON_FIELD_REQUIRED, f"{field} is required", field=field
        )
    return _check_length(trimmed, field=field, max_length=max_length)


def optional_text(value: str, *, field: str, max_length: int) -> str:
    """Trims ``value``, allowing empty, and enforces ``max_length``."""
    return _check_length(value.strip(), field=field, max_length=max_length)


def _check_length(value: str, *, field: str, max_length: int) -> str:
    if len(value) > max_length:
        raise invalid_argument(
            Reason.ERROR_REASON_FIELD_TOO_LONG,
            f"{field} must be at most {max_length} characters",
            field=field,
            metadata={"max_length": str(max_length)},
        )
    return value


def email(value: str, *, field: str = "email") -> str:
    """Normalises and validates an email address.

    Returns:
        The address lower-cased and trimmed. The column is ``citext``, so casing
        does not affect uniqueness, but storing one form keeps logs readable.

    Raises:
        ConnectError: ``INVALID_ARGUMENT`` if the address is unusable.
    """
    trimmed = value.strip().lower()
    if not trimmed:
        raise invalid_argument(Reason.ERROR_REASON_FIELD_REQUIRED, "email is required", field=field)
    if len(trimmed) > MAX_EMAIL_LENGTH or not _EMAIL_PATTERN.match(trimmed):
        raise invalid_argument(
            Reason.ERROR_REASON_INVALID_EMAIL, "email address is not valid", field=field
        )
    return trimmed


def uuid_value(value: str, *, field: str) -> str:
    """Validates a UUID and returns it in canonical form.

    Catching this here matters: passing a non-UUID string into a ``uuid`` column
    aborts the whole transaction with a cast error, which would turn a typo in a
    URL into a 500.

    Raises:
        ConnectError: ``INVALID_ARGUMENT`` if the value is not a UUID.
    """
    trimmed = value.strip()
    if not trimmed:
        raise invalid_argument(
            Reason.ERROR_REASON_FIELD_REQUIRED, f"{field} is required", field=field
        )
    try:
        return str(uuid.UUID(trimmed))
    except ValueError as err:
        raise invalid_argument(
            Reason.ERROR_REASON_VALIDATION_FAILED, f"{field} is not a valid id", field=field
        ) from err


def uuid_values(values: object, *, field: str, max_count: int) -> list[str]:
    """Validates a repeated id field, de-duplicating while preserving order.

    Raises:
        ConnectError: ``INVALID_ARGUMENT`` if any id is malformed or there are too
            many. An unbounded id list is a cheap way to make one request expensive.
    """
    items = [str(item) for item in values]  # type: ignore[call-overload]
    if len(items) > max_count:
        raise invalid_argument(
            Reason.ERROR_REASON_FIELD_TOO_LONG,
            f"{field} accepts at most {max_count} ids",
            field=field,
            metadata={"max_count": str(max_count)},
        )
    seen: dict[str, None] = {}
    for item in items:
        seen[uuid_value(item, field=field)] = None
    return list(seen)


def time_zone(value: str, *, field: str = "time_zone", default: str = "Europe/Copenhagen") -> str:
    """Validates an IANA time-zone name, falling back to ``default`` when empty.

    The zone decides what "today" and "overdue" mean for a user, so an unknown one
    has to be rejected rather than silently treated as UTC.

    Raises:
        ConnectError: ``INVALID_ARGUMENT`` if the zone is unknown.
    """
    trimmed = value.strip()
    if not trimmed:
        return default
    try:
        zoneinfo.ZoneInfo(trimmed)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError) as err:
        raise invalid_argument(
            Reason.ERROR_REASON_INVALID_TIME_ZONE,
            f"{trimmed} is not a known time zone",
            field=field,
        ) from err
    return trimmed


def bounded_int(value: int, *, field: str, minimum: int, maximum: int) -> int:
    """Requires ``minimum <= value <= maximum``.

    Raises:
        ConnectError: ``INVALID_ARGUMENT`` if out of range.
    """
    if not minimum <= value <= maximum:
        raise invalid_argument(
            Reason.ERROR_REASON_VALIDATION_FAILED,
            f"{field} must be between {minimum} and {maximum}",
            field=field,
            metadata={"min": str(minimum), "max": str(maximum)},
        )
    return value


def url(value: str, *, field: str) -> str:
    """Validates an optional http(s) URL.

    Raises:
        ConnectError: ``INVALID_ARGUMENT`` for a non-http scheme. Rejecting
            ``javascript:`` and ``data:`` here stops a stored avatar URL from
            becoming an injection vector in whichever client renders it.
    """
    trimmed = optional_text(value, field=field, max_length=MAX_URL)
    if trimmed and not trimmed.startswith(("http://", "https://")):
        raise invalid_argument(
            Reason.ERROR_REASON_VALIDATION_FAILED,
            f"{field} must be an http or https URL",
            field=field,
        )
    return trimmed
