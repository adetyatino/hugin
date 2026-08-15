"""Measure what SPEC.md section 13 sets targets for, and record the numbers.

Three measurements, all against the running compose stack:

    ingest-day    one replay date through every reader
    backfill      24 replay months, run twice to prove idempotency
    dbt           dbt build on both targets

Nothing here is a benchmark harness: it times the same code paths the DAGs use,
because a number produced by a special measurement path is a number about the
measurement path.

    python scripts/benchmark.py ingest-day
    python scripts/benchmark.py backfill
    python scripts/benchmark.py dbt
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys
import time
import uuid
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from hugin.common.config import get_settings  # noqa: E402
from hugin.ingestion.bronze import BronzeLoader  # noqa: E402
from hugin.ingestion.load_job import all_readers  # noqa: E402
from hugin.ingestion.prod import (  # noqa: E402
    ProductionDailyReader,
    ProductionMonthlyReader,
)

RESULTS = REPO_ROOT / "data" / "_inventory" / "benchmark-results.json"

#: 24 replay months from the start of field life, per SPEC.md section 6's
#: "backfill 24 months of replay succeeds and is idempotent".
BACKFILL_START = date(2008, 6, 1)
BACKFILL_END = date(2010, 5, 31)


def _record(name: str, payload: dict) -> None:
    existing = {}
    if RESULTS.exists():
        existing = json.loads(RESULTS.read_text(encoding="utf-8"))
    existing[name] = {"measured_at": _dt.datetime.now().isoformat(timespec="seconds"), **payload}
    RESULTS.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    print(f"\nrecorded '{name}' in {RESULTS.relative_to(REPO_ROOT)}")


def _table_state(loader: BronzeLoader, tables: list[str]) -> dict[str, dict]:
    """Row count and a hash of the row hashes, per table.

    The count alone would not prove idempotency: a load that deleted one row and
    inserted a different one keeps the count. Summing over _row_hash detects
    that, and is cheap enough to run inside a timed measurement.
    """
    state: dict[str, dict] = {}
    for table in tables:
        rows = loader.client.execute(
            f"SELECT count(*), count(distinct _row_hash), "
            f"       coalesce(sum(from_base(substr(_row_hash, 1, 8), 16)), 0) "
            f"FROM {loader.qualified(table)}"
        )[0]
        state[table] = {
            "rows": rows[0],
            "distinct_row_hashes": rows[1],
            "row_hash_checksum": str(rows[2]),
        }
    return state


def measure_ingest_day(replay_date: date) -> None:
    """One replay date through every reader — SPEC.md section 13's first target."""
    settings = get_settings()
    loader = BronzeLoader(settings=settings)
    loader.client.wait_until_ready(attempts=30, delay=2)

    batch_id = str(uuid.uuid4())
    started = time.time()
    per_reader = []
    total_rows = 0

    for reader in all_readers(batch_id, max_las_files=8):
        reader_started = time.time()
        result = loader.load(reader, replay_date)
        elapsed = time.time() - reader_started
        total_rows += result.rows
        per_reader.append({
            "table": result.table,
            "rows": result.rows,
            "seconds": round(elapsed, 2),
        })
        print(f"  {result.table:28} {result.rows:>8,} rows  {elapsed:6.1f}s")

    elapsed = time.time() - started
    print(f"\ningest of {replay_date}: {total_rows:,} rows in {elapsed:.1f}s")
    _record("ingest_one_replay_day", {
        "replay_date": replay_date.isoformat(),
        "seconds": round(elapsed, 1),
        "rows": total_rows,
        "target_seconds": 60,
        "met": elapsed < 60,
        "per_reader": per_reader,
    })


def measure_backfill() -> None:
    """24 replay months, twice, comparing the table state after each pass.

    SPEC.md section 6 asks for a backfill that is idempotent, and section 13
    sets 25 minutes as the target. Both passes are timed; the second is the one
    that proves re-running changes nothing.
    """
    settings = get_settings()
    loader = BronzeLoader(settings=settings)
    loader.client.wait_until_ready(attempts=30, delay=2)
    tables = ["bronze.prod_daily", "bronze.prod_monthly"]

    passes = []
    for attempt in (1, 2):
        batch_id = str(uuid.uuid4())
        started = time.time()
        rows = 0
        for reader_class in (ProductionDailyReader, ProductionMonthlyReader):
            reader = reader_class(settings=settings, batch_id=batch_id)
            result = loader.load_range(reader, BACKFILL_START, BACKFILL_END)
            rows += result.rows
            print(f"  pass {attempt}: {result.table:26} {result.rows:>8,} rows")
        elapsed = time.time() - started
        state = _table_state(loader, tables)
        passes.append({
            "pass": attempt,
            "batch_id": batch_id,
            "seconds": round(elapsed, 1),
            "rows_loaded": rows,
            "table_state": state,
        })
        print(f"  pass {attempt} finished in {elapsed:.1f}s")

    identical = passes[0]["table_state"] == passes[1]["table_state"]
    print(f"\nidempotent: {identical}")
    for table in tables:
        first = passes[0]["table_state"][table]
        second = passes[1]["table_state"][table]
        flag = "same" if first == second else "DIFFERENT"
        print(f"  {table:24} {first['rows']:>8,} rows -> {second['rows']:>8,} rows  [{flag}]")

    _record("backfill_24_replay_months", {
        "start": BACKFILL_START.isoformat(),
        "end": BACKFILL_END.isoformat(),
        "replay_months": 24,
        "first_pass_seconds": passes[0]["seconds"],
        "second_pass_seconds": passes[1]["seconds"],
        "target_seconds": 25 * 60,
        "met": passes[0]["seconds"] < 25 * 60,
        "idempotent": identical,
        "passes": passes,
    })


def measure_dbt() -> None:
    """dbt build on both targets, timed end to end."""
    transform = REPO_ROOT / "transform"
    results = {}
    for target, target_seconds in (("trino", 8 * 60), ("duckdb", 90)):
        started = time.time()
        completed = subprocess.run(
            ["dbt", "build", "--target", target],
            cwd=transform,
            capture_output=True,
            text=True,
            env={**__import__("os").environ, "DBT_PROFILES_DIR": "."},
        )
        elapsed = time.time() - started
        summary = [
            line for line in completed.stdout.splitlines() if "Done." in line
        ]
        print(f"  {target:8} {elapsed:7.1f}s  {summary[-1].strip() if summary else 'no summary'}")
        results[target] = {
            "seconds": round(elapsed, 1),
            "target_seconds": target_seconds,
            "met": elapsed < target_seconds,
            "summary": summary[-1].strip() if summary else "",
            "exit_code": completed.returncode,
        }
    _record("dbt_build", results)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/benchmark.py")
    parser.add_argument("what", choices=("ingest-day", "backfill", "dbt", "all"))
    parser.add_argument("--date", default="2014-04-07", help="replay date for ingest-day")
    args = parser.parse_args(argv)

    if args.what in ("ingest-day", "all"):
        measure_ingest_day(date.fromisoformat(args.date))
    if args.what in ("backfill", "all"):
        measure_backfill()
    if args.what in ("dbt", "all"):
        measure_dbt()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
