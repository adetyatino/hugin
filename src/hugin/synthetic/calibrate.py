"""Measure the real silver tables, so the fixtures are shaped like the field.

The point of calibration is that a fixture generated from measured
distributions behaves like the data in the ways that matter for testing — the
same water-cut trajectory, the same proportion of shut-in days, the same
sentinel spellings — without being, or being presentable as, Volve data.

**What this module will not do is invent a measurement.** Every parameter in
``profiles.json`` is tagged ``calibrated`` or ``assumed``:

    calibrated  a number this module computed from silver, with the row count
                it was computed from recorded beside it
    assumed     a default, with a stated reason why it could not be measured

That distinction is the whole file. SPEC.md section 10 makes honesty about
fixture provenance a licence condition rather than a preference, and a profile
that quietly mixed guesses into measurements would make every downstream figure
unattributable.

Measured on this delivery, some of the things the brief expects to calibrate are
simply not there — several anomaly classes occur zero times, and the WITSML log
curves do not exist at all. Those come out as ``assumed`` with the measurement
that established the absence recorded alongside.
"""

from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hugin.common.trino import TrinoClient

__all__ = ["Calibration", "Parameter", "calibrate", "write_profiles"]

PROFILES_PATH = Path(__file__).resolve().parent / "profiles.json"

SILVER = "iceberg.silver"


@dataclass
class Parameter:
    """One profile value, and where it came from."""

    value: Any
    origin: str  # "calibrated" | "assumed"
    basis: str  # what was measured, or why it could not be
    rows: int | None = None

    def to_dict(self) -> dict:
        out: dict[str, Any] = {"value": self.value, "origin": self.origin, "basis": self.basis}
        if self.rows is not None:
            out["rows_measured"] = self.rows
        return out


@dataclass
class Calibration:
    parameters: dict[str, Parameter] = field(default_factory=dict)
    source_rows: dict[str, int] = field(default_factory=dict)

    def add(self, name: str, parameter: Parameter) -> None:
        self.parameters[name] = parameter

    def to_dict(self) -> dict:
        calibrated = sum(1 for p in self.parameters.values() if p.origin == "calibrated")
        return {
            "calibrated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
            "source": "silver tables built from the real Volve delivery",
            "warning": (
                "These are parameters describing the shape of real data. Data "
                "generated from them is FIXTURE and must never be presented as "
                "measurements of the Volve field - SPEC.md section 10."
            ),
            "rows_behind_calibration": self.source_rows,
            "parameter_counts": {
                "calibrated": calibrated,
                "assumed": len(self.parameters) - calibrated,
            },
            "parameters": {name: p.to_dict() for name, p in sorted(self.parameters.items())},
        }


def _scalar(client: TrinoClient, sql: str, default=0):
    rows = client.execute(sql)
    if not rows or rows[0][0] is None:
        return default
    return rows[0][0]


def calibrate(client: TrinoClient | None = None) -> Calibration:
    """Read silver and produce the profile. Requires the stack to be running."""
    client = client or TrinoClient(schema="silver")
    cal = Calibration()

    daily_rows = _scalar(client, f"select count(*) from {SILVER}.silver_production_daily")
    sample_rows = _scalar(client, f"select count(*) from {SILVER}.silver_log_sample")
    curve_rows = _scalar(client, f"select count(*) from {SILVER}.silver_log_curve")
    identity_rows = _scalar(client, f"select count(*) from {SILVER}.silver_wellbore_identity")
    cal.source_rows = {
        "silver_production_daily": daily_rows,
        "silver_log_sample": sample_rows,
        "silver_log_curve": curve_rows,
        "silver_wellbore_identity": identity_rows,
    }

    _calibrate_production(client, cal, daily_rows)
    _calibrate_uptime(client, cal, daily_rows)
    _calibrate_water_cut(client, cal, daily_rows)
    _calibrate_anomalies(client, cal, daily_rows)
    _calibrate_sentinels(client, cal, curve_rows, sample_rows)
    _calibrate_telemetry(client, cal)
    _calibrate_identity(client, cal, identity_rows)
    return cal


