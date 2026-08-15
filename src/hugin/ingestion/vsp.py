"""VSP — checkshot depth/time pairs, in the two layouts the delivery uses.

A checkshot is the independent truth BR-09 is validated against: a directly
measured depth-to-time relationship, from a source that knows nothing about the
directional survey. That is the whole reason this small source matters.

**There are two layouts, and only one of them was handled at first.** Three of
the four files open with a single column line:

    Curve Name    TVDBTDD    TVD    TVDSS    Two Way Time
    TIME-CKS      0.00       25.00  0.00     0.0000

The fourth opens with a metadata block and carries different columns:

    Vertical time-depth pairs from VSP survey
    Wellname                : 15_9-F-15A
    Depth datum             : MSL
    ...
    Measured Depth  Vertical Depth  Two-way Time
    MDMSL(m)        TVDMSL(m)       TWT(ms)
      1067.3          1052.0          1096.2

The first reader assumed five whitespace-separated columns and dropped every
row of the second layout on that test — silently, because a line with three
fields simply failed the check. The file that was lost is the only one carrying
**measured depth**, which is precisely what a trajectory has to be validated
against: TVD alone cannot be compared to a survey without an MD to look it up
by.

So the layout is detected rather than assumed, and the reader records which one
it read. The header block is worth keeping too: it names the depth datum (MSL)
and the time datum, and comparing a checkshot to a survey referenced to a
different datum is the mistake this data makes available.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pyarrow as pa

from hugin.common.io import read_text
from hugin.ingestion.base import SourceReader
from hugin.ingestion.las import STATIC_LOAD_DATE

__all__ = ["VspCheckshotReader", "identity_from_name", "parse_checkshot"]

BUSINESS_COLUMNS = (
    "well_from_file_name",
    "well_from_header",
    "layout",
    "curve_name",
    "contractor",
    "depth_datum",
    "time_datum",
    "md_m",
    "tvd_m",
    "tvd_below_datum_m",
    "tvd_subsea_m",
    "two_way_time_ms",
    "row_seq",
)

#: ``checkshot_15_9_19A`` / ``checkshot_15_9_F_15A`` -> the identity part.
_NAME = re.compile(r"^checkshot[_\-]?(.+)$", re.I)

#: ``Wellname                : 15_9-F-15A``
_HEADER_FIELD = re.compile(r"^([A-Za-z][A-Za-z ()!.&/-]*?)\s*:\s*(.+?)\s*$")


def identity_from_name(path: Path) -> str | None:
    """The wellbore this file names, as written in the file name.

    Returned verbatim, underscores and all - BR-12's stage c is what turns
    ``15_9_19A`` into ``15/9-19 A``, and doing it here would put the same rule
    in two places.
    """
    match = _NAME.match(path.stem)
    return match.group(1) if match else None


def _number(text: str) -> str | None:
    try:
        float(text)
    except (TypeError, ValueError):
        return None
    return text


def parse_checkshot(text: str) -> tuple[str, dict[str, str], list[dict[str, str | None]]]:
    """Parse either layout. Returns ``(layout, header, rows)``.

    Layout is decided by what the file actually contains rather than by its
    name: a metadata block with ``Wellname :`` means the MD-bearing form, a
    leading ``Curve Name`` column line means the other.
    """
    lines = [line.rstrip() for line in text.splitlines()]
    header: dict[str, str] = {}
    data_start = 0
    layout = "columns"

    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        # A data line is all numbers; everything before the first one is header.
        fields = stripped.split()
        if fields and all(_number(f) is not None for f in fields):
            data_start = index
            break
        match = _HEADER_FIELD.match(stripped)
        if match:
            layout = "header_block"
            header[match.group(1).strip().lower()] = match.group(2).strip()

    rows: list[dict[str, str | None]] = []
    for sequence, line in enumerate(lines[data_start:], start=1):
        fields = line.split()
        if not fields or any(_number(f) is None for f in fields[1:]):
            continue

        if layout == "header_block" and len(fields) >= 3 and _number(fields[0]) is not None:
            # Measured Depth, Vertical Depth, Two-way Time
            rows.append({
                "md_m": fields[0], "tvd_m": fields[1], "two_way_time_ms": fields[2],
                "tvd_below_datum_m": None, "tvd_subsea_m": None, "curve_name": None,
                "row_seq": str(sequence),
            })
        elif len(fields) >= 5 and _number(fields[0]) is None:
            # Curve Name, TVDBTDD, TVD, TVDSS, Two Way Time. No measured depth,
            # which is why this layout cannot validate a trajectory on its own.
            rows.append({
                "md_m": None, "tvd_below_datum_m": fields[1], "tvd_m": fields[2],
                "tvd_subsea_m": fields[3], "two_way_time_ms": fields[4],
                "curve_name": fields[0], "row_seq": str(sequence),
            })
    return layout, header, rows


class VspCheckshotReader(SourceReader):
    """One row per checkshot depth/time pair, from either layout."""

    source_system = "VSP"
    table = "bronze.vsp_checkshot"
    business_columns = BUSINESS_COLUMNS
    identifier_column = "well_from_file_name"

    def source_files(self) -> list[Path]:
        root = self.settings.landing_dir / "vsp"
        if not root.exists():
            return []
        return sorted(
            p for p in root.rglob("*.txt")
            if p.is_file() and p.stem.lower().startswith("checkshot")
        )

    def read(self, replay_date: date) -> Iterator[pa.RecordBatch]:
        if replay_date != STATIC_LOAD_DATE:
            return
        batcher = self.batcher(replay_date)

        for path in self.source_files():
            identity = identity_from_name(path)
            text, _encoding = read_text(path)
            layout, header, rows = parse_checkshot(text)
            # The header names the well too. Where both are present they agree;
            # where they do not, the crosswalk sees both spellings.
            from_header = header.get("wellname")

            for row in rows:
                record = {
                    "well_from_file_name": identity,
                    "well_from_header": from_header,
                    "layout": layout,
                    "contractor": header.get("contractor"),
                    "depth_datum": header.get("depth datum"),
                    "time_datum": header.get("time datum"),
                    "_source_identifier": identity or from_header,
                    **row,
                }
                yield from batcher.add(record, self.relative(path))

        if batcher.pending:
            yield batcher.flush()
