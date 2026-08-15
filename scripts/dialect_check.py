"""Semantic equivalence of the dialect macros across the three targets.

SPEC.md section 12 wants the same dbt models running on Trino, DuckDB and
Databricks SQL. Trino and DuckDB are proven by `make dbt-build`, which runs the
models against both. Databricks cannot be proven that way here — there is no
workspace, and ADR 007 records why one is not being invented.

What this script proves instead is narrower and still worth having: that for
every macro in ``transform/macros/dialect.sql``, the SQL the *databricks*
dispatch produces returns **the same answer** as the SQL the *duckdb* dispatch
produces, given the same input. The Databricks side runs on Apache Spark 3.5 in
the compose stack, which is what Databricks Runtime is built on.

Why equivalence and not just "does it parse". The failure that motivated this
is `date_diff('second', a, b)`. Databricks has a two-argument `datediff` that
returns whole *days*. Handed two telemetry samples nine seconds apart it does
not raise — it returns 0, the rate of penetration becomes 0, and every rig
state in BR-06 becomes STATIC. A parse check passes that. Comparing answers
does not.

The macros are not copied here. They are rendered out of ``dialect.sql`` with a
``adapter.dispatch`` emulation that resolves exactly as dbt's does —
``<target>__name`` if it exists, ``default__name`` otherwise — so editing a
macro changes what this script tests, and deleting a databricks implementation
makes it silently fall back to the default and be checked as such.

Usage:

    python scripts/dialect_check.py                 # both engines, compare
    python scripts/dialect_check.py --show-sql      # print what is being run
    python scripts/dialect_check.py --json out.json # machine-readable results

Needs the stream profile up for the Spark half:

    docker compose --profile stream up -d spark
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MACRO_FILE = REPO_ROOT / "transform" / "macros" / "dialect.sql"

# Written into ./data, which the compose file mounts at /opt/hugin/data, because
# that is the only channel into the Spark container that does not need a copy.
CASE_DIR = REPO_ROOT / "data" / "_dialect"
CONTAINER_CASE_FILE = "/opt/hugin/data/_dialect/cases.json"


# --------------------------------------------------------------------------
# Rendering the macros as dbt would
# --------------------------------------------------------------------------


def macro_module(target: str):
    """Render dialect.sql under a fake dbt, dispatching for `target`."""
    from jinja2 import Environment, FileSystemLoader

    # jinja2.ext.do is what supplies {% do %}, which dbt enables by default and
    # dialect.sql uses to build the surrogate-key parts list.
    env = Environment(
        loader=FileSystemLoader(str(MACRO_FILE.parent)),
        extensions=["jinja2.ext.do"],
    )
    holder: dict[str, object] = {}

    class Adapter:
        """dbt's adapter.dispatch, reimplemented in the four lines it is."""

        @staticmethod
        def dispatch(name: str, _namespace: str):
            module = holder["module"]
            specific = getattr(module, f"{target}__{name}", None)
            if specific is not None:
                return specific
            default = getattr(module, f"default__{name}", None)
            if default is None:
                raise KeyError(f"no implementation of {name} for {target} and no default")
            return default

    env.globals["adapter"] = Adapter
    # dbt's macro wrappers are `{{ return(adapter.dispatch(...)(args)) }}`.
    # In Jinja that is a call to a global named `return`, which is not a keyword
    # here, so it can simply be the identity.
    env.globals["return"] = lambda value: value

    module = env.get_template(MACRO_FILE.name).make_module()
    holder["module"] = module
    return module


def render(target: str, macro: str, *args) -> str:
    module = macro_module(target)
    fn = getattr(module, macro, None)
    if fn is None:
        raise KeyError(f"{macro} is not defined in {MACRO_FILE.name}")
    return str(fn(*args)).strip()


# --------------------------------------------------------------------------
# The cases
# --------------------------------------------------------------------------


@dataclass
class Case:
    name: str
    macro: str
    why: str
    build: object  # (rendered_sql) -> full query
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)

    def sql(self, target: str) -> str:
        # Builders get the rendered macro plus that target's own text cast, so the
        # scaffolding around a case is no less portable than the case itself.
        text = lambda column: render(target, 'hugin_as_text', column)  # noqa: E731
        return self.build(render(target, self.macro, *self.args, **self.kwargs), text)


# A four-row inline table, written with SELECT ... UNION ALL rather than VALUES
# and a DDL type list. Spark spells text STRING and DuckDB spells it VARCHAR, so
# naming a type in the fixture would be testing the fixture rather than the
# macro. Literals are inferred identically by both.
SAMPLE = """
select '15/9-F-15 D' as uid, '41000' as serial, '1,5' as num, '-999.25' as sentinel union all
select '15/9-F-4'   as uid, '39600' as serial, ' 12 345,6 ' as num, '-999.25' as sentinel union all
select '15/9-F-11 T2' as uid, '43000' as serial, 'nan' as num, '-9999' as sentinel union all
select 'NO 15/9-F-1 C' as uid, '39630' as serial, '3.25' as num, '-999.2500' as sentinel
"""

