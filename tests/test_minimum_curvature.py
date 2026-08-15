"""BR-09 — minimum curvature, against known geometry and against real surveys.

Three layers:

* closed-form cases where the answer is known by geometry rather than by
  another implementation — a vertical hole, a horizontal one, a quarter turn;
* invariants that must hold for any survey;
* the real Volve surveys, where the surveying contractor's own computed TVD is
  the thing being matched. That last one is the test that means something: it
  compares this implementation against software that was used to steer a well.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from hugin.geo.minimum_curvature import (
    Station,
    closure_error,
    dogleg_severity,
    minimum_curvature,
    ratio_factor,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------
# Geometry with a known answer
# --------------------------------------------------------------------------

def test_br09_a_vertical_hole_has_tvd_equal_to_md():
    survey = minimum_curvature([
        Station(0.0, 0.0, 0.0), Station(500.0, 0.0, 0.0), Station(1000.0, 0.0, 0.0),
    ])
    for station in survey:
        assert station.tvd_m == pytest.approx(station.md_m, abs=1e-9)
        assert station.northing_m == pytest.approx(0.0, abs=1e-9)
        assert station.easting_m == pytest.approx(0.0, abs=1e-9)


def test_br09_a_horizontal_section_adds_displacement_and_no_depth():
    """90 degrees inclination due north: all course length becomes northing."""
    survey = minimum_curvature([
        Station(1000.0, 90.0, 0.0), Station(1100.0, 90.0, 0.0),
    ])
    assert survey[-1].tvd_m == pytest.approx(0.0, abs=1e-9)
    assert survey[-1].northing_m == pytest.approx(100.0, abs=1e-6)
    assert survey[-1].easting_m == pytest.approx(0.0, abs=1e-9)


def test_br09_a_quarter_circle_build_matches_the_closed_form():
    """0 to 90 degrees over a 100 m course is a quarter circle of radius
    R = L / (pi/2). Its vertical rise is R and its horizontal reach is R."""
    course = 100.0
    survey = minimum_curvature([Station(0.0, 0.0, 0.0), Station(course, 90.0, 0.0)])
    radius = course / (math.pi / 2)
    assert survey[-1].tvd_m == pytest.approx(radius, rel=1e-9)
    assert survey[-1].northing_m == pytest.approx(radius, rel=1e-9)


def test_br09_east_and_north_follow_the_azimuth():
    east = minimum_curvature([Station(0.0, 90.0, 90.0), Station(100.0, 90.0, 90.0)])
    assert east[-1].easting_m == pytest.approx(100.0, abs=1e-6)
    assert east[-1].northing_m == pytest.approx(0.0, abs=1e-9)

    south = minimum_curvature([Station(0.0, 90.0, 180.0), Station(100.0, 90.0, 180.0)])
    assert south[-1].northing_m == pytest.approx(-100.0, abs=1e-6)


# --------------------------------------------------------------------------
# The numerics that decide whether it survives real data
# --------------------------------------------------------------------------

def test_br09_a_straight_interval_does_not_raise_a_domain_error():
    """acos of 1 + 1e-16 raises. Any survey with a straight section hits this."""
    survey = minimum_curvature([Station(0.0, 30.0, 45.0), Station(30.0, 30.0, 45.0)])
    assert survey[-1].dogleg_deg == pytest.approx(0.0, abs=1e-9)


def test_br09_ratio_factor_tends_to_one_as_the_dogleg_vanishes():
    assert ratio_factor(0.0) == pytest.approx(1.0)
    assert ratio_factor(1e-9) == pytest.approx(1.0, abs=1e-12)
    # Continuous across the series/closed-form switch, not a step.
    below = ratio_factor(1e-4 - 1e-9)
    above = ratio_factor(1e-4 + 1e-9)
    assert below == pytest.approx(above, rel=1e-9)


def test_br09_ratio_factor_grows_with_the_dogleg():
    assert ratio_factor(0.5) > ratio_factor(0.1) > ratio_factor(0.01) > 1.0


def test_br09_dogleg_severity_is_per_thirty_metres():
    """A 3 degree turn over 30 m is 3 deg/30m; over 15 m it is 6."""
    assert dogleg_severity(math.radians(3.0), 30.0) == pytest.approx(3.0)
    assert dogleg_severity(math.radians(3.0), 15.0) == pytest.approx(6.0)


def test_br09_stations_must_be_in_depth_order():
    with pytest.raises(ValueError, match="measured-depth order"):
        minimum_curvature([Station(100.0, 0.0, 0.0), Station(50.0, 0.0, 0.0)])


# --------------------------------------------------------------------------
# Invariants
# --------------------------------------------------------------------------

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, settings as hyp_settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

station_list = st.lists(
    st.tuples(
        st.floats(min_value=1.0, max_value=200.0, allow_nan=False),   # course
        st.floats(min_value=0.0, max_value=95.0, allow_nan=False),    # inclination
        st.floats(min_value=0.0, max_value=360.0, allow_nan=False),   # azimuth
    ),
    min_size=2, max_size=40,
)


@given(steps=station_list)
@hyp_settings(max_examples=200, deadline=None)
def test_property_br09_tvd_never_exceeds_md(steps):
    """SPEC.md states this outright. A hole cannot be deeper than its length."""
    stations, md = [], 0.0
    for course, inclination, azimuth in steps:
        stations.append(Station(md, inclination, azimuth))
        md += course
    survey = minimum_curvature(stations)
    for station in survey:
        assert station.tvd_m <= station.md_m + 1e-6


@given(steps=station_list)
@hyp_settings(max_examples=200, deadline=None)
def test_property_br09_position_advances_by_no_more_than_the_course(steps):
    """The straight-line distance between two stations cannot exceed the
    measured depth between them: the arc is at least as long as the chord."""
    stations, md = [], 0.0
    for course, inclination, azimuth in steps:
        stations.append(Station(md, inclination, azimuth))
        md += course
    survey = minimum_curvature(stations)
    for previous, current in zip(survey, survey[1:]):
        moved = math.dist(
            (previous.tvd_m, previous.northing_m, previous.easting_m),
            (current.tvd_m, current.northing_m, current.easting_m),
        )
        assert moved <= current.course_length_m + 1e-6


@given(steps=station_list)
@hyp_settings(max_examples=100, deadline=None)
def test_property_br09_a_vertical_survey_stays_on_the_axis(steps):
    stations, md = [], 0.0
    for course, _inclination, azimuth in steps:
        stations.append(Station(md, 0.0, azimuth))
        md += course
    survey = minimum_curvature(stations)
    assert survey[-1].tvd_m == pytest.approx(survey[-1].md_m, abs=1e-6)


# --------------------------------------------------------------------------
# Against the real surveys
# --------------------------------------------------------------------------

TRAJ_DIR = REPO_ROOT / "data" / "landing" / "traj"


def real_surveys() -> dict[str, list[tuple[float, float, float, float]]]:
    """(md, inclination in DEGREES, azimuth in degrees, reported tvd) per document.

    The unit is read from each element's ``uom`` attribute. Four of this
    delivery's trajectories declare ``rad`` and the rest ``dega``, and the
    radian ones read plausibly as degrees - which is what makes the mistake
    survive review.
    """
    from lxml import etree

    def local(tag: object) -> str:
        return str(tag).rsplit("}", 1)[-1]

    surveys: dict[str, list[tuple[float, float, float, float]]] = {}
    for path in sorted(TRAJ_DIR.rglob("*.xml")):
        if not path.is_file():
            continue
        try:
            tree = etree.parse(str(path))
        except Exception:
            continue
        for trajectory in tree.getroot().iter():
            if local(trajectory.tag) != "trajectory":
                continue
            uid = trajectory.get("uid") or path.name
            rows = []
            for station in trajectory:
                if local(station.tag) != "trajectoryStation":
                    continue
                values = {local(n.tag): (n.text or "").strip() for n in station}
                units = {local(n.tag): n.get("uom") for n in station}
                try:
                    converted = Station.from_uom(
                        float(values["md"]), float(values["incl"]),
                        float(values["azi"]), units.get("incl"),
                    )
                    rows.append((
                        converted.md_m, converted.inclination_deg,
                        converted.azimuth_deg, float(values["tvd"]),
                    ))
                except (KeyError, ValueError):
                    continue
            if len(rows) >= 5:
                surveys[uid] = sorted(set(rows))
    return surveys


pytestmark_real = pytest.mark.skipif(
    not TRAJ_DIR.exists(), reason="trajectories not extracted; run 'make extract'"
)


def test_br09_angle_units_are_read_not_assumed():
    """Four Volve surveys declare radians. Reading them as degrees is 188 m out.

    0.371 rad is 21.3 degrees. As "0.371 degrees" it describes a nearly vertical
    hole, which is entirely plausible and entirely wrong - the kind of unit
    error that survives review because the number looks reasonable.
    """
    degrees = Station.from_uom(1000.0, 21.26, 45.0, "dega")
    radians = Station.from_uom(1000.0, math.radians(21.26), math.radians(45.0), "rad")
    assert radians.inclination_deg == pytest.approx(degrees.inclination_deg, rel=1e-9)
    assert radians.azimuth_deg == pytest.approx(degrees.azimuth_deg, rel=1e-9)

    with pytest.raises(ValueError, match="angle unit"):
        Station.from_uom(1000.0, 0.371, 4.46, None)


@pytestmark_real
def test_br09_closure_against_the_contractors_own_tvd_is_under_a_tenth_of_a_percent():
    """The real check: this implementation against the software that steered
    the well. SPEC.md's threshold is 0.1%; the surveys agree to millimetres.

    Each trajectory document is treated separately. Volve's F-15A has two
    'Actual Traj' surveys, one per hole section, and both start at MD 0 -
    merging them interleaves two independent surveys of the same hole and
    produces a path neither contractor computed.
    """
    surveys = real_surveys()
    assert surveys, "no trajectory documents parsed"

    worst = 0.0
    for uid, rows in sorted(surveys.items()):
        computed = minimum_curvature(
            [Station(md, incl, azi) for md, incl, azi, _ in rows],
            tvd_start_m=rows[0][3],
        )
        error = closure_error(computed, [(tvd, 0.0, 0.0) for *_x, tvd in rows])
        tvd_error = max(abs(c.tvd_m - r[3]) for c, r in zip(computed, rows))
        depth = max(r[0] for r in rows) or 1.0
        worst = max(worst, tvd_error / depth * 100.0)
        assert tvd_error < 0.5, f"{uid}: TVD differs by {tvd_error:.3f} m from the contractor"
        assert error["stations"] == len(rows)

    assert worst < 0.1, f"worst closure error {worst:.4f}% exceeds SPEC's 0.1%"


@pytestmark_real
def test_br09_real_surveys_never_put_tvd_below_md():
    for uid, rows in sorted(real_surveys().items()):
        computed = minimum_curvature(
            [Station(md, incl, azi) for md, incl, azi, _ in rows], tvd_start_m=rows[0][3]
        )
        for station in computed:
            assert station.tvd_m <= station.md_m + 1e-6, uid
