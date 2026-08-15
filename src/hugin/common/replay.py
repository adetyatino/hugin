"""BR-01 — the replay clock.

Volve stopped producing in 2016. An archive has no arrival pattern, so a pipeline
built on it has nothing to be incremental *about*. The replay clock supplies one:
the field's life (2008-06 .. 2016-09, 100 months) is projected onto real calendar
time, so that a DAG run covering a real interval covers a determinate slice of
field time.

The map is fixed by two settings:

    REPLAY_EPOCH   the real UTC instant at which the replay starts. At that
                   instant the replay is at the first day of field life,
                   2008-06-01.
    REPLAY_SPEED   field months elapsed per real day. Default 1 — one field
                   month per real day, so the whole field life replays in 100
                   real days.

Two properties matter more than the arithmetic:

*   It is a pure function of the interval Airflow hands the task. Nothing here
    reads the wall clock. A task re-run a week later for the same
    ``data_interval`` computes the same ``replay_date``, which is what makes
    backfill and re-run idempotent (see ``ReplayClock.replay_date``).
*   It does not invent field time. Before the epoch, and after the field's life
    is used up, it raises rather than clamping. Clamping would map two distinct
    intervals onto one ``_replay_date`` partition and quietly double-write it.

The arithmetic uses ``Fraction``, not float. Speeds like 0.1 are not
representable in binary floating point, and the day-within-month step is a
floor: a float error of one part in 2**52 landing on the wrong side of a day
boundary would make the round trip ``real_instant_for -> replay_date`` off by a
day for some inputs. Exact rationals remove the question.

Nothing in this module is imported by a DAG yet; the DAGs arrive in a later
phase.
"""

from __future__ import annotations

import calendar
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from fractions import Fraction

__all__ = [
    "FIELD_END",
    "FIELD_MONTHS",
    "FIELD_START",
    "ReplayClock",
    "ReplayClockError",
    "ReplayExhausted",
    "ReplayNotStarted",
    "ReplayWindow",
]

# Field life, from SPEC.md section 2. The end is the last day of 2016-09, so
# that the closed interval [FIELD_START, FIELD_END] is exactly FIELD_MONTHS
# whole calendar months.
FIELD_START = date(2008, 6, 1)
FIELD_END = date(2016, 9, 30)
FIELD_MONTHS = 100

_DEFAULT_SPEED = Fraction(1)
_US_PER_DAY = 86_400_000_000


class ReplayClockError(ValueError):
    """Base class for every way the replay clock can refuse to answer."""


class ReplayNotStarted(ReplayClockError):
    """The instant asked about lies before ``REPLAY_EPOCH``."""


class ReplayExhausted(ReplayClockError):
    """The instant asked about lies past the end of field life.

    Raised, not clamped: there is no field data after 2016-09, and a clamped
    date would be a lie about which slice of the field a run covers.
    """


@dataclass(frozen=True)
class ReplayWindow:
    """The closed range of field days a real interval covers."""

    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError(f"window ends before it starts: {self.start} .. {self.end}")

    def dates(self) -> list[date]:
        """Every field day in the window, inclusive of both ends."""
        span = (self.end - self.start).days
        return [self.start + timedelta(days=n) for n in range(span + 1)]