TELEMETRY = """
select timestamp '2016-08-04 10:00:00' as ts, 12.0 as block_position_m union all
select timestamp '2016-08-04 10:03:00' as ts, 18.5 as block_position_m union all
select timestamp '2016-08-04 10:07:30' as ts, 11.0 as block_position_m union all
select timestamp '2016-08-04 10:19:00' as ts, 25.5 as block_position_m union all
select timestamp '2016-08-04 10:24:00' as ts, 25.5 as block_position_m
"""


CASES: list[Case] = [
    Case(
        name="hugin_as_text",
        macro="hugin_as_text",
        args=("uid",),
        why="Spark rejects an unlengthed VARCHAR; its text type is STRING.",
        build=lambda sql, text: f"select {sql} as v from ({SAMPLE}) t order by 1",
    ),
    Case(
        name="hugin_as_text on a number",
        macro="hugin_as_text",
        args=("cast(serial as double)",),
        why=(
            "The one that could differ silently: this cast sits inside every "
            "surrogate key, so a different text form is a different md5."
        ),
        build=lambda sql, text: f"select {sql} as v from ({SAMPLE}) t order by 1",
    ),
    Case(
        name="hugin_surrogate_key",
        macro="hugin_surrogate_key",
        args=(["uid", "serial"],),
        why=(
            "Every _key column in the warehouse. Must be byte-identical, or joins "
            "break across engines."
        ),
        build=lambda sql, text: f"select {sql} as v from ({SAMPLE}) t order by 1",
    ),
    Case(
        name="hugin_date_from_excel_serial",
        macro="hugin_date_from_excel_serial",
        args=("serial",),
        why=(
            "date_add takes its arguments the other way round from Trino's. Spark 3.5 "
            "accepts date + integer even with ANSI on, so this dispatch is precautionary."
        ),
        build=lambda sql, text: f"select cast({sql} as date) as v from ({SAMPLE}) t order by 1",
    ),
    Case(
        name="hugin_date_from_iso",
        macro="hugin_date_from_iso",
        args=("iso",),
        why=(
            "Daily drilling reports write an offset: 2016-08-04T00:00:00+02:00. The date is "
            "taken in the offset the source wrote, so all three engines must agree that the "
            "first ten characters are the answer and not convert to UTC first."
        ),
        build=lambda sql, text: (
            f"select cast({sql} as date) as v from ("
            "  select '2016-08-04T00:00:00+02:00' as iso union all"
            "  select '2013-04-01T00:00:00+01:00' as iso union all"
            "  select 'not a timestamp' as iso"
            ") t order by 1"
        ),
    ),
    Case(
        name="hugin_to_number",
        macro="hugin_to_number",
        args=("num",),
        why=(
            "try_cast and the decimal-comma repair. Checks Spark's try_cast returns "
            "NULL rather than raising."
        ),
        build=lambda sql, text: f"select {sql} as v from ({SAMPLE}) t order by 1",
    ),
    Case(
        name="hugin_null_if_sentinel",
        macro="hugin_null_if_sentinel",
        args=("num", "sentinel"),
        why=(
            "BR-08. A sentinel surviving as a number on one engine and not the other "
            "is the worst kind of drift."
        ),
        build=lambda sql, text: f"select {sql} as v from ({SAMPLE}) t order by 1",
    ),
    Case(
        name="hugin_safe_divide",
        macro="hugin_safe_divide",
        args=("1.0", "0.0"),
        why=(
            "Water cut on a shut-in day. Spark returns NULL for x/0 anyway; the macro "
            "must not turn that into an error."
        ),
        build=lambda sql, text: f"select {sql} as v",
    ),
    Case(
        name="hugin_month_key",
        macro="hugin_month_key",
        args=("date '2014-04-07'",),
        why="extract() arithmetic. Both should give 201404.",
        build=lambda sql, text: f"select cast({sql} as bigint) as v",
    ),
    Case(
        name="hugin_date_key",
        macro="hugin_date_key",
        args=("date '2014-04-07'",),
        why="Same, at day grain: 20140407.",
        build=lambda sql, text: f"select cast({sql} as bigint) as v",
    ),
    Case(
        name="hugin_strpos",
        macro="hugin_strpos",
        args=("uid", "' '"),
        why=(
            "Splits '15/9-F-15 D' into well and sidetrack. Spark has no strpos, and "
            "locate() reverses the arguments."
        ),
        build=lambda sql, text: f"select {sql} as v from ({SAMPLE}) t order by 1",
    ),
    Case(
        name="hugin_strpos, sidetrack split",
        macro="hugin_strpos",
        args=("uid", "' '"),
        why=(
            "The macro in the position the model actually uses it: the well_code and "
            "sidetrack_code split."
        ),
        build=lambda sql, text: (
            f"select case when {sql} > 0 then substr(uid, 1, {sql} - 1) else uid end as v "
            f"from ({SAMPLE}) t order by 1"
        ),
    ),
    Case(
        name="hugin_seconds_between",
        macro="hugin_seconds_between",
        args=("prev_ts", "ts"),
        why=(
            "The one that fails silently. Databricks' two-argument datediff returns whole days, "
            "which would send every rig state in BR-06 to STATIC without raising anything."
        ),
        build=lambda sql, text: (
            f"select {sql} as v from ("
            f"  select ts, lag(ts) over (order by ts) as prev_ts from ({TELEMETRY}) s"
            f") w where prev_ts is not null order by 1"
        ),
    ),
    Case(
        name="hugin_minutes_preceding",
        macro="hugin_minutes_preceding",
        args=(10,),
        why=(
            "The trailing block-travel window in fct_drilling_state. Spark's parser wants an "
            "unquoted number and a plural unit."
        ),
        build=lambda sql, text: (
            "select cast(travel as double) as v from ("
            "  select max(block_position_m) over ("
            f"    order by ts range between {sql} and current row"
            "  ) - min(block_position_m) over ("
            f"    order by ts range between {sql} and current row"
            "  ) as travel"
            f"  from ({TELEMETRY}) s"
            ") w order by 1"
        ),
    ),
    Case(
        name="hugin_date_spine",
        macro="hugin_date_spine",
        args=("2008-06-01", "2016-09-30"),
        why="dim_date over field life. Spark expands an array with explode(), not unnest().",
        build=lambda sql, text: (
            # Three facts about the spine as text, because a UNION of a count
            # and two dates has to agree on a type and text is the one both
            # engines spell the same way.
            f"select concat('rows=', {text('count(*)')}) as v from ({sql}) spine "
            f"union all select concat('min=', {text('min(calendar_date)')}) from ({sql}) spine "
            f"union all select concat('max=', {text('max(calendar_date)')}) from ({sql}) spine"
        ),
    ),
]


