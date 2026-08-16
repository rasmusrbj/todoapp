"""Localized enum display names and value formatting for the CLI.

Every enum the user can see has a Danish and an English name here. A raw enum name
must never reach the terminal, exactly as it must never reach a web page — and the
strings are kept in parity with ``web/messages/{da,en}.json`` so the CLI and the
browser call the same thing by the same name.

Both languages are written natively rather than translated word-for-word: "Haster"
is what a Dane would actually say, not a rendering of "Urgent".
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Final

from google.protobuf.timestamp_pb2 import Timestamp

# --- Enum display names ------------------------------------------------------

# Keyed by proto enum value name, so a lookup miss is impossible to mistake for a
# real label. Mirrors the `enums` namespace in the web message catalogues.
_NAMES: Final[dict[str, dict[str, str]]] = {
    "da": {
        "TASK_STATUS_TODO": "Ikke startet",
        "TASK_STATUS_IN_PROGRESS": "I gang",
        "TASK_STATUS_BLOCKED": "Blokeret",
        "TASK_STATUS_DONE": "Færdig",
        "TASK_STATUS_CANCELLED": "Droppet",
        "TASK_PRIORITY_NONE": "Ingen",
        "TASK_PRIORITY_LOW": "Lav",
        "TASK_PRIORITY_MEDIUM": "Mellem",
        "TASK_PRIORITY_HIGH": "Høj",
        "TASK_PRIORITY_URGENT": "Haster",
        "LIST_VISIBILITY_PRIVATE": "Privat",
        "LIST_VISIBILITY_SHARED": "Delt",
        "LIST_VISIBILITY_PUBLIC": "Offentlig",
        "LIST_COLOR_ZINC": "Grå",
        "LIST_COLOR_RED": "Rød",
        "LIST_COLOR_AMBER": "Gul",
        "LIST_COLOR_GREEN": "Grøn",
        "LIST_COLOR_BLUE": "Blå",
        "LIST_COLOR_VIOLET": "Lilla",
        "LIST_COLOR_PINK": "Pink",
        "MEMBER_ROLE_OWNER": "Ejer",
        "MEMBER_ROLE_EDITOR": "Redaktør",
        "MEMBER_ROLE_COMMENTER": "Kommentator",
        "MEMBER_ROLE_VIEWER": "Læser",
        "USER_ROLE_MEMBER": "Medlem",
        "USER_ROLE_ADMIN": "Administrator",
        "USER_STATUS_PENDING_VERIFICATION": "Afventer bekræftelse",
        "USER_STATUS_ACTIVE": "Aktiv",
        "USER_STATUS_SUSPENDED": "Spærret",
        "USER_STATUS_DEACTIVATED": "Lukket",
        "LOCALE_DA": "Dansk",
        "LOCALE_EN": "Engelsk",
        "THEME_PREFERENCE_SYSTEM": "Følg systemet",
        "THEME_PREFERENCE_LIGHT": "Lyst",
        "THEME_PREFERENCE_DARK": "Mørkt",
        "RECURRENCE_FREQUENCY_NONE": "Gentages ikke",
        "RECURRENCE_FREQUENCY_DAILY": "Dagligt",
        "RECURRENCE_FREQUENCY_WEEKLY": "Ugentligt",
        "RECURRENCE_FREQUENCY_MONTHLY": "Månedligt",
        "RECURRENCE_FREQUENCY_YEARLY": "Årligt",
        "SESSION_CLIENT_WEB": "Web",
        "SESSION_CLIENT_MOBILE": "Mobil",
        "SESSION_CLIENT_CLI": "Terminal",
        "ACTIVITY_ACTION_CREATED": "oprettede",
        "ACTIVITY_ACTION_UPDATED": "ændrede",
        "ACTIVITY_ACTION_STATUS_CHANGED": "flyttede status på",
        "ACTIVITY_ACTION_ASSIGNED": "tildelte",
        "ACTIVITY_ACTION_UNASSIGNED": "fjernede tildeling på",
        "ACTIVITY_ACTION_COMMENTED": "kommenterede på",
        "ACTIVITY_ACTION_ARCHIVED": "arkiverede",
        "ACTIVITY_ACTION_RESTORED": "genåbnede",
        "ACTIVITY_ACTION_DELETED": "slettede",
        "ACTIVITY_ACTION_MEMBER_ADDED": "gav adgang til",
        "ACTIVITY_ACTION_MEMBER_REMOVED": "fjernede adgang for",
        "ACTIVITY_ACTION_MEMBER_ROLE_CHANGED": "ændrede rollen for",
    },
    "en": {
        "TASK_STATUS_TODO": "To do",
        "TASK_STATUS_IN_PROGRESS": "In progress",
        "TASK_STATUS_BLOCKED": "Blocked",
        "TASK_STATUS_DONE": "Done",
        "TASK_STATUS_CANCELLED": "Dropped",
        "TASK_PRIORITY_NONE": "None",
        "TASK_PRIORITY_LOW": "Low",
        "TASK_PRIORITY_MEDIUM": "Medium",
        "TASK_PRIORITY_HIGH": "High",
        "TASK_PRIORITY_URGENT": "Urgent",
        "LIST_VISIBILITY_PRIVATE": "Private",
        "LIST_VISIBILITY_SHARED": "Shared",
        "LIST_VISIBILITY_PUBLIC": "Public",
        "LIST_COLOR_ZINC": "Grey",
        "LIST_COLOR_RED": "Red",
        "LIST_COLOR_AMBER": "Amber",
        "LIST_COLOR_GREEN": "Green",
        "LIST_COLOR_BLUE": "Blue",
        "LIST_COLOR_VIOLET": "Violet",
        "LIST_COLOR_PINK": "Pink",
        "MEMBER_ROLE_OWNER": "Owner",
        "MEMBER_ROLE_EDITOR": "Editor",
        "MEMBER_ROLE_COMMENTER": "Commenter",
        "MEMBER_ROLE_VIEWER": "Viewer",
        "USER_ROLE_MEMBER": "Member",
        "USER_ROLE_ADMIN": "Admin",
        "USER_STATUS_PENDING_VERIFICATION": "Awaiting confirmation",
        "USER_STATUS_ACTIVE": "Active",
        "USER_STATUS_SUSPENDED": "Suspended",
        "USER_STATUS_DEACTIVATED": "Closed",
        "LOCALE_DA": "Danish",
        "LOCALE_EN": "English",
        "THEME_PREFERENCE_SYSTEM": "Match system",
        "THEME_PREFERENCE_LIGHT": "Light",
        "THEME_PREFERENCE_DARK": "Dark",
        "RECURRENCE_FREQUENCY_NONE": "Does not repeat",
        "RECURRENCE_FREQUENCY_DAILY": "Daily",
        "RECURRENCE_FREQUENCY_WEEKLY": "Weekly",
        "RECURRENCE_FREQUENCY_MONTHLY": "Monthly",
        "RECURRENCE_FREQUENCY_YEARLY": "Yearly",
        "SESSION_CLIENT_WEB": "Web",
        "SESSION_CLIENT_MOBILE": "Mobile",
        "SESSION_CLIENT_CLI": "Terminal",
        "ACTIVITY_ACTION_CREATED": "created",
        "ACTIVITY_ACTION_UPDATED": "changed",
        "ACTIVITY_ACTION_STATUS_CHANGED": "moved the status of",
        "ACTIVITY_ACTION_ASSIGNED": "assigned",
        "ACTIVITY_ACTION_UNASSIGNED": "unassigned",
        "ACTIVITY_ACTION_COMMENTED": "commented on",
        "ACTIVITY_ACTION_ARCHIVED": "archived",
        "ACTIVITY_ACTION_RESTORED": "restored",
        "ACTIVITY_ACTION_DELETED": "deleted",
        "ACTIVITY_ACTION_MEMBER_ADDED": "gave access to",
        "ACTIVITY_ACTION_MEMBER_REMOVED": "removed access for",
        "ACTIVITY_ACTION_MEMBER_ROLE_CHANGED": "changed the role of",
    },
}

# Short, fixed-width status marks for list output. Chosen to line up in a column.
_STATUS_MARKS: Final[dict[str, str]] = {
    "TASK_STATUS_TODO": "○",
    "TASK_STATUS_IN_PROGRESS": "◐",
    "TASK_STATUS_BLOCKED": "▲",
    "TASK_STATUS_DONE": "●",
    # U+00D7 rather than a letter x, so the column of marks stays visually even.
    "TASK_STATUS_CANCELLED": "\u00d7",
}

# Ascending urgency, so a priority column reads as a ramp.
_PRIORITY_MARKS: Final[dict[str, str]] = {
    "TASK_PRIORITY_NONE": "  ",
    "TASK_PRIORITY_LOW": " ·",
    "TASK_PRIORITY_MEDIUM": " ▪",
    "TASK_PRIORITY_HIGH": " ▲",
    "TASK_PRIORITY_URGENT": "!!",
}

_RELATIVE: Final[dict[str, dict[str, str]]] = {
    "da": {
        "today": "i dag",
        "tomorrow": "i morgen",
        "yesterday": "i går",
        "in_days": "om {n} dage",
        "days_ago": "for {n} dage siden",
        "never": "aldrig",
        "none": "—",
    },
    "en": {
        "today": "today",
        "tomorrow": "tomorrow",
        "yesterday": "yesterday",
        "in_days": "in {n} days",
        "days_ago": "{n} days ago",
        "never": "never",
        "none": "—",
    },
}


def locale_or_default(locale: str | None) -> str:
    """Normalises a locale to one this build ships, falling back to Danish."""
    candidate = (locale or "da").lower().split("-")[0]
    return candidate if candidate in _NAMES else "da"


def enum_name(value_name: str, *, locale: str = "da") -> str:
    """Returns the display name for a proto enum value name.

    Args:
        value_name: The generated name, e.g. ``TASK_STATUS_DONE``.
        locale: ``da`` or ``en``.

    Returns:
        The localized name, or the raw value name when it is unknown. Falling back
        to the raw name keeps output legible after a proto change that predates a
        translation, and is loud enough to be spotted in review.
    """
    return _NAMES[locale_or_default(locale)].get(value_name, value_name)


def status_mark(value_name: str) -> str:
    """Returns the one-character mark for a task status."""
    return _STATUS_MARKS.get(value_name, "?")


def priority_mark(value_name: str) -> str:
    """Returns the two-character mark for a task priority."""
    return _PRIORITY_MARKS.get(value_name, "  ")


def timestamp(stamp: Timestamp | None, *, locale: str = "da", with_time: bool = True) -> str:
    """Formats a proto timestamp as a local date, optionally with the time."""
    if stamp is None or (stamp.seconds == 0 and stamp.nanos == 0):
        return _RELATIVE[locale_or_default(locale)]["none"]
    moment = stamp.ToDatetime(tzinfo=UTC).astimezone()
    return moment.strftime("%Y-%m-%d %H:%M" if with_time else "%Y-%m-%d")


def relative_date(stamp: Timestamp | None, *, locale: str = "da") -> str:
    """Formats a timestamp as a short relative phrase, e.g. "in 3 days".

    Beyond a week either side it falls back to an absolute date: "in 94 days" is
    less useful than the date itself.
    """
    words = _RELATIVE[locale_or_default(locale)]
    if stamp is None or (stamp.seconds == 0 and stamp.nanos == 0):
        return words["none"]

    moment = stamp.ToDatetime(tzinfo=UTC).astimezone()
    delta_days = (moment.date() - datetime.now(tz=UTC).astimezone().date()).days
    if delta_days == 0:
        return words["today"]
    if delta_days == 1:
        return words["tomorrow"]
    if delta_days == -1:
        return words["yesterday"]
    if 1 < delta_days <= 7:
        return words["in_days"].format(n=delta_days)
    if -7 <= delta_days < -1:
        return words["days_ago"].format(n=abs(delta_days))
    return moment.strftime("%Y-%m-%d")