def _calibrate_production(client: TrinoClient, cal: Calibration, rows: int) -> None:
    """Per-well rate distribution, and the decline shape across a well's life."""
    per_well = client.execute(f"""
        select wellbore_uid,
               count(*), round(avg(oil_sm3), 2), round(stddev(oil_sm3), 2),
               round(max(oil_sm3), 2)
        from {SILVER}.silver_production_daily
        where not is_injector
        group by wellbore_uid
        order by wellbore_uid
    """)
    cal.add("production_rate_by_wellbore", Parameter(
        value={
            row[0]: {"days": row[1], "mean_sm3": float(row[2] or 0),
                     "stddev_sm3": float(row[3] or 0), "peak_sm3": float(row[4] or 0)}
            for row in per_well
        },
        origin="calibrated",
        basis="mean, stddev and peak daily oil per producing wellbore",
        rows=rows,
    ))

    # Decline as the ratio of each year's mean to the well's peak year. A
    # hyperbolic fit would be better and needs more producing wells than six.
    decline = client.execute(f"""
        with by_year as (
            select wellbore_uid, year(prod_date) yr, avg(oil_sm3) mean_oil
            from {SILVER}.silver_production_daily
            where not is_injector and oil_sm3 > 0
            group by wellbore_uid, year(prod_date)
        ),
        peaks as (select wellbore_uid, max(mean_oil) peak from by_year group by wellbore_uid)
        select b.wellbore_uid, b.yr, round(b.mean_oil / p.peak, 4)
        from by_year b join peaks p on b.wellbore_uid = p.wellbore_uid
        order by b.wellbore_uid, b.yr
    """)
    shape: dict[str, list[float]] = {}
    for wellbore, _year, fraction in decline:
        shape.setdefault(wellbore, []).append(float(fraction))
    cal.add("decline_shape_by_wellbore", Parameter(
        value=shape,
        origin="calibrated",
        basis="each producing year's mean oil as a fraction of the wellbore's best year",
        rows=rows,
    ))


def _calibrate_uptime(client: TrinoClient, cal: Calibration, rows: int) -> None:
    buckets = client.execute(f"""
        select case when on_stream_hours is null then 'null'
                    when on_stream_hours = 0 then 'shut_in'
                    when on_stream_hours >= 23.5 then 'full'
                    else 'partial' end,
               count(*)
        from {SILVER}.silver_production_daily
        group by 1
    """)
    total = sum(row[1] for row in buckets) or 1
    cal.add("on_stream_hours_distribution", Parameter(
        value={row[0]: round(row[1] / total, 4) for row in buckets},
        origin="calibrated",
        basis="share of production days that are full, partial, shut in, or unreported",
        rows=rows,
    ))

    # Consecutive shut-in days are one shutdown. The islands-and-gaps trick:
    # subtracting a per-wellbore row number from a global one gives a constant
    # for each run. The grouping has to happen outside the window, because a
    # select alias is not in scope in its own GROUP BY.
    runs = _scalar(client, f"""
        select count(*) from (
            select wellbore_uid, grp
            from (
                select wellbore_uid,
                       date_diff('day', date '2000-01-01', prod_date)
                     - row_number() over (partition by wellbore_uid order by prod_date) as grp
                from {SILVER}.silver_production_daily
                where on_stream_hours = 0
            ) runs
            group by wellbore_uid, grp
        ) t
    """)
    cal.add("shutdown_event_count", Parameter(
        value=runs,
        origin="calibrated",
        basis="runs of consecutive zero-uptime days, counted as one shutdown each",
        rows=rows,
    ))


def _calibrate_water_cut(client: TrinoClient, cal: Calibration, rows: int) -> None:
    by_year = client.execute(f"""
        select wellbore_uid, year(prod_date),
               round(avg(case when oil_sm3 + water_sm3 > 0
                              then water_sm3 / (oil_sm3 + water_sm3) end), 4)
        from {SILVER}.silver_production_daily
        where not is_injector
        group by wellbore_uid, year(prod_date)
        order by wellbore_uid, year(prod_date)
    """)
    series: dict[str, list[float]] = {}
    for wellbore, _year, cut in by_year:
        if cut is not None:
            series.setdefault(wellbore, []).append(float(cut))

    rises = []
    for values in series.values():
        if len(values) > 1:
            rises.append((values[-1] - values[0]) / (len(values) - 1))
    cal.add("water_cut_by_wellbore_year", Parameter(
        value=series, origin="calibrated",
        basis="mean daily water cut per wellbore per year", rows=rows,
    ))
    cal.add("water_cut_rise_per_year", Parameter(
        value=round(sum(rises) / len(rises), 4) if rises else 0.0,
        origin="calibrated",
        basis="mean annual increase in water cut across producing wellbores",
        rows=rows,
    ))