# --------------------------------------------------------------------------
# Engines
# --------------------------------------------------------------------------


def run_duckdb(queries: dict[str, str]) -> dict[str, object]:
    import duckdb

    con = duckdb.connect()
    out: dict[str, object] = {}
    for name, sql in queries.items():
        try:
            rows = con.execute(sql).fetchall()
            out[name] = {"ok": True, "rows": [[stringify(v) for v in r] for r in rows]}
        except Exception as exc:  # noqa: BLE001 - the failure is the result
            out[name] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return out


SPARK_WORKER = r'''
import json, sys, datetime, decimal
from pyspark.sql import SparkSession

with open("__CASES__") as fh:
    queries = json.load(fh)

# ANSI mode on. Databricks SQL warehouses enable it by default and OSS Spark
# does not, so a check run under the OSS default would be lenient in exactly
# the places Databricks is strict - overflow, bad casts, division by zero.
spark = (SparkSession.builder.master("local[1]")
         .appName("hugin-dialect-check")
         .config("spark.ui.enabled", "false")
         .config("spark.sql.ansi.enabled", "true")
         .config("spark.sql.session.timeZone", "UTC")
         .getOrCreate())
spark.sparkContext.setLogLevel("ERROR")

def stringify(v):
    if v is None:
        return None
    if isinstance(v, float):
        return repr(round(v, 9))
    if isinstance(v, decimal.Decimal):
        return repr(round(float(v), 9))
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()
    return str(v)

out = {}
for name, sql in queries.items():
    try:
        rows = spark.sql(sql).collect()
        out[name] = {"ok": True, "rows": [[stringify(v) for v in r] for r in rows]}
    except Exception as exc:
        out[name] = {"ok": False, "error": "%s: %s" % (type(exc).__name__, str(exc).split("\n")[0])}

sys.stdout.write("---RESULTS---" + json.dumps(out))
'''


