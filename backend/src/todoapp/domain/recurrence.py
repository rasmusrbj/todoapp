"""Recurring-task rules.

When a repeating task is completed, the next occurrence is created rather than the
existing row being rolled forward. That keeps history intact: "pay rent" completed
in March and completed in April are two records, not one row whose due date moved.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

# Days per step, for the frequencies that are a fixed number of days.
_FIXED_STEP_DAYS: Final[dict[str, int]] = {"daily": 1, "weekly": 7}


@dataclass(frozen=True, slots=True)
class Recurrence:
    """A validated repeat rule.

    Attributes:
        frequency: PostgreSQL ``recurrence_frequency`` label.
        interval: Repeat every ``interval`` periods. Always at least 1.
        until: Stop after this moment, or ``None`` for indefinitely.
    """

    frequency: str
    interval: int
    until: datetime | None

    @property
    def repeats(self) -> bool:
        """Whether this rule produces further occurrences at all."""
        return self.frequency != "none"


def _add_months(moment: datetime, months: int) -> datetime:
    """Adds calendar months, clamping the day to the target month's length.

    31 January plus one month is 28 (or 29) February, not 3 March. Clamping is what
    users expect from a monthly reminder, and it is what every calendar app does.
    """
    zero_based_month = moment.month - 1 + months
    year = moment.year + zero_based_month // 12
    month = zero_based_month % 12 + 1

    # Day 1 of the following month, minus a day, is the last day of `month`.
    next_month_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    last_day = (
        moment.replace(year=next_month_year, month=next_month, day=1) - timedelta(days=1)
    ).day

    return moment.replace(year=year, month=month, day=min(moment.day, last_day))


def next_occurrence(anchor: datetime, rule: Recurrence) -> datetime | None:
    """Returns the moment after ``anchor`` at which the task recurs.

    Args:
        anchor: The completed occurrence's due date, or its completion time when it
            had no due date.
        rule: The repeat rule.

    Returns:
        The next occurrence, or ``None`` when the rule does not repeat or has run
        past its ``until`` bound.
    """
    if not rule.repeats:
        return None

    interval = max(rule.interval, 1)
    if (step_days := _FIXED_STEP_DAYS.get(rule.frequency)) is not None:
        candidate = anchor + timedelta(days=step_days * interval)
    elif rule.frequency == "monthly":
        candidate = _add_months(anchor, interval)
    elif rule.frequency == "yearly":
        candidate = _add_months(anchor, 12 * interval)
    else:
        raise ValueError(f"unhandled recurrence frequency {rule.frequency!r}")

    if rule.until is not None and candidate > rule.until:
        return None
    return candidate


def shift(
    due_at: datetime | None, starts_at: datetime | None, target_due: datetime
) -> datetime | None:
    """Moves ``starts_at`` by the same delta that moves ``due_at`` to ``target_due``.

    A task due Friday that starts Wednesday should still start two days early in the
    next occurrence, so the gap is preserved rather than the absolute start date.
    """
    if starts_at is None:
        return None
    if due_at is None:
        return target_due
    return target_due - (due_at - starts_at)
