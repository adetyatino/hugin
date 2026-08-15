"""GEOM — geophysical interpretation. The source the brief describes is not here.

The brief asks for a fixed-width parser whose character positions come from an
Equinor readme in ``docs/source-readme/``, producing four streams: fault
polygons, horizons, well picks and perforation intervals.

Two facts stop that, and both were established before this module was written:

1.  **There is no ``Geophysical_Interpretations`` delivery.** Twenty-four
    archives were inventoried and none produces a single file under the GEOM
    code (docs/data-inventory.md, section 6 and finding 5).
2.  **There is no readme documenting column positions.** ``docs/source-readme/``
    holds nine files — five licences, an Eclipse model readme, a VSP readme, an
    EDT/EDM export readme, and a production-log note. None describes a
    fixed-width layout.

So the character positions the brief says to read cannot be read, and inventing
them would be exactly the guess CLAUDE.md forbids. This module therefore does
two things instead of one:

*   :class:`FixedWidthSpec` and :func:`parse_fixed_width` implement the parser
    the brief describes, driven by a **declared** column specification. Given a
    spec — from a readme, a header, or a manual transcription — it parses. It
    has no built-in positions for Volve, because none are documented.
*   :class:`FaultRecordReader` reads what the delivery *does* hold of the GEOM
    subject matter. Fault definitions exist only as ``FAULT_*.GRDECL`` files
    inside the Eclipse model, and they are worth being precise about: they are
    ``ADDZCORN`` grid-corner operations over (i, j, k) index ranges, **not**
    polygon geometry. There are no coordinates in them. A fault surface can be
    derived from the simulation grid they modify, which is geological modelling
    and out of scope for ingestion.

Well picks and perforations are likewise embedded rather than delivered: picks
sit in per-well petrophysical spreadsheets and perforations in
``WL_RAW_PROD_CCL-PERF*`` log runs. Both are LOG-code files and belong to
:mod:`hugin.ingestion.las`, not here. BR-13 will need them; it will find them
through the LOG reader, and this docstring is where that is written down.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pyarrow as pa

from hugin.common.io import read_text
from hugin.ingestion.base import SourceReader
from hugin.ingestion.las import STATIC_LOAD_DATE

__all__ = [
    "FaultRecordReader",
    "FixedWidthSpec",
    "parse_fixed_width",
]


@dataclass(frozen=True)
class FixedWidthSpec:
    """A declared fixed-width layout: ``(column name, start, end)``, 0-based.

    Deliberately has no defaults. A fixed-width parser with guessed positions
    produces plausible values in the wrong columns, which is the failure mode
    that does not announce itself.
    """

    fields: Sequence[tuple[str, int, int]]
    source: str = "declared by the caller"

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(name for name, _start, _end in self.fields)

    def parse(self, line: str) -> dict[str, str]:
        return {
            name: line[start:end].strip() for name, start, end in self.fields
        }


def parse_fixed_width(
    path: Path,
    spec: FixedWidthSpec,
    *,
    comment_prefixes: tuple[str, ...] = ("--", "#"),
) -> Iterator[dict[str, str]]:
    """Parse a fixed-width file against a declared specification."""
    text, _encoding = read_text(path)
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith(comment_prefixes):
            continue
        yield spec.parse(line)


#: ``   10.0    0 62  46 0  1 63    0 62  46 0  /`` — an ADDZCORN record: a
#: shift, then index ranges. Whitespace-separated, not fixed-width.
_ADDZCORN = re.compile(r"^\s*([-\d.]+)((?:\s+\d+)+)\s*/")

BUSINESS_COLUMNS = (
    "fault_file",
    "keyword",
    "record_seq",
    "z_shift",
    "index_values",
    "comment",
)


class FaultRecordReader(SourceReader):
    """Fault definitions as the Eclipse model actually holds them.

    One row per ``ADDZCORN`` record. ``index_values`` keeps the index range as
    written rather than splitting it into named i/j/k columns: the meaning of
    the positions depends on the keyword's signature, and asserting one here
    would be the guess this module exists to avoid.
    """

    source_system = "GEOM"
    table = "bronze.geom_fault_record"
    business_columns = BUSINESS_COLUMNS
    identifier_column = None

    def source_files(self) -> list[Path]:
        root = self.settings.landing_dir / "sim"
        if not root.exists():
            return []
        return sorted(p for p in root.rglob("FAULT_*") if p.is_file())

    def read(self, replay_date: date) -> Iterator[pa.RecordBatch]:
        if replay_date != STATIC_LOAD_DATE:
            return
        batcher = self.batcher(replay_date)

        for path in self.source_files():
            text, _encoding = read_text(path)
            keyword: str | None = None
            comment: str | None = None
            sequence = 0
            for line in text.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.startswith("--"):
                    comment = stripped.lstrip("- ").strip() or None
                    continue
                if stripped.isalpha():
                    keyword = stripped
                    continue
                match = _ADDZCORN.match(line)
                if not match:
                    continue
                sequence += 1
                yield from batcher.add(
                    {
                        "fault_file": path.name,
                        "keyword": keyword,
                        "record_seq": str(sequence),
                        "z_shift": match.group(1),
                        "index_values": " ".join(match.group(2).split()),
                        "comment": comment,
                    },
                    self.relative(path),
                )

        if batcher.pending:
            yield batcher.flush()