@dataclass(frozen=True)
class ReplayClock:
    """Maps real UTC instants onto field dates.

    ``epoch`` is the real instant that corresponds to :data:`FIELD_START`.
    ``speed`` is field months per real day, as an exact rational.
    """

    epoch: datetime
    speed: Fraction = _DEFAULT_SPEED

    def __post_init__(self) -> None:
        if self.epoch.tzinfo is None:
            raise ReplayClockError("epoch must be timezone-aware; use UTC")
        if self.speed <= 0:
            raise ReplayClockError(f"speed must be positive, got {self.speed}")
        # Normalise to UTC once, so equality between clocks is not sensitive to
        # which timezone the epoch was written in.
        object.__setattr__(self, "epoch", self.epoch.astimezone(UTC))
        object.__setattr__(self, "speed", Fraction(self.speed))

    # -- construction ----------------------------------------------------

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> ReplayClock:
        """Build a clock from ``REPLAY_EPOCH`` and ``REPLAY_SPEED``.

        ``REPLAY_EPOCH`` is required — there is no sensible default, since
        defaulting it to "today" would make every run's output depend on the day
        it ran, which is the failure mode this module exists to prevent.
        """
        env = os.environ if env is None else env
        raw_epoch = env.get("REPLAY_EPOCH", "").strip()
        if not raw_epoch:
            raise ReplayClockError(
                "REPLAY_EPOCH is not set. It pins the replay to a fixed real "
                "instant; without it, results depend on when the DAG happened "
                "to run. See .env.example."
            )
        raw_speed = env.get("REPLAY_SPEED", "").strip()
        return cls(
            epoch=parse_epoch(raw_epoch),
            speed=parse_speed(raw_speed) if raw_speed else _DEFAULT_SPEED,
        )

    # -- real time -> field time -----------------------------------------

    def replay_date(self, instant: datetime) -> date:
        """The field date the replay has reached at ``instant``.

        Pass ``data_interval_start`` from Airflow. Naive datetimes are read as
        UTC.
        """
        months = self._elapsed_field_months(instant)
        index = int(months // 1)
        if index >= FIELD_MONTHS:
            raise ReplayExhausted(
                f"{_fmt(instant)} is field month {index} of {FIELD_MONTHS}: the "
                f"replay ran past {FIELD_END}. Move REPLAY_EPOCH forward, or "
                f"stop the schedule — there is no Volve data after that date."
            )
        month_start = add_months(FIELD_START, index)
        days_in_month = calendar.monthrange(month_start.year, month_start.month)[1]
        day_offset = int((months - index) * days_in_month)
        return month_start + timedelta(days=day_offset)

    def replay_window(self, interval_start: datetime, interval_end: datetime) -> ReplayWindow:
        """The field days covered by a real interval, both ends inclusive.

        Airflow's ``data_interval_end`` is exclusive, so the last field day is
        taken from the instant just before it. At the default speed a single
        daily run covers a whole field month.
        """
        if interval_end <= interval_start:
            raise ReplayClockError(
                f"interval must be non-empty: {_fmt(interval_start)} .. {_fmt(interval_end)}"
            )
        last = interval_end - timedelta(microseconds=1)
        return ReplayWindow(self.replay_date(interval_start), self.replay_date(last))

    def is_exhausted(self, instant: datetime) -> bool:
        """True once the replay has passed the end of field life.

        Lets a DAG stop cleanly instead of catching :class:`ReplayExhausted`.
        """
        return self._elapsed_field_months(instant) >= FIELD_MONTHS

    # -- field time -> real time -----------------------------------------

    def real_instant_for(self, field_date: date) -> datetime:
        """The earliest real instant at which the replay has reached a field date.

        The inverse of :meth:`replay_date`, and the answer to "when will the
        replay reach 2013-04?". Rounded up to the microsecond, so the round trip
        ``replay_date(real_instant_for(d)) == d`` holds exactly.
        """
        if not FIELD_START <= field_date <= FIELD_END:
            raise ReplayClockError(
                f"{field_date} is outside field life {FIELD_START} .. {FIELD_END}"
            )
        index = months_between(FIELD_START, field_date)
        month_start = add_months(FIELD_START, index)
        days_in_month = calendar.monthrange(month_start.year, month_start.month)[1]
        months = index + Fraction((field_date - month_start).days, days_in_month)
        microseconds = months * _US_PER_DAY / self.speed
        return self.epoch + timedelta(microseconds=_ceil(microseconds))

    # -- internals -------------------------------------------------------

    def _elapsed_field_months(self, instant: datetime) -> Fraction:
        elapsed = _as_utc(instant) - self.epoch
        microseconds = (
            elapsed.days * _US_PER_DAY + elapsed.seconds * 1_000_000 + elapsed.microseconds
        )
        if microseconds < 0:
            raise ReplayNotStarted(
                f"{_fmt(instant)} is before REPLAY_EPOCH {_fmt(self.epoch)}: the "
                f"replay has not started."
            )
        return Fraction(microseconds, _US_PER_DAY) * self.speed


# -- module-level helpers -------------------------------------------------


def parse_epoch(raw: str) -> datetime:
    """Parse ``REPLAY_EPOCH``: an ISO-8601 date or datetime. Naive means UTC."""
    text = raw.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        try:
            parsed = datetime.combine(date.fromisoformat(text), datetime.min.time())
        except ValueError:
            raise ReplayClockError(
                f"REPLAY_EPOCH {raw!r} is not an ISO-8601 date or datetime "
                f"(e.g. 2026-08-01 or 2026-08-01T00:00:00Z)"
            ) from exc
    return _as_utc(parsed)


def parse_speed(raw: str) -> Fraction:
    """Parse ``REPLAY_SPEED``: field months per real day, as an exact rational."""
    try:
        speed = Fraction(raw.strip())
    except (ValueError, ZeroDivisionError) as exc:
        raise ReplayClockError(
            f"REPLAY_SPEED {raw!r} is not a number (e.g. 1, 0.5, or 2)"
        ) from exc
    if speed <= 0:
        raise ReplayClockError(f"REPLAY_SPEED must be positive, got {raw!r}")
    return speed


def add_months(start: date, months: int) -> date:
    """``start`` plus a whole number of calendar months, keeping the day.

    Only ever called with day-1 dates here, so the end-of-month clamp that a
    general implementation needs does not arise.
    """
    total = start.month - 1 + months
    year = start.year + total // 12
    month = total % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def months_between(start: date, end: date) -> int:
    """Whole calendar months from ``start`` to ``end``."""
    return (end.year - start.year) * 12 + (end.month - start.month)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(
        UTC
    )


def _ceil(value: Fraction) -> int:
    return -((-value.numerator) // value.denominator)


def _fmt(value: datetime) -> str:
    return _as_utc(value).isoformat()
