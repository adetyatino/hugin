"""BR-06 — rig state classification, exactly as SPEC.md section 5 writes it.

The rule is an ordered list and the first match wins. That ordering is not
incidental: CONNECTION and STATIC would both match a stationary string, and
DRILLING and CIRCULATING both match a turning one with flow. Evaluating in a
different order silently reclassifies large stretches of a well.

    CONNECTION     flow_in < 100 and rpm < 5 and block position moving in a
                   10-minute window
    TRIPPING_OUT   d(bit_depth)/dt < -0.05 m/s and wob < 2
    TRIPPING_IN    d(bit_depth)/dt > +0.05 m/s and wob < 2
    DRILLING       bit_depth ~= hole_depth (+/- 0.5 m) and wob > 2 and
                   flow_in > 1000
    CIRCULATING    flow_in > 1000 and |d(bit_depth)/dt| < 0.01
    STATIC         anything else

``is_npt`` is true for a STATIC stretch longer than 30 minutes.

**The thresholds in this module are the ones SPEC.md specifies, and they are not
tuned.** SPEC.md section 5 is explicit that the agreement rate against the daily
drilling reports is to be reported as measured, and that adjusting the
thresholds to improve it is forbidden. They are constants here so that any
change to them is a visible diff rather than a quiet edit inside a query.

The classifier is a pure function over a window of samples, so it can be tested
without Spark, Kafka or a container — and it is, in tests/test_rig_state.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Iterator, Sequence

__all__ = [
    "CONNECTION_WINDOW",
    "NPT_THRESHOLD",
    "THRESHOLDS",
    "RigStateSpan",
    "Sample",
    "classify",
    "classify_stream",
    "spans_from_states",
]

#: Every number BR-06 names, in one place, with the unit in the name. Changing
#: one is a change to the rule and shows up as a diff on this block.
THRESHOLDS = {
    "connection_flow_in_lpm_max": 100.0,
    "connection_rpm_max": 5.0,
    "connection_block_travel_m_min": 0.5,
    "tripping_rate_m_per_s": 0.05,
    "tripping_wob_klbf_max": 2.0,
    "drilling_depth_tolerance_m": 0.5,
    "drilling_wob_klbf_min": 2.0,
    "drilling_flow_in_lpm_min": 1000.0,
    "circulating_flow_in_lpm_min": 1000.0,
    "circulating_rate_m_per_s_max": 0.01,
}

#: The window CONNECTION looks back over for block movement.
CONNECTION_WINDOW = timedelta(minutes=10)

#: A STATIC stretch longer than this is non-productive time.
NPT_THRESHOLD = timedelta(minutes=30)

STATES = ("CONNECTION", "TRIPPING_OUT", "TRIPPING_IN", "DRILLING", "CIRCULATING", "STATIC")


@dataclass(frozen=True)
class Sample:
    """One telemetry sample. Channels are optional because sensors drop out."""

    ts: datetime
    bit_depth_m: float
    hole_depth_m: float
    block_position_m: float | None = None
    wob_klbf: float | None = None
    rpm: float | None = None
    flow_in_lpm: float | None = None

    def __post_init__(self) -> None:
        if self.bit_depth_m > self.hole_depth_m + 0.5:
            raise ValueError(
                f"bit_depth_m {self.bit_depth_m} exceeds hole_depth_m "
                f"{self.hole_depth_m}: the bit cannot be below the hole bottom"
            )


@dataclass(frozen=True)
class RigStateSpan:
    """A run of consecutive samples sharing a state."""

    state: str
    started_at: datetime
    ended_at: datetime
    depth_from_m: float
    depth_to_m: float
    sample_count: int

    @property
    def duration_s(self) -> float:
        return (self.ended_at - self.started_at).total_seconds()

    @property
    def is_npt(self) -> bool:
        """BR-06: STATIC for more than 30 minutes is non-productive time."""
        return self.state == "STATIC" and self.duration_s > NPT_THRESHOLD.total_seconds()


def _value(sample: Sample, name: str, default: float) -> float:
    """A missing channel takes a default that cannot satisfy a threshold.

    A dropped-out sensor must not classify as anything but STATIC. Defaulting
    flow to 0 and rpm to 0 makes CONNECTION's low-flow test pass on missing
    data, which is why the block-travel test is also required for CONNECTION.
    """
    value = getattr(sample, name)
    return default if value is None else float(value)


def _block_travel(window: Sequence[Sample]) -> float:
    positions = [s.block_position_m for s in window if s.block_position_m is not None]
    return max(positions) - min(positions) if len(positions) >= 2 else 0.0


def classify(
    sample: Sample,
    previous: Sample | None,
    window: Sequence[Sample] = (),
) -> str:
    """The state of one sample, given its predecessor and a 10-minute window.

    ``previous`` supplies the depth derivative; ``window`` supplies the block
    movement CONNECTION needs. With neither, only the state tests that depend on
    instantaneous values can fire, and the rest fall through to STATIC — which
    is the correct answer for a single sample in isolation.
    """
    flow = _value(sample, "flow_in_lpm", 0.0)
    rpm = _value(sample, "rpm", 0.0)
    wob = _value(sample, "wob_klbf", 0.0)

    rate = 0.0
    if previous is not None:
        elapsed = (sample.ts - previous.ts).total_seconds()
        if elapsed > 0:
            rate = (sample.bit_depth_m - previous.bit_depth_m) / elapsed

    # First match wins, in SPEC.md's order.
    if (
        flow < THRESHOLDS["connection_flow_in_lpm_max"]
        and rpm < THRESHOLDS["connection_rpm_max"]
        and _block_travel(window) >= THRESHOLDS["connection_block_travel_m_min"]
    ):
        return "CONNECTION"

    if rate < -THRESHOLDS["tripping_rate_m_per_s"] and wob < THRESHOLDS["tripping_wob_klbf_max"]:
        return "TRIPPING_OUT"

    if rate > THRESHOLDS["tripping_rate_m_per_s"] and wob < THRESHOLDS["tripping_wob_klbf_max"]:
        return "TRIPPING_IN"

    if (
        abs(sample.bit_depth_m - sample.hole_depth_m) <= THRESHOLDS["drilling_depth_tolerance_m"]
        and wob > THRESHOLDS["drilling_wob_klbf_min"]
        and flow > THRESHOLDS["drilling_flow_in_lpm_min"]
    ):
        return "DRILLING"

    if (
        flow > THRESHOLDS["circulating_flow_in_lpm_min"]
        and abs(rate) < THRESHOLDS["circulating_rate_m_per_s_max"]
    ):
        return "CIRCULATING"

    return "STATIC"


def classify_stream(samples: Iterable[Sample]) -> Iterator[tuple[Sample, str]]:
    """Classify a time-ordered stream, maintaining the CONNECTION window.

    The window is trimmed by time rather than by count, so a stream whose sample
    interval changes — a rig switching from 5 s to 1 s logging — still looks
    back exactly ten minutes.
    """
    window: list[Sample] = []
    previous: Sample | None = None
    for sample in samples:
        window.append(sample)
        cutoff = sample.ts - CONNECTION_WINDOW
        while window and window[0].ts < cutoff:
            window.pop(0)
        yield sample, classify(sample, previous, window)
        previous = sample


def spans_from_states(
    classified: Iterable[tuple[Sample, str]],
) -> Iterator[RigStateSpan]:
    """Collapse consecutive identical states into spans.

    ``fct_drilling_state`` is grained on state runs, not samples: a two-hour
    trip is one fact, and storing it per sample would multiply the table by the
    logging rate without adding information.
    """
    state: str | None = None
    first: Sample | None = None
    last: Sample | None = None
    count = 0

    for sample, current in classified:
        if current != state:
            if state is not None and first is not None and last is not None:
                yield RigStateSpan(
                    state=state, started_at=first.ts, ended_at=last.ts,
                    depth_from_m=first.bit_depth_m, depth_to_m=last.bit_depth_m,
                    sample_count=count,
                )
            state, first, count = current, sample, 0
        last = sample
        count += 1

    if state is not None and first is not None and last is not None:
        yield RigStateSpan(
            state=state, started_at=first.ts, ended_at=last.ts,
            depth_from_m=first.bit_depth_m, depth_to_m=last.bit_depth_m,
            sample_count=count,
        )
