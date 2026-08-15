"""Run the bronze load for a set of replay dates.

    python -m hugin.ingestion.load_job --date 2014-04-07 --date 2016-08-04
    python -m hugin.ingestion.load_job --demo
    python -m hugin.ingestion.load_job --counts

Every reader is offered every date. A reader whose source has nothing on that
date yields nothing, which is the normal case and not an error — the replay
clock drives the schedule, and most sources are quiet on most days.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import uuid
from collections.abc import Iterator
from datetime import date

from hugin.common.config import get_settings
from hugin.ingestion.base import SourceReader
from hugin.ingestion.bronze import BronzeLoader
from hugin.ingestion.ddr import DDRActivityReader
from hugin.ingestion.eclipse import EclipseBalanceReader
from hugin.ingestion.geom import FaultRecordReader
from hugin.ingestion.las import STATIC_LOAD_DATE, LasCurveHeaderReader, LasSampleReader
from hugin.ingestion.prod import ProductionDailyReader, ProductionMonthlyReader
from hugin.ingestion.segy import SegyHeaderReader
from hugin.ingestion.trajectory import TrajectoryStationReader
from hugin.ingestion.vsp import VspCheckshotReader
from hugin.ingestion.witsml import (
    WitsmlLogDataReader,
    WitsmlLogHeaderReader,
    WitsmlMessageReader,
)

#: Dates chosen because each has data in at least one source. Between them they
#: exercise every reader that this delivery can feed.
DEMO_DATES = (
    STATIC_LOAD_DATE,          # logs, checkshots, SEG-Y headers, fault records
    date(2008, 6, 12),         # an Eclipse balance report inside field life
    date(2009, 5, 29),         # 469 trajectory stations
    date(2014, 4, 7),          # daily production
    date(2016, 8, 4),          # a daily drilling report
    date(2016, 8, 26),         # WITSML drilling messages
)


def all_readers(batch_id: str, max_las_files: int | None = None) -> Iterator[SourceReader]:
    """One instance of every reader, sharing a batch id.

    They share it because a load is one event: SPEC.md section 3 defines
    ``_batch_id`` as a UUID per DAG execution, not per reader.
    """
    settings = get_settings()
    common = {"settings": settings, "batch_id": batch_id}
    yield ProductionDailyReader(**common)
    yield ProductionMonthlyReader(**common)
    yield DDRActivityReader(**common)
    yield TrajectoryStationReader(**common)
    yield WitsmlMessageReader(**common)
    yield WitsmlLogHeaderReader(**common)
    yield WitsmlLogDataReader(**common)
    yield LasCurveHeaderReader(**common)
    yield LasSampleReader(max_files=max_las_files, **common)
    yield VspCheckshotReader(**common)
    yield SegyHeaderReader(**common)
    yield EclipseBalanceReader(**common)
    yield FaultRecordReader(**common)


def print_counts(loader: BronzeLoader) -> None:
    rows = loader.table_counts()
    width = max((len(name) for name, *_ in rows), default=20)
    print(f"\n{'table':<{width}}  {'rows':>12}  {'wellbore_uid':>12}  {'linked':>7}")
    print("-" * (width + 38))
    total = linked_total = 0
    for name, count, linked, percent in rows:
        print(f"{name:<{width}}  {count:>12,}  {linked:>12,}  {percent:>6.1f}%")
        total += count
        linked_total += linked
    print("-" * (width + 38))
    overall = (linked_total / total * 100) if total else 0.0
    print(f"{'TOTAL':<{width}}  {total:>12,}  {linked_total:>12,}  {overall:>6.1f}%")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hugin.ingestion.load_job")
    parser.add_argument("--date", action="append", default=[], help="replay date, repeatable")
    parser.add_argument("--demo", action="store_true", help="load the demonstration dates")
    parser.add_argument("--counts", action="store_true", help="print bronze counts and exit")
    parser.add_argument(
        "--max-las-files", type=int, default=None,
        help="bound the LAS sample reader; the load report states the bound",
    )
    args = parser.parse_args(argv)

    loader = BronzeLoader()
    if not loader.client.wait_until_ready(attempts=5, delay=2.0):
        raise SystemExit(
            "Trino is not accepting queries. Start the stack first:\n"
            "  docker compose --profile core up -d"
        )

    if args.counts:
        print_counts(loader)
        return 0

    dates = [date.fromisoformat(value) for value in args.date]
    if args.demo or not dates:
        dates = list(DEMO_DATES)

    batch_id = str(uuid.uuid4())
    started = _dt.datetime.now()
    print(f"batch {batch_id}")
    print(f"dates: {', '.join(d.isoformat() for d in dates)}")
    if args.max_las_files is not None:
        print(f"LAS sample reader bounded to the {args.max_las_files} smallest files")
    print()

    loaded = 0
    for reader in all_readers(batch_id, max_las_files=args.max_las_files):
        for replay_date in dates:
            result = loader.load(reader, replay_date)
            if not result.skipped:
                print(f"  {result}")
                loaded += result.rows

    elapsed = (_dt.datetime.now() - started).total_seconds()
    print(f"\nloaded {loaded:,} rows in {elapsed:.0f}s")
    print_counts(loader)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
