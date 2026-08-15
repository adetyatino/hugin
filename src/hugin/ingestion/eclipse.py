"""SIM — Eclipse print file, the paged fixed-width report format.

``VOLVE_2016.PRT`` is 238 MB of paginated report. Each balance page looks like:

      BALANCE  AT      0.00  DAYS *2010a Volve simulation model     * ECLIPSE ...
      REPORT   0    31 DEC 2007   *  RUN                            * RUN AT ...
                    :--------------- OIL    SM3  ---------------:-- WAT  SM3 -:...
                    :     LIQUID         VAPOUR         TOTAL    :    TOTAL    :...
      :CURRENTLY IN PLACE       :     21967455.        21967455. :   81270001. :...

The page repeats every report step with the same column positions and the same
row labels. That regularity is the whole contract: the columns are fixed-width
and the row is identified by its label, not by its position.

Two things make this harder than a CSV, and both are handled by streaming:

*   The file never fits comfortably in memory, so it is read line by line and a
    page is emitted as soon as its closing rule is seen.
*   Numbers are written with a trailing period (``21967455.``) and are right-
    aligned into columns whose widths are set by the header rule, so splitting
    on whitespace works only because every field here is non-empty. The column
    *positions* are taken from the rule line, which is what makes the parse
    robust when a field is blank.

Values are stored as written, trailing period included. SPEC.md section 2 scopes
this source to summary tables only: no restart files, no binary output.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pyarrow as pa

from hugin.common.io import read_text
from hugin.ingestion.base import SourceReader

__all__ = ["EclipseBalanceReader", "iter_balance_pages"]

BUSINESS_COLUMNS = (
    "report_number",
    "report_date",
    "days_from_start",
    "model_name",
    "simulator_version",
    "run_at",
    "row_label",
    "oil_liquid",
    "oil_vapour",
    "oil_total",
    "water_total",
    "gas_free",
    "gas_dissolved",
    "gas_total",
    "pav_bara",
    "porv_rm3",
)

_BALANCE = re.compile(r"BALANCE\s+AT\s+([\d.]+)\s+DAYS")
_REPORT = re.compile(r"REPORT\s+(\d+)\s+(\d{1,2}\s+\w{3}\s+\d{4})")
_VERSION = re.compile(r"ECLIPSE\s+VERSION\s+(\S+)")
_RUN_AT = re.compile(r"RUN AT\s+(.+?)\s*$")
_PAV = re.compile(r"PAV\s*=\s*([\d.]+)")
_PORV = re.compile(r"PORV\s*=\s*([\d.]+)")
#: A data row: ``:CURRENTLY IN PLACE       :   21967455.   ...``
_DATA_ROW = re.compile(r"^\s*:([A-Z][A-Z .,]+?)\s*:(.*)$")

#: The sub-header naming the seven value columns. Its label positions are what
#: fix the column boundaries for every data row on the page.
_SUBHEADER_LABELS = ("LIQUID", "VAPOUR", "TOTAL", "TOTAL", "FREE", "DISSOLVED", "TOTAL")


def _column_spans(subheader: str) -> list[tuple[int, int]] | None:
    """Character spans of the seven value columns, from the sub-header line.

    Splitting a data row on whitespace looks like it works and does not: oil
    VAPOUR is blank on every page of this file, so a whitespace split yields
    two numbers for a three-column group and silently files the oil *total*
    under *vapour*. The columns are fixed-width, so the boundaries are taken
    from where the labels sit and each row is sliced at those positions.

    Boundaries fall midway between one label's end and the next one's start, so
    a right-aligned number that overruns its label still lands in its own
    column.
    """
    positions: list[tuple[int, int]] = []
    cursor = 0
    for label in _SUBHEADER_LABELS:
        found = subheader.find(label, cursor)
        if found < 0:
            return None
        positions.append((found, found + len(label)))
        cursor = found + len(label)

    # The row label occupies the first column of a data row and is closed by a
    # colon. Starting the first value column at 0 would swallow the label.
    label_edge = subheader.rfind(":", 0, positions[0][0]) + 1

    spans: list[tuple[int, int]] = []
    for index, (start, end) in enumerate(positions):
        left = label_edge if index == 0 else (positions[index - 1][1] + start) // 2
        right = (
            len(subheader) + 200  # last column runs to the end of the row
            if index == len(positions) - 1
            else (end + positions[index + 1][0]) // 2
        )
        spans.append((left, right))
    return spans

_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def _parse_report_date(text: str) -> date | None:
    """``31 DEC 2007`` -> a date. Eclipse writes month names, not numbers."""
    parts = text.split()
    if len(parts) != 3:
        return None
    try:
        return date(int(parts[2]), _MONTHS[parts[1].upper()], int(parts[0]))
    except (KeyError, ValueError):
        return None


def iter_balance_pages(path: Path) -> Iterator[dict]:
    """Stream the print file, yielding one dict per balance page.

    Pages are recognised by their ``BALANCE AT`` banner and closed by the next
    one, so a truncated final page still yields what it had.
    """
    text, _encoding = read_text(path)
    page: dict | None = None

    for line in text.splitlines():
        banner = _BALANCE.search(line)
        if banner:
            if page is not None:
                yield page
            page = {
                "days_from_start": banner.group(1),
                "spans": None,
                "report_number": None,
                "report_date": None,
                "model_name": None,
                "simulator_version": None,
                "run_at": None,
                "pav_bara": None,
                "porv_rm3": None,
                "rows": [],
            }
            # The model name sits between the asterisks on the banner line.
            fragments = line.split("*")
            if len(fragments) > 1:
                page["model_name"] = fragments[1].strip() or None
            version = _VERSION.search(line)
            if version:
                page["simulator_version"] = version.group(1)
            continue

        if page is None:
            continue

        report = _REPORT.search(line)
        if report:
            page["report_number"] = report.group(1)
            parsed = _parse_report_date(report.group(2))
            page["report_date"] = parsed.isoformat() if parsed else report.group(2)
            run_at = _RUN_AT.search(line)
            if run_at:
                page["run_at"] = run_at.group(1).strip()
            continue

        pav = _PAV.search(line)
        if pav:
            page["pav_bara"] = pav.group(1)
        porv = _PORV.search(line)
        if porv:
            page["porv_rm3"] = porv.group(1)

        if page["spans"] is None and "LIQUID" in line and "DISSOLVED" in line:
            page["spans"] = _column_spans(line)
            continue

        row = _DATA_ROW.match(line)
        if row:
            label = row.group(1).strip()
            if label.startswith("-") or not label:
                continue
            if page["spans"]:
                values = [line[start:end].strip().strip(":").strip() for start, end in page["spans"]]
            else:
                # No sub-header seen yet: keep the raw groups rather than
                # guessing which column each number belongs to.
                values = [part.strip() for part in row.group(2).split(":") if part.strip()]
            page["rows"].append((label, values))

    if page is not None:
        yield page


class EclipseBalanceReader(SourceReader):
    """One row per labelled line of each balance page.

    Grain: report date x row label. ``CURRENTLY IN PLACE`` and
    ``ORIGINALLY IN PLACE`` are the field totals BR-11 compares against
    production; the material-balance error rows are kept because a simulation
    whose error is drifting is a fact about the model, not noise.
    """

    source_system = "SIM"
    table = "bronze.sim_summary"
    business_columns = BUSINESS_COLUMNS
    identifier_column = None

    def source_files(self) -> list[Path]:
        root = self.settings.landing_dir / "sim"
        if not root.exists():
            return []
        return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.upper() == ".PRT")

    def read(self, replay_date: date) -> Iterator[pa.RecordBatch]:
        batcher = self.batcher(replay_date)

        for path in self.source_files():
            relative = self.relative(path)
            for page in iter_balance_pages(path):
                if page["report_date"] != replay_date.isoformat():
                    continue
                for label, values in page["rows"]:
                    record = {
                        "report_number": page["report_number"],
                        "report_date": page["report_date"],
                        "days_from_start": page["days_from_start"],
                        "model_name": page["model_name"],
                        "simulator_version": page["simulator_version"],
                        "run_at": page["run_at"],
                        "pav_bara": page["pav_bara"],
                        "porv_rm3": page["porv_rm3"],
                        "row_label": label,
                    }
                    # Seven numeric columns in the order the rule line sets:
                    # oil liquid/vapour/total, water total, gas free/dissolved/
                    # total. A page that writes fewer leaves the rest NULL
                    # rather than shifting values into the wrong column.
                    for name, value in zip(
                        (
                            "oil_liquid", "oil_vapour", "oil_total", "water_total",
                            "gas_free", "gas_dissolved", "gas_total",
                        ),
                        values,
                        strict=False,
                    ):
                        record[name] = value or None
                    yield from batcher.add(record, relative)

        if batcher.pending:
            yield batcher.flush()
