"""Pure unit tests for the repeat-rule arithmetic.

Calendar maths is where date bugs live, so it is tested without a database.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from todoapp.domain.recurrence import Recurrence, next_occurrence, shift


def at(year: int, month: int, day: int, hour: int = 9) -> datetime:
    """Builds an aware UTC datetime."""
    return datetime(year, month, day, hour, tzinfo=UTC)


def rule(frequency: str, interval: int = 1, until: datetime | None = None) -> Recurrence:
    """Builds a repeat rule."""
    return Recurrence(frequency=frequency, interval=interval, until=until)


def test_none_never_recurs() -> None:
    assert next_occurrence(at(2026, 8, 15), rule("none")) is None
    assert rule("none").repeats is False


@pytest.mark.parametrize(
    ("frequency", "interval", "expected"),
    [
        ("daily", 1, at(2026, 8, 16)),
        ("daily", 3, at(2026, 8, 18)),
        ("weekly", 1, at(2026, 8, 22)),
        ("weekly", 2, at(2026, 8, 29)),
        ("monthly", 1, at(2026, 9, 15)),
        ("monthly", 4, at(2026, 12, 15)),
        ("yearly", 1, at(2027, 8, 15)),
    ],
)
def test_fixed_steps(frequency: str, interval: int, expected: datetime) -> None:
    assert next_occurrence(at(2026, 8, 15), rule(frequency, interval)) == expected


def test_time_of_day_is_preserved() -> None:
    assert next_occurrence(at(2026, 8, 15, 17), rule("daily")) == at(2026, 8, 16, 17)


def test_monthly_clamps_to_the_shorter_month() -> None:
    """31 January plus a month is the end of February, not the start of March."""
    assert next_occurrence(at(2026, 1, 31), rule("monthly")) == at(2026, 2, 28)
    assert next_occurrence(at(2026, 3, 31), rule("monthly")) == at(2026, 4, 30)
    assert next_occurrence(at(2026, 8, 31), rule("monthly")) == at(2026, 9, 30)


def test_monthly_clamps_into_a_leap_february() -> None:
    assert next_occurrence(at(2028, 1, 31), rule("monthly")) == at(2028, 2, 29)


def test_monthly_rolls_the_year_over() -> None:
    assert next_occurrence(at(2026, 12, 15), rule("monthly")) == at(2027, 1, 15)
    assert next_occurrence(at(2026, 11, 15), rule("monthly", 2)) == at(2027, 1, 15)


def test_yearly_from_a_leap_day_clamps() -> None:
    assert next_occurrence(at(2028, 2, 29), rule("yearly")) == at(2029, 2, 28)


def test_until_bounds_the_series() -> None:
    assert next_occurrence(at(2026, 8, 15), rule("daily", until=at(2026, 8, 16))) == at(2026, 8, 16)
    # One day past the bound: the series is over.
    assert next_occurrence(at(2026, 8, 16), rule("daily", until=at(2026, 8, 16))) is None


def test_interval_below_one_is_treated_as_one() -> None:
    """Guards against a stored 0 producing an infinite loop of same-day tasks."""
    assert next_occurrence(at(2026, 8, 15), rule("daily", 0)) == at(2026, 8, 16)


def test_unknown_frequency_raises() -> None:
    with pytest.raises(ValueError, match="unhandled recurrence frequency"):
        next_occurrence(at(2026, 8, 15), rule("fortnightly"))


def test_shift_preserves_the_gap_between_start_and_due() -> None:
    due = at(2026, 8, 21)
    starts = at(2026, 8, 19)
    moved = shift(due, starts, at(2026, 9, 21))
    assert moved == at(2026, 9, 19)
    assert moved is not None
    assert due - starts == at(2026, 9, 21) - moved == timedelta(days=2)


def test_shift_without_a_start_stays_absent() -> None:
    assert shift(at(2026, 8, 21), None, at(2026, 9, 21)) is None


def test_shift_without_a_due_date_anchors_on_the_target() -> None:
    assert shift(None, at(2026, 8, 19), at(2026, 9, 21)) == at(2026, 9, 21)