def run_spark(queries: dict[str, str]) -> dict[str, object]:
    CASE_DIR.mkdir(parents=True, exist_ok=True)
    (CASE_DIR / "cases.json").write_text(json.dumps(queries), encoding="utf-8")

    worker = SPARK_WORKER.replace("__CASES__", CONTAINER_CASE_FILE)
    # The apache/spark image ships pyspark under /opt/spark/python but does not
    # put it on the default path — spark-submit adds it. Adding it here keeps
    # the worker a plain python3 process, which is what makes the errors legible.
    pythonpath = "/opt/spark/python:/opt/spark/python/lib/py4j-0.10.9.7-src.zip:/opt/hugin/src"
    proc = subprocess.run(
        [
            "docker", "compose", "exec", "-T",
            "-e", f"PYTHONPATH={pythonpath}",
            "spark", "python3", "-",
        ],
        input=worker,
        capture_output=True,
        text=True,
        # Explicit, because the worker crosses a pipe into Linux and Windows
        # would otherwise encode it as cp1252 and hand python3 bytes it rejects.
        encoding="utf-8",
        cwd=REPO_ROOT,
    )
    marker = "---RESULTS---"
    if marker not in proc.stdout:
        raise SystemExit(
            "Spark produced no results. Is the stream profile up?\n"
            "  docker compose --profile stream up -d spark\n\n"
            f"stdout tail:\n{proc.stdout[-2000:]}\n\nstderr tail:\n{proc.stderr[-2000:]}"
        )
    return json.loads(proc.stdout.split(marker, 1)[1])


def ordered(rows):
    """Sort rows None-safely, so NULL placement is not mistaken for a result."""
    if rows is None:
        return None
    return sorted(rows, key=lambda row: [(value is None, value or "") for value in row])


def stringify(value) -> str | None:
    import datetime
    import decimal

    if value is None:
        return None
    if isinstance(value, float):
        return repr(round(value, 9))
    if isinstance(value, decimal.Decimal):
        return repr(round(float(value), 9))
    if isinstance(value, datetime.date | datetime.datetime):
        return value.isoformat()
    return str(value)


# --------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show-sql", action="store_true", help="print both renderings per case")
    parser.add_argument("--json", type=Path, help="write results as JSON")
    parser.add_argument(
        "--engine",
        choices=["both", "duckdb"],
        default="both",
        help="duckdb only skips the container, for a syntax check without the stack",
    )
    args = parser.parse_args()

    duck_sql = {c.name: c.sql("duckdb") for c in CASES}
    dbx_sql = {c.name: c.sql("databricks") for c in CASES}

    if args.show_sql:
        for case in CASES:
            print(f"\n=== {case.name} ===\n{case.why}")
            print(f"-- duckdb dispatch:\n{duck_sql[case.name]}")
            print(f"-- databricks dispatch:\n{dbx_sql[case.name]}")

    duck = run_duckdb(duck_sql)
    if args.engine == "duckdb":
        for name, res in duck.items():
            print(f"{'ok  ' if res['ok'] else 'FAIL'}  {name}")
            if not res["ok"]:
                print(f"        {res['error']}")
        return 0 if all(r["ok"] for r in duck.values()) else 1

    spark = run_spark(dbx_sql)

    results = []
    for case in CASES:
        d, s = duck[case.name], spark[case.name]
        # Compare as sets of rows, not sequences. `order by 1` sorts NULLs last
        # in DuckDB and first in Spark, which is a difference in where the two
        # put an unknown value and not a difference in what the macro computed.
        # Ordering is not what any of these cases is testing; if it ever
        # becomes so, the case should order by something not null.
        identical = ordered(d.get("rows")) == ordered(s.get("rows"))
        # A macro with no databricks__ implementation is dispatched to default__
        # on both sides; saying so distinguishes "agrees" from "is the same SQL".
        dispatched = duck_sql[case.name] != dbx_sql[case.name]
        verdict = (
            "agree" if d["ok"] and s["ok"] and identical
            else "DIFFER" if d["ok"] and s["ok"]
            else "ERROR"
        )
        results.append(
            {
                "case": case.name,
                "macro": case.macro,
                "why": case.why,
                "dispatched": dispatched,
                "verdict": verdict,
                "duckdb": d,
                "spark": s,
            }
        )

    width = max(len(r["case"]) for r in results) + 2
    print(f"\n{'case'.ljust(width)}{'dispatched':<12}{'verdict':<8}rows")
    print("-" * (width + 32))
    for r in results:
        rows = len(r["duckdb"].get("rows", []) or [])
        mark = "yes" if r["dispatched"] else "default"
        print(f"{r['case'].ljust(width)}{mark:<12}{r['verdict']:<8}{rows}")
        if r["verdict"] != "agree":
            print(f"    duckdb: {json.dumps(r['duckdb'])[:400]}")
            print(f"    spark : {json.dumps(r['spark'])[:400]}")

    failed = [r for r in results if r["verdict"] != "agree"]
    print(f"\n{len(results) - len(failed)}/{len(results)} agree")

    if args.json:
        args.json.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"written: {args.json}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
