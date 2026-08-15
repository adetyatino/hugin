"""Service level objectives for the gold layer, and the check that enforces them.

An SLO here is a number a table must satisfy, the SQL that measures it, and a
sentence saying what goes wrong when it does not. All three are required. A
threshold with no measurement is a wish, and a measurement with no stated
consequence is a dashboard.

Three dimensions, and they fail differently:

**Freshness** — how far the table's newest business date lags the replay clock
(BR-01). Measured in replay days, not real ones, because the pipeline's clock
is the replay clock: a table that is current as of replay day 400 is fresh even
though the date on it is 2009. A stale table is the failure nobody notices,
because every query still returns rows.

**Completeness** — row floors and non-null rates. A table that lost 90% of its
rows still answers every query, still passes every `not_null` test on the rows
that remain, and is wrong. dbt tests ask "is this row legal"; these ask "is
enough of it here".

**Coverage** — BR-12's identity resolution, from `mart_identity_coverage`. This
is the one that can legitimately go *down* when a new delivery arrives with
names nothing recognises, which is why it is an objective rather than a test.

Thresholds are set **below** the measured value with headroom, so an SLO does
not fail on legitimate variation. Two exceptions are deliberate and are marked
`known_breach`: they encode what the table is supposed to contain rather than
what it currently does, they fail today, and `docs/slo.md` says why. An SLO set
to today's broken number would make the breach invisible, which is the opposite
of the point.

Usage:

    python -m hugin.slo                # evaluate everything, exit 1 on breach
    python -m hugin.slo --json out.json
    python -m hugin.slo --include-known-breaches   # fail on those too

Airflow calls `evaluate` from the `slo_check` task in `hugin_daily`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from dataclasses import dataclass
from typing import Any, Literal

__all__ = ["Slo", "SLOS", "Measurement", "evaluate", "format_report"]

Dimension = Literal["freshness", "completeness", "coverage"]
Comparison = Literal[">=", "<="]


@dataclass(frozen=True)
class Slo:
    """One objective. Name it after what it protects, not after the metric."""

    name: str
    table: str
    dimension: Dimension
    #: The measurement, as one row with one numeric column.
    sql: str
    threshold: float
    comparison: Comparison
    unit: str
    #: What breaks when this is breached. Not what the metric means.
    consequence: str
    #: Where the threshold came from. "measured 14,859 on 2026-08-13" beats
    #: "seems about right", and stops the next person tightening it blindly.
    basis: str
    #: Set when the objective is deliberately not met yet. It is reported and
    #: does not fail the DAG unless --include-known-breaches is passed.
    known_breach: str = ""

    def satisfied(self, value: float | None) -> bool:
        if value is None:
            return False
        return value >= self.threshold if self.comparison == ">=" else value <= self.threshold


@dataclass
class Measurement:
    slo: Slo
    value: float | None
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and self.slo.satisfied(self.value)

    @property
    def blocking(self) -> bool:
        """A breach that should stop the pipeline."""
        return not self.ok and not self.slo.known_breach

    def line(self) -> str:
        status = "ok  " if self.ok else ("known" if self.slo.known_breach else "BREACH")
        shown = "error" if self.error else f"{self.value:,.4g}"
        return (
            f"{status:<7} {self.slo.name:<46} {shown:>12} {self.slo.unit:<12} "
            f"({self.slo.comparison} {self.slo.threshold:,.4g})"
        )


# --------------------------------------------------------------------------
# Freshness
#
# `_days_behind` compares a table's newest business date against the replay
# clock's current date. The clock is asked for the date rather than told it,
# so this measures the same thing whether it runs inside the DAG or from a
# terminal at three in the morning.
# --------------------------------------------------------------------------


def _freshness_sql(table: str, date_column: str) -> str:
    return f"select date_diff('day', max({date_column}), date '{{replay_date}}') from {table}"


def _freshness_sql_from_key(table: str, key_column: str) -> str:
    """For tables keyed by an integer date key like 20140407."""
    return (
        f"select date_diff('day', "
        f"max(date_parse(cast({key_column} as varchar), '%Y%m%d')), "
        f"date '{{replay_date}}') from {table}"
    )


SLOS: tuple[Slo, ...] = (
    # -- freshness ---------------------------------------------------------
    Slo(
        name="gold.fct_production_daily.freshness",
        table="gold.fct_production_daily",
        dimension="freshness",
        sql=_freshness_sql("gold.fct_production_daily", "prod_date"),
        threshold=2,
        comparison="<=",
        unit="replay days",
        consequence=(
            "Every production figure downstream - mart_well_performance, the allocation "
            "reconciliation, the Metabase dashboard - is answering about a day that has "
            "already passed, and no query will say so."
        ),
        basis=(
            "Two replay days of slack: one for the run itself, one for a retry. "
            "A negative value means the table is ahead of the clock, which a backfill "
            "makes normal and is not a breach."
        ),
    ),
    Slo(
        name="gold.fct_production_monthly.freshness",
        table="gold.fct_production_monthly",
        dimension="freshness",
        sql=_freshness_sql_from_key("gold.fct_production_monthly", "month_key * 100 + 1"),
        threshold=62,
        comparison="<=",
        unit="replay days",
        consequence=(
            "BR-02's reconciliation compares daily against monthly. A stale monthly side "
            "makes every variance look like a data problem in the daily side."
        ),
        basis=(
            "Two months of slack, because the reported monthly figure for a month only "
            "exists after that month has closed. A tighter threshold would fail every "
            "month-end by construction."
        ),
    ),
    # -- completeness: the production spine --------------------------------
    Slo(
        name="gold.fct_production_daily.row_floor",
        table="gold.fct_production_daily",
        dimension="completeness",
        sql="select count(*) from gold.fct_production_daily",
        threshold=14000,
        comparison=">=",
        unit="rows",
        consequence=(
            "Silently missing production days. Every aggregate stays valid-looking and "
            "every total is low."
        ),
        basis=(
            "Measured 14,859 on 2026-08-13; floor set ~6% below, with headroom for a "
            "partial replay."
        ),
    ),
    Slo(
        name="gold.fct_production_daily.wellbore_key_resolved",
        table="gold.fct_production_daily",
        dimension="completeness",
        sql=(
            "select 100.0 * sum(case when wellbore_key is not null then 1 else 0 end) "
            "/ nullif(count(*), 0) from gold.fct_production_daily"
        ),
        threshold=100.0,
        comparison=">=",
        unit="% of rows",
        consequence=(
            "A production row with no wellbore key joins to nothing and disappears from "
            "every per-well figure while still counting in the total. BR-12 routes "
            "unresolved identities to a surrogate key rather than to NULL precisely so "
            "this stays at 100."
        ),
        basis="Measured 100% on 2026-08-13. This one is exact on purpose: the model guarantees it.",
    ),
    Slo(
        name="gold.fct_production_monthly.row_floor",
        table="gold.fct_production_monthly",
        dimension="completeness",
        sql="select count(*) from gold.fct_production_monthly",
        threshold=480,
        comparison=">=",
        unit="rows",
        consequence="BR-02 loses the side it reconciles against.",
        basis="Measured 497 on 2026-08-13.",
    ),
    # -- completeness: dimensions -----------------------------------------
    Slo(
        name="gold.dim_wellbore.wellbore_floor",
        table="gold.dim_wellbore",
        dimension="completeness",
        sql="select count(distinct wellbore_uid) from gold.dim_wellbore",
        threshold=7,
        comparison=">=",
        unit="wellbores",
        consequence=(
            "A missing wellbore takes its whole production history out of every "
            "per-well report, and the field total still looks plausible."
        ),
        basis="Measured 7 distinct wellbore_uid across 18 SCD2 versions on 2026-08-13.",
    ),
    Slo(
        name="gold.dim_wellbore.exactly_one_current_version",
        table="gold.dim_wellbore",
        dimension="completeness",
        sql=(
            "select count(*) from (select wellbore_uid, "
            "sum(case when is_current then 1 else 0 end) "
            "as current_versions from gold.dim_wellbore group by wellbore_uid) t "
            "where current_versions <> 1"
        ),
        threshold=0,
        comparison="<=",
        unit="wellbores in breach",
        consequence=(
            "Two current versions double-counts every fact joined to the dimension; zero "
            "current versions drops them. Both look like a production change rather than "
            "a dimension bug."
        ),
        basis=(
            "Structural. assert_gold_scd2_has_exactly_one_current_version.sql tests "
            "the same rule per build; this watches it between builds."
        ),
    ),
    Slo(
        name="gold.dim_date.covers_field_life",
        table="gold.dim_date",
        dimension="completeness",
        sql="select count(*) from gold.dim_date",
        threshold=3044,
        comparison=">=",
        unit="days",
        consequence=(
            "dim_date is deliberately built over field life rather than over loaded data, "
            "so a join against it never drops a fact for a day nobody has ingested yet. "
            "A short spine silently reintroduces that."
        ),
        basis=(
            "2008-06-01 to 2016-09-30 inclusive is 3,044 days. Exact, not a floor: "
            "the spine is generated rather than loaded."
        ),
    ),
    # -- completeness: logs, trajectory, simulation ------------------------
    Slo(
        name="gold.fct_log_sample.row_floor",
        table="gold.fct_log_sample",
        dimension="completeness",
        sql="select count(*) from gold.fct_log_sample",
        threshold=30000,
        comparison=">=",
        unit="rows",
        consequence="Log curves vanish from the depth-range queries without any error.",
        basis=(
            "Measured 30,421 on 2026-08-13 under the bounded LAS load "
            "(--max-las-files 8). The floor tracks the bounded load, not the full one."
        ),
    ),
    Slo(
        name="gold.fct_log_sample.curve_key_resolved",
        table="gold.fct_log_sample",
        dimension="completeness",
        sql=(
            "select 100.0 * sum(case when curve_key is not null then 1 else 0 end) "
            "/ nullif(count(*), 0) from gold.fct_log_sample"
        ),
        threshold=99.0,
        comparison=">=",
        unit="% of rows",
        consequence=(
            "Without a curve key, a sample cannot be joined to what the curve is - its "
            "unit, its description, whether the mnemonic means different things in "
            "different files. The readings are there and unusable."
        ),
        basis="What the model is for. See known_breach.",
        known_breach=(
            "0% as of 2026-08-13. bronze.las_curve_header is empty, so silver_log_curve "
            "and dim_curve are empty, so the join in fct_log_sample yields NULL for every "
            "row. The reader exists and is registered (LasCurveHeaderReader in "
            "hugin.ingestion.las, wired in load_job.all_readers) and emits only on the "
            "static load date; the static load that populated las_sample did not populate "
            "it. Diagnosis is in docs/slo.md; the fix is a reload, not a code change."
        ),
    ),
    Slo(
        name="gold.dim_curve.row_floor",
        table="gold.dim_curve",
        dimension="completeness",
        sql="select count(*) from gold.dim_curve",
        threshold=1,
        comparison=">=",
        unit="rows",
        consequence=(
            "An empty curve dimension is what makes the curve_key breach above possible. "
            "It is listed separately because the cause is here and the symptom is there."
        ),
        basis=(
            "Any non-empty dimension. fct_log_sample holds 196 distinct mnemonics, so "
            "the true figure should be 196."
        ),
        known_breach=(
            "0 rows as of 2026-08-13. Same root cause as "
            "gold.fct_log_sample.curve_key_resolved: bronze.las_curve_header is empty."
        ),
    ),
    Slo(
        name="gold.fct_trajectory.row_floor",
        table="gold.fct_trajectory",
        dimension="completeness",
        sql="select count(*) from gold.fct_trajectory",
        threshold=450,
        comparison=">=",
        unit="stations",
        consequence=(
            "BR-09's minimum-curvature path is computed per station. Missing stations "
            "shorten the wellbore without making the geometry look wrong."
        ),
        basis="Measured 475 stations across 2 trajectories on 2026-08-13.",
    ),
    Slo(
        name="gold.fct_trajectory.crs_declared",
        table="gold.fct_trajectory",
        dimension="completeness",
        sql=(
            "select 100.0 * sum(case when source_crs is not null then 1 else 0 end) "
            "/ nullif(count(*), 0) from gold.fct_trajectory"
        ),
        threshold=100.0,
        comparison=">=",
        unit="% of rows",
        consequence=(
            "BR-10 and the rule in CLAUDE.md: never assume a CRS. A station with no "
            "declared CRS is a coordinate whose datum is a guess, and in the North Sea "
            "the ED50/WGS84 guess is wrong by hundreds of metres."
        ),
        basis=(
            "What BR-10 requires. See known_breach for why it is not met, and why "
            "that is not a bug."
        ),
        known_breach=(
            "0% as of 2026-08-13, and the cause is in the source rather than in the code. "
            "The directional survey files declare no CRS, and fct_trajectory says so in "
            "its header: northing_offset_m and easting_offset_m are offsets from the well "
            "reference point, not projected coordinates, which is why they are named "
            "_offset_. There is nothing to declare a CRS about until a surface location "
            "with a datum is read from another source. The objective is kept at 100% and "
            "left breached rather than lowered, because lowering it would encode the "
            "absence as acceptable, and the day a projected coordinate does arrive it "
            "must carry its datum."
        ),
    ),
    Slo(
        name="gold.fct_simulation.row_floor",
        table="gold.fct_simulation",
        dimension="completeness",
        sql="select count(*) from gold.fct_simulation",
        threshold=180,
        comparison=">=",
        unit="rows",
        consequence="mart_sim_vs_actual loses the simulated side of its comparison.",
        basis="Measured 183 on 2026-08-13, from a single Eclipse report date.",
    ),
    # -- coverage: BR-12 ---------------------------------------------------
    Slo(
        name="mart.identity_coverage.total",
        table="mart.mart_identity_coverage",
        dimension="coverage",
        sql=(
            "select resolved_pct from mart.mart_identity_coverage where source_system = 'TOTAL'"
        ),
        threshold=95.0,
        comparison=">=",
        unit="% resolved",
        consequence=(
            "Below this, enough wellbore identities are unresolved that per-well figures "
            "are missing production that the field total still contains. The gap is the "
            "kind that reads as a well being shut in."
        ),
        basis=(
            "Measured 100% across 44 identities on 2026-08-13. The objective is set at 95 "
            "rather than 100 deliberately: BR-12 is allowed to fail to resolve a name, and "
            "recording that is the whole design. What is not allowed is failing quietly, "
            "or at scale."
        ),
    ),
    Slo(
        name="mart.identity_coverage.no_system_below_half",
        table="mart.mart_identity_coverage",
        dimension="coverage",
        sql=(
            "select count(*) from mart.mart_identity_coverage "
            "where not is_total_row and resolved_pct < 50"
        ),
        threshold=0,
        comparison="<=",
        unit="source systems in breach",
        consequence=(
            "The total can stay healthy while one source system resolves almost nothing - "
            "WITSML contributes 2 identities and PROD contributes 14, so a total-only "
            "objective would not notice WITSML failing completely."
        ),
        basis="Measured: every source system at 100% on 2026-08-13.",
    ),
)


# --------------------------------------------------------------------------


def current_replay_date() -> dt.date:
    """Where the replay clock stands now. BR-01."""
    from hugin.common.config import get_settings

    return get_settings().replay_clock().replay_date(dt.datetime.now(dt.UTC))


def evaluate(
    client=None,
    replay_date: dt.date | None = None,
    slos: tuple[Slo, ...] = SLOS,
) -> list[Measurement]:
    """Measure every SLO. One failing measurement does not stop the others.

    Stopping at the first breach would report one problem and stay silent about
    whether anything else is wrong, which is the question being asked when
    something has already gone wrong.
    """
    if client is None:
        from hugin.common.trino import TrinoClient

        client = TrinoClient(schema="gold")

    as_of = replay_date or current_replay_date()
    measurements: list[Measurement] = []
    for slo in slos:
        sql = slo.sql.format(replay_date=as_of.isoformat())
        try:
            value = client.scalar(sql)
            measurements.append(
                Measurement(slo=slo, value=None if value is None else float(value))
            )
        except Exception as exc:  # noqa: BLE001 - an unmeasurable SLO is a breach
            measurements.append(
                Measurement(slo=slo, value=None, error=f"{type(exc).__name__}: {exc}")
            )
    return measurements


def format_report(measurements: list[Measurement], replay_date: dt.date) -> str:
    lines = [
        f"SLO check at replay date {replay_date.isoformat()}",
        "",
    ]
    for dimension in ("freshness", "completeness", "coverage"):
        group = [m for m in measurements if m.slo.dimension == dimension]
        if not group:
            continue
        lines.append(f"-- {dimension} " + "-" * (60 - len(dimension)))
        lines.extend(m.line() for m in group)
        lines.append("")

    blocking = [m for m in measurements if m.blocking]
    known = [m for m in measurements if not m.ok and m.slo.known_breach]

    if known:
        lines.append("Known breaches, tracked in docs/slo.md, not blocking:")
        for m in known:
            lines.append(f"  {m.slo.name}: {m.slo.known_breach.splitlines()[0]}")
        lines.append("")

    if blocking:
        lines.append("BREACHED:")
        for m in blocking:
            detail = m.error or (
                f"{m.value:,.4g} {m.slo.unit}, "
                f"objective {m.slo.comparison} {m.slo.threshold:,.4g}"
            )
            lines.append(f"  {m.slo.name}: {detail}")
            lines.append(f"      {m.slo.consequence}")
    else:
        lines.append(
            f"{len(measurements) - len(known)} objectives met, {len(known)} known breaches."
        )

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", help="write measurements as JSON")
    parser.add_argument(
        "--include-known-breaches",
        action="store_true",
        help="fail on the objectives docs/slo.md records as not yet met",
    )
    parser.add_argument("--replay-date", help="evaluate as of this replay date rather than now")
    args = parser.parse_args(argv)

    as_of = dt.date.fromisoformat(args.replay_date) if args.replay_date else current_replay_date()
    measurements = evaluate(replay_date=as_of)
    print(format_report(measurements, as_of))

    if args.json:
        payload: list[dict[str, Any]] = [
            {
                "name": m.slo.name,
                "table": m.slo.table,
                "dimension": m.slo.dimension,
                "threshold": m.slo.threshold,
                "comparison": m.slo.comparison,
                "unit": m.slo.unit,
                "value": m.value,
                "ok": m.ok,
                "known_breach": bool(m.slo.known_breach),
                "error": m.error,
            }
            for m in measurements
        ]
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    failed = [m for m in measurements if (not m.ok if args.include_known_breaches else m.blocking)]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
