"""BR-06 — rig state classification, and the physical invariant it rests on.

The classifier is a pure function, so it is tested without Spark, Kafka or a
container. Each test builds the smallest sample sequence that should produce one
state and asserts it, which is also how the ordering is checked: several tests
construct a sample matching two rules and assert the earlier one wins.

The thresholds are SPEC.md's and are not adjusted here or anywhere. A test that
failed would mean the classifier disagrees with the rule as written, and the fix
is the classifier.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from hugin.streaming.rig_state import (
    NPT_THRESHOLD,
    THRESHOLDS,
    Sample,
    classify,
    classify_stream,
    spans_from_states,
)

T0 = datetime(2020, 1, 1, 0, 0, 0)


def sample(offset_s: float = 0.0, **kwargs) -> Sample:
    defaults = {
        "ts": T0 + timedelta(seconds=offset_s),
        "bit_depth_m": 1000.0,
        "hole_depth_m": 1000.0,
    }
    defaults.update(kwargs)
    return Sample(**defaults)


# --------------------------------------------------------------------------
# Each state, from the smallest case that produces it
# --------------------------------------------------------------------------

def test_br06_drilling_needs_depth_weight_and_flow():
    """bit at bottom, weight on bit, full flow."""
    previous = sample(0, bit_depth_m=999.9, hole_depth_m=1000.0)
    current = sample(5, bit_depth_m=1000.0, hole_depth_m=1000.0,
                     wob_klbf=12.0, flow_in_lpm=2200.0, rpm=110.0)
    assert classify(current, previous) == "DRILLING"


def test_br06_drilling_requires_the_bit_near_bottom():
    """Same weight and flow, bit 40 m off bottom: circulating, not drilling."""
    previous = sample(0, bit_depth_m=960.0, hole_depth_m=1000.0)
    current = sample(5, bit_depth_m=960.0, hole_depth_m=1000.0,
                     wob_klbf=12.0, flow_in_lpm=2200.0, rpm=110.0)
    assert classify(current, previous) == "CIRCULATING"


def test_br06_tripping_out_is_negative_depth_rate_with_no_weight():
    previous = sample(0, bit_depth_m=1000.0, hole_depth_m=1000.0)
    current = sample(10, bit_depth_m=999.0, hole_depth_m=1000.0, wob_klbf=0.5)
    assert classify(current, previous) == "TRIPPING_OUT"


def test_br06_tripping_in_is_positive_depth_rate_with_no_weight():
    previous = sample(0, bit_depth_m=900.0, hole_depth_m=1000.0)
    current = sample(10, bit_depth_m=901.0, hole_depth_m=1000.0, wob_klbf=0.5)
    assert classify(current, previous) == "TRIPPING_IN"


def test_br06_tripping_needs_the_string_off_bottom_weight():
    """Moving with weight on bit is not tripping — that is drilling ahead."""
    previous = sample(0, bit_depth_m=999.0, hole_depth_m=1000.0)
    current = sample(10, bit_depth_m=1000.0, hole_depth_m=1000.0,
                     wob_klbf=15.0, flow_in_lpm=2200.0)
    assert classify(current, previous) == "DRILLING"


def test_br06_circulating_is_flow_without_depth_change():
    previous = sample(0, bit_depth_m=980.0, hole_depth_m=1000.0)
    current = sample(10, bit_depth_m=980.02, hole_depth_m=1000.0,
                     flow_in_lpm=2000.0, wob_klbf=0.0)
    assert classify(current, previous) == "CIRCULATING"


def test_br06_static_is_the_fallback():
    previous = sample(0, bit_depth_m=500.0, hole_depth_m=1000.0)
    current = sample(10, bit_depth_m=500.0, hole_depth_m=1000.0,
                     flow_in_lpm=0.0, rpm=0.0, wob_klbf=0.0)
    assert classify(current, previous) == "STATIC"


def test_br06_connection_needs_block_movement_not_just_stillness():
    """Low flow and no rotation alone are STATIC; the blocks must be moving.

    This is the distinction that makes CONNECTION worth having: a connection is
    the pipe being handled, and without block travel the rig is simply stopped.
    """
    window_still = [
        sample(t, block_position_m=10.0, flow_in_lpm=0.0, rpm=0.0) for t in range(0, 120, 10)
    ]
    assert classify(window_still[-1], window_still[-2], window_still) == "STATIC"

    window_moving = [
        sample(t, block_position_m=2.0 + t / 20.0, flow_in_lpm=0.0, rpm=0.0)
        for t in range(0, 120, 10)
    ]
    assert classify(window_moving[-1], window_moving[-2], window_moving) == "CONNECTION"


def test_br06_connection_wins_over_static_when_both_would_match():
    """Ordering: CONNECTION is evaluated first and must take the sample."""
    window = [sample(t, block_position_m=1.0 + t, flow_in_lpm=0.0, rpm=0.0)
              for t in range(0, 60, 10)]
    assert classify(window[-1], window[-2], window) == "CONNECTION"


def test_br06_connection_window_is_ten_minutes_not_the_whole_history():
    """Block travel from twenty minutes ago must not classify now.

    The window is trimmed by time, so a rig that made a connection and then sat
    still stops being CONNECTION once the movement falls out of the window.
    """
    early = [sample(t, block_position_m=1.0 + t, flow_in_lpm=0.0, rpm=0.0) for t in range(0, 60, 10)]
    later = [sample(1200 + t, block_position_m=61.0, flow_in_lpm=0.0, rpm=0.0)
             for t in range(0, 60, 10)]
    states = [state for _sample, state in classify_stream(early + later)]
    assert states[-1] == "STATIC", "movement outside the 10-minute window still classified"


# --------------------------------------------------------------------------
# The physical invariant
# --------------------------------------------------------------------------

def test_br06_a_bit_below_the_hole_bottom_is_rejected():
    """SPEC.md states this as a property. It is enforced at construction."""
    with pytest.raises(ValueError, match="cannot be below"):
        Sample(ts=T0, bit_depth_m=1200.0, hole_depth_m=1000.0)


def test_br06_the_invariant_allows_measurement_noise():
    """Half a metre of tolerance, because two sensors never agree exactly."""
    Sample(ts=T0, bit_depth_m=1000.4, hole_depth_m=1000.0)


# --------------------------------------------------------------------------
# Spans and NPT
# --------------------------------------------------------------------------

def test_br06_consecutive_identical_states_collapse_into_one_span():
    samples = [
        sample(t, bit_depth_m=1000.0, hole_depth_m=1000.0,
               wob_klbf=12.0, flow_in_lpm=2200.0, rpm=100.0)
        for t in range(0, 60, 5)
    ]
    spans = list(spans_from_states(classify_stream(samples)))
    assert len(spans) == 1
    assert spans[0].state == "DRILLING"
    assert spans[0].sample_count == len(samples)


def test_br06_npt_is_static_for_more_than_thirty_minutes():
    short = [sample(t, flow_in_lpm=0.0, rpm=0.0, bit_depth_m=500.0) for t in range(0, 600, 60)]
    long = [sample(t, flow_in_lpm=0.0, rpm=0.0, bit_depth_m=500.0) for t in range(0, 3000, 60)]

    short_span = next(iter(spans_from_states(classify_stream(short))))
    long_span = next(iter(spans_from_states(classify_stream(long))))

    assert short_span.state == "STATIC" and not short_span.is_npt
    assert long_span.state == "STATIC" and long_span.is_npt
    assert long_span.duration_s > NPT_THRESHOLD.total_seconds()


def test_br06_a_span_records_the_depth_it_covered():
    samples = [sample(t * 10, bit_depth_m=1000.0 - t, hole_depth_m=1000.0, wob_klbf=0.5)
               for t in range(6)]
    spans = list(spans_from_states(classify_stream(samples)))
    tripping = [s for s in spans if s.state == "TRIPPING_OUT"]
    assert tripping, "a string coming out of the hole must produce a TRIPPING_OUT span"
    assert tripping[0].depth_from_m > tripping[0].depth_to_m


# --------------------------------------------------------------------------
# Property tests
# --------------------------------------------------------------------------

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, settings as hyp_settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402


@given(
    bit=st.floats(min_value=0, max_value=5000, allow_nan=False),
    delta=st.floats(min_value=0, max_value=2000, allow_nan=False),
    wob=st.floats(min_value=0, max_value=60, allow_nan=False),
    rpm=st.floats(min_value=0, max_value=200, allow_nan=False),
    flow=st.floats(min_value=0, max_value=4000, allow_nan=False),
)
@hyp_settings(max_examples=300, deadline=None)
def test_property_br06_always_returns_one_of_the_six_states(bit, delta, wob, rpm, flow):
    """Total function: every physically valid sample gets a state.

    A classifier returning None or raising on an unusual combination would stop
    a streaming job on one odd sample, which is the failure BR-07's dead-letter
    handling exists to avoid at the boundary — and it must not be reintroduced
    here.
    """
    hole = bit + delta
    current = sample(5, bit_depth_m=bit, hole_depth_m=hole,
                     wob_klbf=wob, rpm=rpm, flow_in_lpm=flow)
    previous = sample(0, bit_depth_m=bit, hole_depth_m=hole)
    state = classify(current, previous)
    assert state in {"CONNECTION", "TRIPPING_OUT", "TRIPPING_IN",
                     "DRILLING", "CIRCULATING", "STATIC"}


@given(rate=st.floats(min_value=-5.0, max_value=5.0, allow_nan=False))
@hyp_settings(max_examples=200, deadline=None)
def test_property_br06_tripping_direction_follows_the_sign_of_the_rate(rate):
    """Whatever else it decides, it never calls downward movement TRIPPING_OUT."""
    previous = sample(0, bit_depth_m=1000.0, hole_depth_m=3000.0)
    current = sample(10, bit_depth_m=1000.0 + rate * 10, hole_depth_m=3000.0, wob_klbf=0.0)
    state = classify(current, previous)
    if state == "TRIPPING_IN":
        assert rate > 0
    if state == "TRIPPING_OUT":
        assert rate < 0


@given(
    count=st.integers(min_value=1, max_value=60),
    seed=st.integers(min_value=0, max_value=10_000),
)
@hyp_settings(max_examples=50, deadline=None)
def test_property_spans_cover_every_sample_exactly_once(count, seed):
    """Collapsing to spans must not lose or duplicate a sample."""
    import random

    rng = random.Random(seed)
    samples = []
    depth = 1000.0
    for index in range(count):
        depth += rng.uniform(-0.5, 0.5)
        samples.append(sample(index * 5, bit_depth_m=depth, hole_depth_m=depth + 5,
                              wob_klbf=rng.uniform(0, 20), rpm=rng.uniform(0, 150),
                              flow_in_lpm=rng.uniform(0, 3000)))
    spans = list(spans_from_states(classify_stream(samples)))
    assert sum(span.sample_count for span in spans) == count
