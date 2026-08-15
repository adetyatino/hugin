"""BR-01 — replay clock.

Every test name carries the rule code, per SPEC.md section 9.

These are deterministic sweeps rather than property tests. `hypothesis` is a
declared dependency for later phases but is not installed yet, and a test that
cannot run is worse than one that enumerates its own inputs: the sweeps below
cover every field day of the replay, which is the whole input domain that
matters here.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from fractions import Fraction

import pytest

from hugin.common.replay import (
    FIELD_END,
    FIELD_MONTHS,
    FIELD_START,
    ReplayClock,
    ReplayClockError,
    ReplayExhausted,
    ReplayNotStarted,
    add_months,
    months_between,
    parse_epoch,
    parse_speed,
)

EPOCH = datetime(2026, 8, 1, tzinfo=UTC)


def clock(speed: str = "1") -> ReplayClock:
    return ReplayClock(epoch=EPOCH, speed=Fraction(speed))


def field_days() -> list[date]:
    days, day = [], FIELD_START
    while day <= FIELD_END:
        days.append(day)
        day += timedelta(days=1)
    return days


# -- the map itself -------------------------------------------------------


def test_br01_epoch_maps_to_first_day_of_field_life():
    assert clock().replay_date(EPOCH) == FIELD_START


def test_br01_default_speed_is_one_field_month_per_real_day():
    c = clock()
    assert c.replay_date(EPOCH + timedelta(days=1)) == date(2008, 7, 1)
    assert c.replay_date(EPOCH + timedelta(days=2)) == date(2008, 8, 1)
    # 100 field months of life: the last real day lands in the last field month.
    last = c.replay_date(EPOCH + timedelta(days=FIELD_MONTHS - 1))
    assert (last.year, last.month) == (FIELD_END.year, FIELD_END.month)


def test_br01_field_life_is_one_hundred_months():
    assert months_between(FIELD_START, FIELD_END) + 1 == FIELD_MONTHS
    assert add_months(FIELD_START, FIELD_MONTHS - 1) == FIELD_END.replace(day=1)


def test_br01_a_real_day_walks_the_whole_field_month():
    """Within one real day the replay walks 2008-06-01 .. 06-30 and no further."""
    c = clock()
    seen = {c.replay_date(EPOCH + timedelta(minutes=m)) for m in range(24 * 60)}
    assert min(seen) == date(2008, 6, 1)
    assert max(seen) == date(2008, 6, 30)
    assert len(seen) == 30


def test_br01_speed_scales_the_map():
    """Half speed puts the field month boundary two real days out, not one."""
    half = clock("0.5")
    assert half.replay_date(EPOCH + timedelta(days=1)) == date(2008, 6, 16)
    assert half.replay_date(EPOCH + timedelta(days=2)) == date(2008, 7, 1)
    assert clock("2").replay_date(EPOCH + timedelta(days=1)) == date(2008, 8, 1)


def test_br01_speed_uses_exact_rationals_not_floats():
    """0.1 is not representable in binary; the tenth step must still land clean."""
    c = clock("0.1")
    assert c.replay_date(EPOCH + timedelta(days=10)) == date(2008, 7, 1)
    assert c.speed == Fraction(1, 10)


# -- the properties the pipeline leans on ---------------------------------


def test_br01_is_monotonic_over_the_whole_replay():
    c = clock()
    previous = FIELD_START
    for hour in range(FIELD_MONTHS * 24):
        current = c.replay_date(EPOCH + timedelta(hours=hour))
        assert current >= previous
        previous = current


def test_br01_round_trips_every_field_day():
    c = clock()
    for day in field_days():
        assert c.replay_date(c.real_instant_for(day)) == day


def test_br01_round_trips_every_field_day_at_other_speeds():
    for speed in ("0.5", "2", "1/3", "7"):
        c = clock(speed)
        for day in field_days():
            assert c.replay_date(c.real_instant_for(day)) == day


def test_br01_covers_every_field_day_exactly_once():
    """No field day is skipped and none is visited by two different runs."""
    c = clock()
    covered = [d for n in range(FIELD_MONTHS) for d in c.replay_window(
        EPOCH + timedelta(days=n), EPOCH + timedelta(days=n + 1)
    ).dates()]
    assert covered == field_days()
    assert len(set(covered)) == len(covered)


def test_br01_is_a_pure_function_of_the_interval_not_the_wall_clock():
    """Idempotency rests on this: a re-run of the same interval is the same date."""
    interval = EPOCH + timedelta(days=17, hours=6)
    first = clock().replay_date(interval)
    later = ReplayClock(epoch=EPOCH, speed=Fraction(1)).replay_date(interval)
    # 17 real days in: field month 17 after 2008-06 is 2009-11; the extra six
    # hours is a quarter of that month's 30 days, so day 1 + 7.
    assert first == later == date(2009, 11, 8)


def test_br01_daily_run_covers_one_whole_field_month():
    window = clock().replay_window(EPOCH, EPOCH + timedelta(days=1))
    assert (window.start, window.end) == (date(2008, 6, 1), date(2008, 6, 30))
    assert len(window.dates()) == 30


# -- refusals -------------------------------------------------------------


def test_br01_refuses_instants_before_the_epoch():
    with pytest.raises(ReplayNotStarted):
        clock().replay_date(EPOCH - timedelta(microseconds=1))


def test_br01_refuses_to_clamp_past_the_end_of_field_life():
    """Clamping would map two intervals onto one _replay_date partition."""
    c = clock()
    exhausted = EPOCH + timedelta(days=FIELD_MONTHS)
    assert c.is_exhausted(exhausted)
    assert not c.is_exhausted(exhausted - timedelta(microseconds=1))
    with pytest.raises(ReplayExhausted):
        c.replay_date(exhausted)


def test_br01_refuses_an_empty_interval():
    with pytest.raises(ReplayClockError):
        clock().replay_window(EPOCH, EPOCH)


def test_br01_refuses_a_field_date_outside_field_life():
    with pytest.raises(ReplayClockError):
        clock().real_instant_for(FIELD_START - timedelta(days=1))
    with pytest.raises(ReplayClockError):
        clock().real_instant_for(FIELD_END + timedelta(days=1))


def test_br01_refuses_a_naive_epoch():
    with pytest.raises(ReplayClockError):
        ReplayClock(epoch=datetime(2026, 8, 1))


# -- configuration --------------------------------------------------------


def test_br01_reads_epoch_and_speed_from_env():
    c = ReplayClock.from_env({"REPLAY_EPOCH": "2026-08-01", "REPLAY_SPEED": "0.5"})
    assert c.epoch == EPOCH
    assert c.speed == Fraction(1, 2)


def test_br01_speed_defaults_to_one_month_per_day():
    assert ReplayClock.from_env({"REPLAY_EPOCH": "2026-08-01"}).speed == Fraction(1)


def test_br01_requires_an_explicit_epoch():
    """Defaulting the epoch to 'today' would make output depend on run date."""
    with pytest.raises(ReplayClockError, match="REPLAY_EPOCH"):
        ReplayClock.from_env({})


def test_br01_parses_epoch_in_the_forms_a_env_file_uses():
    expected = datetime(2026, 8, 1, tzinfo=UTC)
    assert parse_epoch("2026-08-01") == expected
    assert parse_epoch("2026-08-01T00:00:00Z") == expected
    assert parse_epoch("2026-08-01T00:00:00+00:00") == expected
    # Non-UTC offsets are normalised, not rejected.
    assert parse_epoch("2026-08-01T02:00:00+02:00") == expected


@pytest.mark.parametrize("bad", ["", "yesterday", "2026-13-01"])
def test_br01_rejects_an_unparseable_epoch(bad):
    with pytest.raises(ReplayClockError):
        parse_epoch(bad)


@pytest.mark.parametrize("bad", ["0", "-1", "fast", ""])
def test_br01_rejects_a_nonpositive_or_unparseable_speed(bad):
    with pytest.raises(ReplayClockError):
        parse_speed(bad)