def _calibrate_anomalies(client: TrinoClient, cal: Calibration, rows: int) -> None:
    """Anomaly frequencies, measured. Several of them are zero, and stay zero.

    The brief lists five classes to calibrate. On this delivery only one occurs.
    Reporting the other four as small non-zero rates would be inventing defects
    and calling them measurements, so they are recorded as measured-zero and the
    generator's injection rates for them are marked ``assumed``.
    """
    gaps = _scalar(client, f"""
        select coalesce(sum(gap), 0) from (
            select date_diff('day',
                       lag(prod_date) over (partition by wellbore_uid order by prod_date),
                       prod_date) - 1 gap
            from {SILVER}.silver_production_daily) t
        where gap > 0
    """)
    duplicates = _scalar(client, f"""
        select count(*) from (
            select _row_hash from {SILVER}.silver_production_daily
            group by _row_hash having count(*) > 1) t
    """)
    frozen = _scalar(client, f"""
        select count(*) from (
            select wellbore_uid, oil_sm3, count(*) n from (
                select wellbore_uid, prod_date, oil_sm3,
                       row_number() over (partition by wellbore_uid order by prod_date)
                     - row_number() over (partition by wellbore_uid, oil_sm3 order by prod_date) grp
                from {SILVER}.silver_production_daily where oil_sm3 > 0) x
            group by wellbore_uid, oil_sm3, grp having count(*) >= 3) y
    """)
    spikes = _scalar(client, f"""
        select count(*) from (
            select oil_sm3, lag(oil_sm3) over (partition by wellbore_uid order by prod_date) prev,
                   stddev(oil_sm3) over (partition by wellbore_uid) sd
            from {SILVER}.silver_production_daily where not is_injector) t
        where prev is not null and sd > 0 and abs(oil_sm3 - prev) > 5 * sd
    """)

    measured = {
        "dropout_missing_days": gaps,
        "duplicate_rows": duplicates,
        "frozen_value_runs": frozen,
        "spike_days": spikes,
        "clock_skew_events": 0,
    }
    cal.add("anomaly_counts_observed", Parameter(
        value=measured, origin="calibrated",
        basis=(
            "counted in silver_production_daily: calendar gaps inside a wellbore's "
            "span, repeated _row_hash, runs of 3+ identical non-zero volumes, "
            "day-over-day changes beyond 5 sigma. Clock skew is 0 because "
            "production carries a date, not a timestamp, so the class cannot occur"
        ),
        rows=rows,
    ))
    cal.add("anomaly_rate_dropout", Parameter(
        value=round(gaps / rows, 6) if rows else 0.0,
        origin="calibrated",
        basis="missing calendar days as a fraction of observed production days",
        rows=rows,
    ))
    for name, count in (("duplicate", duplicates), ("frozen", frozen), ("spike", spikes),
                        ("clock_skew", 0)):
        cal.add(f"anomaly_rate_{name}", Parameter(
            value=0.0,
            origin="assumed",
            basis=(
                f"measured {count} occurrences in {rows} rows of real production, "
                f"so there is no rate to calibrate. The generator can still inject "
                f"this class at --dirt-level 2, where the rate is a deliberate "
                f"test input rather than a claim about the field"
            ),
            rows=rows,
        ))


def _calibrate_sentinels(client: TrinoClient, cal: Calibration, curves: int, samples: int) -> None:
    spellings = client.execute(f"""
        select sentinel_declared, count(*), count(distinct source_file)
        from {SILVER}.silver_log_curve
        where sentinel_declared is not null and sentinel_declared <> ''
        group by sentinel_declared
        order by count(*) desc
    """)
    total_files = sum(row[2] for row in spellings) or 1
    cal.add("las_sentinel_spellings", Parameter(
        value={row[0]: {"curves": row[1], "files": row[2],
                        "file_share": round(row[2] / total_files, 4)} for row in spellings},
        origin="calibrated",
        basis="every distinct NULL sentinel declared in a LAS ~WELL section, by file count",
        rows=curves,
    ))

    share = client.execute(f"""
        select count(*), sum(case when was_sentinel then 1 else 0 end)
        from {SILVER}.silver_log_sample
    """)[0]
    cal.add("las_sentinel_sample_share", Parameter(
        value=round((share[1] or 0) / share[0], 4) if share[0] else 0.0,
        origin="calibrated",
        basis="fraction of log samples whose value equalled the declared sentinel",
        rows=samples,
    ))


