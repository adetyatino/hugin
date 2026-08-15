"""BR-09 — minimum curvature. Not tangential, not average angle.

The formula, exactly as SPEC.md section 5 writes it:

    DL   = arccos( cos(I2 - I1) - sin(I1)*sin(I2)*(1 - cos(A2 - A1)) )
    RF   = (2/DL) * tan(DL/2)        when DL > 0, otherwise 1
    dTVD = (dMD/2) * (cos I1 + cos I2) * RF
    dN   = (dMD/2) * (sin I1*cos A1 + sin I2*cos A2) * RF
    dE   = (dMD/2) * (sin I1*sin A1 + sin I2*sin A2) * RF

Why the method matters. The tangential method takes the lower station's angles
for the whole interval and can be tens of metres out over a build section;
average-angle is better and still biased. Minimum curvature fits a circular arc
through both stations, which is what a bottom-hole assembly actually drills.
The ratio factor RF is the correction from a straight chord to that arc, and it
tends to 1 as the dogleg tends to zero — which is why the DL = 0 case is not a
special case bolted on but the limit of the same expression.

Two numerical points that decide whether this works on real data:

*   **The arccos argument must be clamped.** For a nearly straight interval the
    expression evaluates to 1 + 1e-16 in floating point, and ``acos`` raises a
    domain error. A survey with any straight section will fail on the first one.
*   **RF is computed by series when DL is small.** ``(2/DL)*tan(DL/2)`` divides
    two quantities that both approach zero; below about 1e-4 radians the result
    is dominated by rounding. The Taylor expansion 1 + DL^2/12 is exact to
    machine precision there and continuous with the closed form above it.

Everything here is pure: it takes stations and returns a computed survey, so it
can be checked against the surveying contractor's own numbers, which is what
:mod:`tests.test_minimum_curvature` does over 475 real stations.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

__all__ = [
    "ComputedStation",
    "Station",
    "closure_error",
    "dogleg_severity",
    "minimum_curvature",
    "ratio_factor",
]

#: Below this dogleg, in radians, RF is evaluated by series rather than by the
#: closed form. 1e-4 rad over a 30 m course is a dogleg of 0.17 deg/30m, well
#: inside what any survey calls straight.
_SMALL_DOGLEG = 1e-4


@dataclass(frozen=True)
class Station:
    """One survey station.

    Angles are degrees *because the caller converted them*, not because surveys
    always use degrees. Four of Volve's trajectory documents declare
    ``uom="rad"`` on incl and azi while the rest declare ``uom="dega"``, and the
    radian ones are perfectly plausible read as degrees - 0.371 looks like a
    nearly vertical hole and is really 21 degrees. Reading them as degrees puts
    the shoe 188 m off, which is the kind of error that reaches a well plan.

    :func:`from_uom` does the conversion from what a document declares; nothing
    in this module guesses.
    """

    md_m: float
    inclination_deg: float
    azimuth_deg: float

    @classmethod
    def from_uom(
        cls, md_m: float, inclination: float, azimuth: float, uom: str | None
    ) -> "Station":
        """Build a station from angles in the unit the source declares.

        ``uom`` is the WITSML unit of measure: ``dega`` or ``rad``. An
        unrecognised or missing unit raises rather than defaulting - a survey
        that does not say what its angles are is not one this can compute with.
        """
        unit = (uom or "").strip().lower()
        if unit in ("dega", "deg", "degree", "degrees"):
            return cls(md_m, inclination, azimuth)
        if unit in ("rad", "radian", "radians"):
            return cls(md_m, math.degrees(inclination), math.degrees(azimuth))
        raise ValueError(
            f"angle unit {uom!r} is not one this understands. Surveys in this "
            f"delivery declare 'dega' or 'rad'; guessing between them is a "
            f"188 m error on a 3 km well."
        )


@dataclass(frozen=True)
class ComputedStation:
    """A station with the position minimum curvature puts it at."""

    md_m: float
    inclination_deg: float
    azimuth_deg: float
    tvd_m: float
    northing_m: float
    easting_m: float
    dogleg_deg: float
    dogleg_severity_deg_30m: float
    course_length_m: float


def _dogleg_radians(i1: float, i2: float, a1: float, a2: float) -> float:
    """The dogleg angle between two stations, all arguments in radians."""
    value = math.cos(i2 - i1) - math.sin(i1) * math.sin(i2) * (1.0 - math.cos(a2 - a1))
    # Clamp: a straight interval produces 1 + epsilon and acos raises on it.
    # This is not a tolerance being applied to the physics, it is floating point
    # being kept inside the domain of the function.
    return math.acos(max(-1.0, min(1.0, value)))


def ratio_factor(dogleg_rad: float) -> float:
    """RF = (2/DL)*tan(DL/2), by series where that expression loses precision."""
    if dogleg_rad < _SMALL_DOGLEG:
        # tan(x) = x + x^3/3 + ..., so (2/DL)*tan(DL/2) = 1 + DL^2/12 + O(DL^4)
        return 1.0 + dogleg_rad * dogleg_rad / 12.0
    return (2.0 / dogleg_rad) * math.tan(dogleg_rad / 2.0)


def dogleg_severity(dogleg_rad: float, course_length_m: float, per_m: float = 30.0) -> float:
    """Dogleg severity in degrees per 30 m, the unit every drilling report uses.

    SPEC.md asks for degrees per 30 m specifically. A severity in degrees per
    metre is the same information and is off by a factor of thirty in every
    comparison against a drilling programme.
    """
    if course_length_m <= 0:
        return 0.0
    return math.degrees(dogleg_rad) * per_m / course_length_m


def minimum_curvature(
    stations: Sequence[Station],
    tvd_start_m: float = 0.0,
    northing_start_m: float = 0.0,
    easting_start_m: float = 0.0,
) -> list[ComputedStation]:
    """Compute the position of every station from the one before it.

    The first station is the tie-in: its position is the starting point, not a
    computed value, which is why the survey's own first station is passed
    through rather than recomputed from zero.
    """
    if not stations:
        return []

    first = stations[0]
    computed = [
        ComputedStation(
            md_m=first.md_m,
            inclination_deg=first.inclination_deg,
            azimuth_deg=first.azimuth_deg,
            tvd_m=tvd_start_m,
            northing_m=northing_start_m,
            easting_m=easting_start_m,
            dogleg_deg=0.0,
            dogleg_severity_deg_30m=0.0,
            course_length_m=0.0,
        )
    ]

    for previous, current in zip(stations, stations[1:], strict=False):
        course = current.md_m - previous.md_m
        if course < 0:
            raise ValueError(
                f"stations are not in measured-depth order: {previous.md_m} then {current.md_m}"
            )

        i1 = math.radians(previous.inclination_deg)
        i2 = math.radians(current.inclination_deg)
        a1 = math.radians(previous.azimuth_deg)
        a2 = math.radians(current.azimuth_deg)

        dogleg = _dogleg_radians(i1, i2, a1, a2)
        factor = ratio_factor(dogleg)
        half = course / 2.0

        delta_tvd = half * (math.cos(i1) + math.cos(i2)) * factor
        delta_north = half * (
            math.sin(i1) * math.cos(a1) + math.sin(i2) * math.cos(a2)
        ) * factor
        delta_east = half * (
            math.sin(i1) * math.sin(a1) + math.sin(i2) * math.sin(a2)
        ) * factor

        last = computed[-1]
        computed.append(
            ComputedStation(
                md_m=current.md_m,
                inclination_deg=current.inclination_deg,
                azimuth_deg=current.azimuth_deg,
                tvd_m=last.tvd_m + delta_tvd,
                northing_m=last.northing_m + delta_north,
                easting_m=last.easting_m + delta_east,
                dogleg_deg=math.degrees(dogleg),
                dogleg_severity_deg_30m=dogleg_severity(dogleg, course),
                course_length_m=course,
            )
        )

    return computed


def closure_error(
    computed: Iterable[ComputedStation],
    reported: Iterable[tuple[float, float, float]],
) -> dict[str, float]:
    """Compare a computed survey against the values the source reported.

    ``reported`` is ``(tvd, northing, easting)`` per station, in the same order.
    This is the real check on an implementation of BR-09: the surveying
    contractor computed these numbers with their own software, and agreement to
    within a fraction of a percent over a few thousand metres means the method
    and the conventions match. A closure error against *zero* would only prove
    the arithmetic is self-consistent.

    Returned as absolute and relative, because a 0.3 m disagreement means
    something different at 300 m than at 3,000 m.
    """
    max_tvd = max_north = max_east = 0.0
    max_position = 0.0
    depth_at_max = 0.0
    count = 0

    for station, (tvd, north, east) in zip(computed, reported, strict=False):
        count += 1
        d_tvd = abs(station.tvd_m - tvd)
        d_north = abs(station.northing_m - north)
        d_east = abs(station.easting_m - east)
        position = math.sqrt(d_tvd**2 + d_north**2 + d_east**2)

        max_tvd = max(max_tvd, d_tvd)
        max_north = max(max_north, d_north)
        max_east = max(max_east, d_east)
        if position > max_position:
            max_position = position
            depth_at_max = station.md_m

    return {
        "stations": count,
        "max_tvd_error_m": max_tvd,
        "max_northing_error_m": max_north,
        "max_easting_error_m": max_east,
        "max_position_error_m": max_position,
        "md_at_max_error_m": depth_at_max,
        # Relative to the depth where the worst disagreement occurs, which is
        # the number SPEC.md's 0.1% threshold is about.
        "closure_error_pct": (max_position / depth_at_max * 100.0) if depth_at_max else 0.0,
    }
