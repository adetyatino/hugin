"""Validate mapped OSDU payloads against JSON Schema.

Run against the warehouse:

    python -m hugin.osdu.validate_osdu                    # all three kinds
    python -m hugin.osdu.validate_osdu --kind wellbore
    python -m hugin.osdu.validate_osdu --write data/osdu  # also emit the records

or against records already on disk:

    python -m hugin.osdu.validate_osdu --records data/osdu

The schemas are **reduced local copies** of the published OSDU well-known
schemas - `src/hugin/osdu/schemas/README.md` says exactly what was kept and
what was dropped. A pass here means the envelope, the kind, the id form and
every mapped property are right. It does not mean an OSDU instance would take
the record; ADR 008 says why that line is where it is, and
`mapping.UNFILLED_OSDU_PROPERTIES` lists what would still be missing.

Validation is done by `jsonschema` rather than by something written here. That
is the whole point of the exercise: a validator I wrote, checking a mapping I
wrote, against a schema I reduced, would be marking my own homework twice over.
An independent implementation of the spec is the only part of this chain that
is not mine.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hugin.osdu import mapping

SCHEMA_DIR = Path(__file__).parent / "schemas"

#: kind -> (schema file, the gold table it comes from)
KINDS: dict[str, tuple[str, str, str]] = {
    "wellbore": (
        mapping.WELLBORE_KIND,
        "master-data--Wellbore.1.0.0.json",
        "gold.dim_wellbore",
    ),
    "welllog": (
        mapping.WELL_LOG_KIND,
        "work-product-component--WellLog.1.0.0.json",
        "gold.fct_log_sample",
    ),
    "trajectory": (
        mapping.TRAJECTORY_KIND,
        "work-product-component--WellboreTrajectory.1.0.0.json",
        "gold.fct_trajectory",
    ),
}


def load_schema(kind: str) -> dict[str, Any]:
    _, filename, _ = KINDS[kind]
    return json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))


@dataclass
class Result:
    kind: str
    source: str
    records: int = 0
    failures: list[tuple[int, str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures

    def line(self) -> str:
        status = "ok  " if self.ok else "FAIL"
        return (
            f"{status}  {self.kind:<12} {self.records:>5} records from {self.source}"
            + ("" if self.ok else f"  - {len(self.failures)} invalid")
        )


def validate_records(kind: str, records: Iterable[Mapping[str, Any]], source: str) -> Result:
    """Validate every record, collecting failures rather than stopping at one.

    Stopping at the first failure would report one broken record in a batch of
    thousands and say nothing about whether the rest are fine, which is the
    question being asked.
    """
    import jsonschema

    schema = load_schema(kind)
    validator = jsonschema.Draft7Validator(schema)
    result = Result(kind=kind, source=source)
    for index, record in enumerate(records):
        result.records += 1
        for error in sorted(validator.iter_errors(record), key=lambda e: list(e.absolute_path)):
            path = "/".join(str(part) for part in error.absolute_path) or "<root>"
            result.failures.append((index, path, error.message))
    return result


# --------------------------------------------------------------------------
# Sources of records
# --------------------------------------------------------------------------


def from_warehouse(kind: str, limit: int | None = None) -> list[dict[str, Any]]:
    """Read gold from Trino and map it. Needs the compose stack up."""
    from hugin.common.trino import TrinoClient

    client = TrinoClient(schema="gold")
    context = mapping.OsduContext.from_env()

    if kind == "wellbore":
        rows = _rows(
            client,
            """
            select wellbore_uid, well_code, sidetrack_code, version_number,
                   well_role, operator_label, valid_from, valid_to, is_current,
                   source_system_count, identity_variant_count
            from gold.dim_wellbore
            """,
            limit,
        )
        identities = _rows(
            client,
            """
            select wellbore_uid, source_identifier, source_system
            from silver.silver_wellbore_identity
            where wellbore_uid is not null
            """,
            None,
        )
        return mapping.map_wellbores(rows, context, identities=identities)

    if kind == "welllog":
        rows = _rows(
            client,
            """
            select wellbore_uid, source_file, curve_mnemonic, curve_key,
                   index_mnemonic, depth_m, depth_uom, was_sentinel
            from gold.fct_log_sample
            """,
            limit,
        )
        units = {
            row["curve_mnemonic"]: row["curve_unit"]
            for row in _rows(
                client,
                "select curve_mnemonic, curve_unit from gold.dim_curve "
                "where curve_unit is not null",
                None,
            )
        }
        # skip_unresolved: an export is exactly the place where BR-12's
        # unresolved identities should be left out rather than attached to a
        # guess. They stay counted in mart_identity_coverage.
        return mapping.map_well_logs(rows, context, curve_units=units, skip_unresolved=True)

    rows = _rows(
        client,
        """
        select wellbore_uid, trajectory_uid, station_seq, station_date, md_m,
               tvd_m, inclination_deg, azimuth_deg, dogleg_severity_deg_per_m,
               azi_ref, source_crs
        from gold.fct_trajectory
        """,
        limit,
    )
    return mapping.map_trajectories(rows, context, skip_unresolved=True)


def _rows(client, sql: str, limit: int | None) -> list[dict[str, Any]]:
    if limit:
        sql = f"{sql.rstrip().rstrip(';')} limit {int(limit)}"
    return list(client.query_dicts(sql))


def from_disk(directory: Path, kind: str) -> list[dict[str, Any]]:
    """Read records previously written by --write."""
    path = directory / f"{kind}.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else [payload]


# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--kind",
        choices=[*KINDS, "all"],
        default="all",
        help="which mapping to validate",
    )
    parser.add_argument(
        "--records",
        type=Path,
        help="validate records already on disk instead of reading the warehouse",
    )
    parser.add_argument("--write", type=Path, help="write the mapped records to this directory")
    parser.add_argument("--limit", type=int, help="cap the rows read from gold")
    parser.add_argument(
        "--show", type=int, default=0, help="print the first N records for eyeballing"
    )
    args = parser.parse_args(argv)

    kinds = list(KINDS) if args.kind == "all" else [args.kind]
    results: list[Result] = []

    for kind in kinds:
        if args.records:
            records = from_disk(args.records, kind)
            source = str(args.records)
        else:
            _, _, table = KINDS[kind]
            records = from_warehouse(kind, args.limit)
            source = table

        if args.write:
            args.write.mkdir(parents=True, exist_ok=True)
            (args.write / f"{kind}.json").write_text(
                json.dumps(records, indent=2, default=str), encoding="utf-8"
            )

        if args.show:
            for record in records[: args.show]:
                print(json.dumps(record, indent=2, default=str))

        results.append(validate_records(kind, records, source))

    print()
    for result in results:
        print(result.line())
        for index, path, message in result.failures[:10]:
            print(f"        record {index} at {path}: {message}")
        if len(result.failures) > 10:
            print(f"        ... and {len(result.failures) - 10} more")

    total = sum(r.records for r in results)
    bad = sum(len(r.failures) for r in results)
    print(f"\n{total} records, {bad} schema violations")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
