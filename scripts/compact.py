"""Iceberg compaction, measured before and after.

    python scripts/compact.py --table bronze.prod_daily
    python scripts/compact.py --all

Small files are what an incremental pipeline produces and what a query engine
hates: every one costs a request, a footer read and a split. SPEC.md section 13
sets targets for the file count and the average size after compaction, so the
point of this script is not to run OPTIMIZE — it is to record what changed.

Trino's Iceberg connector exposes ``ALTER TABLE ... EXECUTE optimize``, which
rewrites small data files into larger ones without touching the table's logical
contents. The row count before and after must match exactly, and this script
asserts that rather than trusting it: a compaction that lost a row would
otherwise look like a success with better statistics.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from hugin.common.config import get_settings  # noqa: E402
from hugin.common.trino import TrinoClient  # noqa: E402

RESULTS = REPO_ROOT / "data" / "_inventory" / "compaction-results.json"


def file_stats(client: TrinoClient, catalog: str, schema: str, table: str) -> dict:
    """File count and sizes from the Iceberg ``$files`` metadata table.

    Read from metadata rather than by listing object storage: the storage prefix
    also holds files from superseded snapshots, and counting those would report
    a compaction as having made things worse.
    """
    row = client.execute(f"""
        SELECT count(*), coalesce(sum(file_size_in_bytes), 0),
               coalesce(avg(file_size_in_bytes), 0), coalesce(sum(record_count), 0)
        FROM {catalog}.{schema}."{table}$files"
    """)[0]
    return {
        "files": int(row[0]),
        "total_bytes": int(row[1]),
        "avg_bytes": float(row[2]),
        "records": int(row[3]),
    }


def compact(client: TrinoClient, catalog: str, schema: str, table: str,
            file_size_threshold: str = "128MB") -> dict:
    """Compact one table, measuring both sides."""
    qualified = f"{catalog}.{schema}.{table}"
    rows_before = client.scalar(f"SELECT count(*) FROM {qualified}")
    before = file_stats(client, catalog, schema, table)

    started = time.perf_counter()
    client.execute(
        f"ALTER TABLE {qualified} EXECUTE optimize(file_size_threshold => '{file_size_threshold}')"
    )
    elapsed = time.perf_counter() - started

    after = file_stats(client, catalog, schema, table)
    rows_after = client.scalar(f"SELECT count(*) FROM {qualified}")

    if rows_before != rows_after:
        raise SystemExit(
            f"{qualified}: compaction changed the row count "
            f"({rows_before} -> {rows_after}). This is data loss, not optimisation."
        )

    reduction = (
        (before["files"] - after["files"]) / before["files"] * 100 if before["files"] else 0.0
    )
    return {
        "table": qualified,
        "seconds": round(elapsed, 2),
        "rows": rows_before,
        "files_before": before["files"],
        "files_after": after["files"],
        "file_reduction_pct": round(reduction, 1),
        "avg_bytes_before": round(before["avg_bytes"]),
        "avg_bytes_after": round(after["avg_bytes"]),
        "total_bytes_before": before["total_bytes"],
        "total_bytes_after": after["total_bytes"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/compact.py")
    parser.add_argument("--table", action="append", default=[],
                        help="schema.table, repeatable")
    parser.add_argument("--all", action="store_true", help="every bronze table")
    parser.add_argument("--threshold", default="128MB")
    args = parser.parse_args(argv)

    settings = get_settings()
    client = TrinoClient(host=settings.trino_host, port=settings.trino_port,
                         catalog=settings.trino_catalog, schema="bronze")
    if not client.wait_until_ready(attempts=15, delay=2):
        raise SystemExit("Trino is not accepting queries; start the stack with 'make up'")

    targets: list[tuple[str, str]] = []
    if args.all:
        for schema in ("bronze", "silver", "gold"):
            for row in client.execute(
                f"SELECT table_name FROM {settings.trino_catalog}.information_schema.tables "
                f"WHERE table_schema = '{schema}' ORDER BY table_name"
            ):
                targets.append((schema, row[0]))
    for entry in args.table:
        schema, _, table = entry.partition(".")
        targets.append((schema or "bronze", table or entry))

    if not targets:
        raise SystemExit("nothing to compact: pass --table or --all")

    results = []
    header = f"{'table':40} {'rows':>10} {'files':>14} {'avg size':>20} {'time':>7}"
    print(header)
    print("-" * len(header))
    for schema, table in targets:
        try:
            result = compact(client, settings.trino_catalog, schema, table, args.threshold)
        except Exception as exc:  # noqa: BLE001 - report and continue
            print(f"{schema}.{table:33} SKIPPED: {str(exc)[:60]}")
            continue
        results.append(result)
        print(
            f"{schema + '.' + table:40} {result['rows']:>10,} "
            f"{result['files_before']:>5} -> {result['files_after']:<5} "
            f"{result['avg_bytes_before']:>9,} -> {result['avg_bytes_after']:<9,} "
            f"{result['seconds']:>6.1f}s"
        )

    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(
        json.dumps(
            {"measured_at": _dt.datetime.now().isoformat(timespec="seconds"),
             "threshold": args.threshold, "tables": results},
            indent=2,
        ),
        encoding="utf-8",
    )
    total_before = sum(r["files_before"] for r in results)
    total_after = sum(r["files_after"] for r in results)
    if total_before:
        print(f"\ntotal files {total_before} -> {total_after} "
              f"({(total_before - total_after) / total_before * 100:.1f}% fewer)")
    print(f"wrote {RESULTS.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
