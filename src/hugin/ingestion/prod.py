"""PROD — daily and monthly production and injection, per wellbore.

What the delivery actually contains, measured rather than assumed
(docs/data-dictionary.md, docs/data-inventory.md finding 7):

*   **One workbook**, ``Production_data/Volve production data.xlsx``. No CSV
    form of it exists anywhere in the delivery, so ``.xlsx`` is not a
    convenience here, it is the only form.
*   **Two sheets with different date encodings.** Daily rows carry ``DATEPRD``
    as an Excel serial (39326 = 2007-09-01) under number format ``dd-mmm-yy``.
    Monthly rows carry integer ``Year`` and ``Month`` columns instead. That is
    the dual date format this source really has — not two written date shapes,
    but two different ways of encoding a date at all.
*   **No decimal commas.** Every numeric cell in both sheets uses ``.``; a scan
    of all 15,635 daily rows found no cell containing a comma. Decimal-comma
    handling is therefore *not* implemented here: it would be untested code
    defending against something this source does not do.
*   **One trailer row**, on the monthly sheet only — a row with no populated
    cell. Dropped as a blank, not as a record.
*   **UTF-8 throughout**, including ``MÆRSK INSPIRER`` in the facility column.
    Read as UTF-8 by the XML parser; nothing to detect.

Two readers, because they are two grains and SPEC.md section 4.2 keeps them
apart deliberately: the difference between them is BR-02's reconciliation, and
a union would destroy the thing being reconciled.

Date range note. Production runs 2007-09-01 to 2016-12-01, which is *wider*
than the field life the replay clock covers (2008-06 .. 2016-09). Rows outside
that window can never be selected by a replay-driven run. They are not dropped
and not silently included: :func:`out_of_replay_window` counts them so the load
report can state the number.
"""

from __future__ import annotations

import datetime as _dt
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pyarrow as pa

from hugin.common.io import sheet_names, xlsx_table
from hugin.ingestion.base import SourceReader

__all__ = [
    "EXCEL_EPOCH",
    "ProductionDailyReader",
    "ProductionMonthlyReader",
    "excel_serial_to_date",
    "out_of_replay_window",
]

WORKBOOK = Path("prod/Production_data/Volve production data.xlsx")

DAILY_SHEET = "Daily Production Data"
MONTHLY_SHEET = "Monthly Production Data"

#: Excel's day 1 is 1900-01-01, and it treats 1900 as a leap year, which it was
#: not. Counting from 1899-12-30 reproduces that off-by-one for every date after
#: 1900-03-01 — which is every date in this dataset — without special-casing.
EXCEL_EPOCH = _dt.date(1899, 12, 30)

DAILY_COLUMNS = (
    "dateprd",
    "well_bore_code",
    "npd_well_bore_code",
    "npd_well_bore_name",
    "npd_field_code",
    "npd_field_name",
    "npd_facility_code",
    "npd_facility_name",
    "on_stream_hrs",
    "avg_downhole_pressure",
    "avg_downhole_temperature",
    "avg_dp_tubing",
    "avg_annulus_press",
    "avg_choke_size_p",
    "avg_choke_uom",
    "avg_whp_p",
    "avg_wht_p",
    "dp_choke_size",
    "bore_oil_vol",
    "bore_gas_vol",
    "bore_wat_vol",
    "bore_wi_vol",
    "flow_kind",
    "well_type",
)

MONTHLY_COLUMNS = (
    "wellbore_name",
    "npdcode",
    "year",
    "month",
    "on_stream",
    "oil",
    "gas",
    "water",
    "gi",
    "wi",
)


def excel_serial_to_date(value: str) -> date | None:
    """Excel date serial -> date. None when the cell is not a serial.

    Bronze stores the serial as written; this exists so a run can decide which
    rows belong to a replay date, which is selection, not transformation.
    """
    text = (value or "").strip()
    if not text:
        return None
    try:
        serial = float(text)
    except ValueError:
        return None
    if serial <= 0:
        return None
    return EXCEL_EPOCH + _dt.timedelta(days=int(serial))


def _lower_keys(row: dict[str, str]) -> dict[str, str]:
    """Column names as written, lowercased, with spaces as underscores.

    Trino and Iceberg fold identifiers to lower case anyway, so keeping
    ``DATEPRD`` would only mean the table and the file disagree about spelling.
    The two sheets also disagree with each other — daily writes
    ``WELL_BORE_CODE``, monthly writes ``Wellbore name`` — and a column called
    ``wellbore name`` would need quoting in every query that touched it. The
    words are unchanged; only case and the space are.
    """
    return {
        "_".join(key.strip().lower().split()): value for key, value in row.items()
    }