def _calibrate_telemetry(client: TrinoClient, cal: Calibration) -> None:
    """Telemetry channel ranges per rig state — none of which can be measured.

    The delivery contains no WITSML log curves: ``mnemonicList`` appears in zero
    of 10,773 extracted files, and the log directories hold only MetaFileInfo
    listings of curves the export never wrote. There is therefore nothing to
    calibrate channel ranges or rig-state distributions against.

    The values below are physically plausible drilling ranges, and they are
    marked assumed. They exist so the load-scale generator can produce telemetry
    at volume for a throughput test; they are not a description of Volve.
    """
    basis = (
        "NOT MEASURED. This delivery contains no WITSML log curves - mnemonicList "
        "appears in zero of 10,773 files - so no channel range or rig-state "
        "distribution could be computed. These are plausible drilling ranges "
        "used to generate load-test volume, and are not a claim about Volve"
    )
    cal.add("telemetry_channels", Parameter(
        value={
            "bit_depth_m": {"min": 0.0, "max": 4700.0},
            "hole_depth_m": {"min": 0.0, "max": 4700.0},
            "block_position_m": {"min": 0.0, "max": 28.0},
            "hook_load_klbf": {"min": 20.0, "max": 320.0},
            "wob_klbf": {"min": 0.0, "max": 45.0},
            "rpm": {"min": 0.0, "max": 180.0},
            "torque_kftlbf": {"min": 0.0, "max": 22.0},
            "flow_in_lpm": {"min": 0.0, "max": 3600.0},
            "spp_bar": {"min": 0.0, "max": 320.0},
            "rop_mph": {"min": 0.0, "max": 60.0},
        },
        origin="assumed", basis=basis,
    ))
    cal.add("rig_state_distribution", Parameter(
        value={"DRILLING": 0.35, "CIRCULATING": 0.15, "TRIPPING_IN": 0.12,
               "TRIPPING_OUT": 0.12, "CONNECTION": 0.16, "STATIC": 0.10},
        origin="assumed", basis=basis,
    ))
    cal.add("telemetry_sample_interval_seconds", Parameter(
        value=5, origin="assumed",
        basis=basis + ". 5 s is a common WITSML surface-log rate",
    ))


def _calibrate_identity(client: TrinoClient, cal: Calibration, rows: int) -> None:
    stats = client.execute(f"""
        select count(*), count(distinct wellbore_uid),
               sum(case when is_resolved then 0 else 1 end)
        from {SILVER}.silver_wellbore_identity
    """)[0]
    cal.add("identity_variants_per_wellbore", Parameter(
        value=round(stats[0] / stats[1], 2) if stats[1] else 0.0,
        origin="calibrated",
        basis="distinct written identities divided by distinct resolved wellbores",
        rows=rows,
    ))
    cal.add("identity_unresolved_count", Parameter(
        value=stats[2] or 0, origin="calibrated",
        basis="identities in silver with no wellbore_uid", rows=rows,
    ))


def write_profiles(cal: Calibration, path: Path = PROFILES_PATH) -> Path:
    path.write_text(json.dumps(cal.to_dict(), indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="python -m hugin.synthetic.calibrate")
    parser.add_argument("--out", type=Path, default=PROFILES_PATH)
    args = parser.parse_args(argv)

    client = TrinoClient(schema="silver")
    if not client.wait_until_ready(attempts=10, delay=2):
        raise SystemExit(
            "Trino is not accepting queries. Calibration reads the real silver "
            "tables; start the stack with 'make up' and load them first."
        )
    cal = calibrate(client)
    written = write_profiles(cal, args.out)
    summary = cal.to_dict()["parameter_counts"]
    print(f"wrote {written}")
    print(f"  {summary['calibrated']} calibrated, {summary['assumed']} assumed")
    for name, parameter in sorted(cal.parameters.items()):
        if parameter.origin == "assumed":
            print(f"  assumed: {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
