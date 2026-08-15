"""The SLO definitions, checked without a warehouse.

What is worth testing here is not the numbers - those come from measurements
and change - but the shape: that every objective can be measured, that a breach
is reported as a breach, and that a known breach does not quietly become
blocking or a blocking one quietly become known.
"""

from __future__ import annotations

import datetime as dt

import pytest

from hugin.slo import SLOS, Measurement, evaluate, format_report


class FakeClient:
    """Answers every scalar with a canned value, keyed by substring."""

    def __init__(self, answers: dict[str, float], default: float = 1_000_000.0) -> None:
        self.answers = answers
        self.default = default
        self.seen: list[str] = []

    def scalar(self, sql: str):
        self.seen.append(sql)
        for needle, value in self.answers.items():
            if needle in sql:
                return value
        return self.default


def test_every_objective_states_a_consequence_and_a_basis() -> None:
    for slo in SLOS:
        assert len(slo.consequence) > 40, f"{slo.name}: a consequence, not a restatement"
        assert len(slo.basis) > 20, f"{slo.name}: say where the threshold came from"
        assert slo.unit, f"{slo.name}: SPEC.md section 9 - a quantity carries its unit"


def test_objective_names_are_unique_and_table_qualified() -> None:
    names = [slo.name for slo in SLOS]
    assert len(names) == len(set(names))
    for slo in SLOS:
        assert slo.name.startswith(slo.table.split(".")[0] + ".")


def test_every_objective_covers_all_three_dimensions() -> None:
    dimensions = {slo.dimension for slo in SLOS}
    assert dimensions == {"freshness", "completeness", "coverage"}


def test_freshness_sql_takes_the_replay_date_not_the_wall_clock() -> None:
    """BR-01. A freshness check against `now()` is not reproducible on a re-run."""
    for slo in SLOS:
        if slo.dimension == "freshness":
            assert "{replay_date}" in slo.sql, f"{slo.name} does not use the replay date"
        assert "current_date" not in slo.sql.lower()
        assert "now()" not in slo.sql.lower()


def test_evaluate_formats_the_replay_date_into_every_query() -> None:
    client = FakeClient({})
    evaluate(client=client, replay_date=dt.date(2014, 4, 7))
    assert any("2014-04-07" in sql for sql in client.seen)
    assert not any("{replay_date}" in sql for sql in client.seen)


def test_a_breach_is_reported_and_blocks() -> None:
    client = FakeClient({"count(*) from gold.fct_production_daily": 12.0})
    measurements = evaluate(client=client, replay_date=dt.date(2014, 4, 7))
    breached = [m for m in measurements if m.slo.name == "gold.fct_production_daily.row_floor"]
    assert breached and not breached[0].ok
    assert breached[0].blocking
    assert "BREACHED" in format_report(measurements, dt.date(2014, 4, 7))


def test_a_known_breach_is_reported_but_does_not_block() -> None:
    known = [slo for slo in SLOS if slo.known_breach]
    assert known, "the point of the field is that it is used"
    for slo in known:
        measurement = Measurement(slo=slo, value=0.0)
        assert not measurement.ok
        assert not measurement.blocking, f"{slo.name} should be tracked, not blocking"
        assert len(slo.known_breach) > 80, f"{slo.name}: a diagnosis, not a shrug"


def test_an_unmeasurable_objective_counts_as_a_breach() -> None:
    """A query that errors is not a pass. Silence is the failure mode to avoid."""

    class Broken:
        def scalar(self, sql):
            raise RuntimeError("table does not exist")

    measurements = evaluate(client=Broken(), replay_date=dt.date(2014, 4, 7))
    assert all(not m.ok for m in measurements)
    assert any(m.blocking for m in measurements)


def test_comparison_directions_are_right_way_round() -> None:
    for slo in SLOS:
        if slo.comparison == ">=":
            assert slo.satisfied(slo.threshold)
            assert not slo.satisfied(slo.threshold - 1)
        else:
            assert slo.satisfied(slo.threshold)
            assert not slo.satisfied(slo.threshold + 1)
        assert not slo.satisfied(None), f"{slo.name}: a missing measurement is not a pass"


@pytest.mark.parametrize("slo", SLOS, ids=lambda s: s.name)
def test_each_objective_measures_the_table_it_names(slo) -> None:
    """The SQL has to touch the table the objective claims to be about."""
    table = slo.table.split(".")[-1]
    assert table in slo.sql, f"{slo.name} does not query {slo.table}"