class _WorkbookReader(SourceReader):
    """Shared plumbing: locate the workbook and its sheets once."""

    source_system = "PROD"
    sheet: str = ""

    def workbook_path(self) -> Path:
        return self.settings.landing_dir / WORKBOOK

    def sheet_part(self) -> str:
        parts = sheet_names(self.workbook_path())
        if self.sheet not in parts:
            raise FileNotFoundError(
                f"sheet {self.sheet!r} not in {self.workbook_path().name}; "
                f"found {sorted(parts)}"
            )
        return parts[self.sheet]

    def source_files(self) -> list[Path]:
        path = self.workbook_path()
        return [path] if path.exists() else []


class ProductionDailyReader(_WorkbookReader):
    """Daily production and injection, one row per wellbore per day."""

    table = "bronze.prod_daily"
    sheet = DAILY_SHEET
    business_columns = DAILY_COLUMNS
    identifier_column = "well_bore_code"

    def read(self, replay_date: date) -> Iterator[pa.RecordBatch]:
        yield from self._read_between(replay_date, replay_date, replay_date)

    def read_range(self, start: date, end: date) -> Iterator[pa.RecordBatch]:
        """One pass over the workbook for a whole date range.

        The default implementation would re-parse 14 MB of sheet XML once per
        day. Over the field's 3,044 days that is the difference between a
        backfill that finishes and one that does not.

        Each row keeps its *own* date as ``_replay_date``, so a range load and
        a sequence of daily loads produce identical rows.
        """
        yield from self._read_between(start, end, None)

    def _read_between(
        self, start: date, end: date, fixed_replay_date: date | None
    ) -> Iterator[pa.RecordBatch]:
        path = self.workbook_path()
        if not path.exists():
            return
        source_file = self.relative(path)
        # One batcher per date, because _replay_date is a column: a batch
        # spanning dates would have to carry more than one value for it.
        batchers: dict[date, object] = {}

        for raw in xlsx_table(path, self.sheet_part(), header_row=1):
            row = _lower_keys(raw)
            produced = excel_serial_to_date(row.get("dateprd", ""))
            if produced is None or produced < start or produced > end:
                continue
            replay_date = fixed_replay_date or produced
            if replay_date not in batchers:
                batchers[replay_date] = self.batcher(replay_date)
            yield from batchers[replay_date].add(row, source_file)

        for batcher in batchers.values():
            if batcher.pending:
                yield batcher.flush()


class ProductionMonthlyReader(_WorkbookReader):
    """Monthly reported volumes, one row per wellbore per month.

    The sheet's second row holds units (``hrs``, ``Sm3``) rather than data, so it
    is skipped as a second header. Those units are a fact about the source and
    are recorded in docs/data-dictionary.md; they do not belong in the rows.

    A month's rows are emitted on the **first day of that month**, so a full
    replay emits each monthly row exactly once. Any other choice either repeats
    the row for every day of the month or, if tied to the last day, silently
    drops months the replay window ends inside.
    """

    table = "bronze.prod_monthly"
    sheet = MONTHLY_SHEET
    business_columns = MONTHLY_COLUMNS
    identifier_column = "wellbore_name"

    def read(self, replay_date: date) -> Iterator[pa.RecordBatch]:
        if replay_date.day != 1:
            return
        yield from self.read_range(replay_date, replay_date)

    def read_range(self, start: date, end: date) -> Iterator[pa.RecordBatch]:
        """One pass over the monthly sheet for a whole date range.

        A month's rows land on the first of that month, so a range load emits
        each monthly row exactly once, exactly as the daily path would.
        """
        path = self.workbook_path()
        if not path.exists():
            return
        source_file = self.relative(path)
        batchers: dict[date, object] = {}

        for raw in xlsx_table(path, self.sheet_part(), header_row=1, skip_rows=1):
            row = _lower_keys(raw)
            year, month = row.get("year", ""), row.get("month", "")
            if not year or not month:
                continue
            try:
                replay_date = date(int(float(year)), int(float(month)), 1)
            except ValueError:
                continue
            if replay_date < start or replay_date > end:
                continue
            if replay_date not in batchers:
                batchers[replay_date] = self.batcher(replay_date)
            yield from batchers[replay_date].add(row, source_file)

        for batcher in batchers.values():
            if batcher.pending:
                yield batcher.flush()


def out_of_replay_window(landing_dir: Path, first: date, last: date) -> dict[str, int]:
    """Count daily rows whose own date falls outside the replay window.

    Reported rather than resolved. The window comes from SPEC.md section 2's
    field life; production data exists on both sides of it, and a replay-driven
    DAG cannot reach those rows. Which of the two is wrong is a decision, not a
    parsing problem.
    """
    path = landing_dir / WORKBOOK
    if not path.exists():
        return {"before": 0, "after": 0, "inside": 0, "unparseable": 0}

    counts = {"before": 0, "after": 0, "inside": 0, "unparseable": 0}
    for raw in xlsx_table(path, sheet_names(path)[DAILY_SHEET], header_row=1):
        produced = excel_serial_to_date(_lower_keys(raw).get("dateprd", ""))
        if produced is None:
            counts["unparseable"] += 1
        elif produced < first:
            counts["before"] += 1
        elif produced > last:
            counts["after"] += 1
        else:
            counts["inside"] += 1
    return counts
