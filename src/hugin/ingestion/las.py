"""LOG — well logs. Two streams: curve metadata and samples.

BR-08 is the reason this module reads the NULL sentinel from every file's
``~WELL`` section instead of using a constant. Measured across the delivery:

    -999.25   what everyone expects
    -9999     what several files actually declare

Both are declared by the file that uses them. A pipeline that hard-coded
``-999.25`` would carry ``-9999`` through as a measurement, and −9999 does not
look wrong in an average until the average is wrong. The sentinel is read per
file and carried into bronze as ``null_value_declared`` beside every sample, so
silver can apply BR-08 without reopening the file and a reader can see which
sentinel applied to which row.

Bronze stores sample values **as written**, sentinel included. Converting here
would be cleaning, which belongs in silver.

Three more measured facts shape this module:

*   **Two LAS dialects.** Most files are LAS 2.0, whitespace-aligned. Others
    are LAS 3.0 declaring ``DLM. COMMA`` with vendor sections
    (``~Phase_Definition_RMDATA``, ``~PolarisInterpretation_Parameters[1]``).
    The delimiter is read from ``DLM``, never assumed.
*   **lasio is not usable for every file here.** On one 3.2 MB LAS 3.0 file it
    takes 243 seconds and returns zero curves. So headers are scanned directly
    — which is what BR-08 requires anyway, "read it from the header" — and
    lasio parses the data section where it is the better tool, on the LAS 2.0
    files it was built for.
*   **Dates are not usable for scheduling.** ``~WELL`` DATE values include
    ``UNKNOWN``, empty, ``22-Jun-09`` and ``Wed Nov 26 21-01-09``. Logs load as
    static reference data on one declared date rather than pretending to a
    schedule; the declared value is stored as written, whatever it says.

A file that cannot be parsed is recorded, not skipped: :meth:`parse_failures`
lists them with the reason, and the load report states the count.
"""

from __future__ import annotations

import re
import warnings
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pyarrow as pa

from hugin.common.io import read_text
from hugin.common.replay import FIELD_START
from hugin.ingestion.base import SourceReader

__all__ = [
    "STATIC_LOAD_DATE",
    "LasCurveHeaderReader",
    "LasHeader",
    "LasSampleReader",
    "scan_header",
]

#: Logs carry no reliable acquisition date, so they load once, on the first day
#: of field life. Any other choice either invents a date the file does not
#: declare or reloads the same curves on every replay date.
STATIC_LOAD_DATE = FIELD_START

#: ``MNEM.UNIT  VALUE : DESCRIPTION``.
#:
#: Two things make this harder than it looks, and both bite:
#:
#: * The unit is attached to the dot with no space (``STRT.M``), so a pattern
#:   that skips whitespace after the dot reads the *value* as the unit. That is
#:   how ``NULL.   -999.25   : NULL`` ends up declaring a unit of ``-999.25``
#:   and no sentinel at all — which would defeat BR-08 silently.
#: * The value may contain colons: ``STRT. 00:00:00 09-Jun-08 : START INDEX``.
#:   The description follows the *last* colon, not the first.
_HEADER_LINE = re.compile(r"^\s*([^.\s]+)\s*\.(\S*)\s*(.*)$")

HEADER_COLUMNS = (
    "well_name",
    "uwi",
    "field",
    "company",
    "service_company",
    "date_declared",
    "null_value_declared",
    "las_version",
    "wrapped",
    "delimiter_declared",
    "start",
    "stop",
    "step",
    "index_mnemonic",
    "index_unit",
    "curve_index",
    "mnemonic",
    "unit",
    "api_code",
    "description",
)

SAMPLE_COLUMNS = (
    "well_name",
    "mnemonic",
    "index_mnemonic",
    "index_value",
    "index_unit",
    "value",
    "null_value_declared",
)

#: LAS names the delimiter rather than writing it.
_DELIMITERS = {"COMMA": ",", "TAB": "\t", "SPACE": None}


@dataclass
class LasHeader:
    """Everything the header declares, read without touching the data section."""

    path: Path
    version: str | None = None
    wrap: str | None = None
    delimiter_name: str | None = None
    null_value: str | None = None
    well: dict[str, str] = field(default_factory=dict)
    curves: list[dict[str, str | None]] = field(default_factory=list)
    data_start_line: int | None = None
    error: str | None = None

    @property
    def delimiter(self) -> str | None:
        """Separator for the data section; None means any run of whitespace."""
        return _DELIMITERS.get((self.delimiter_name or "SPACE").upper(), None)

    @property
    def identity(self) -> str | None:
        """The wellbore as this file names it: WELL, else UWI, else API."""
        for mnemonic in ("WELL", "UWI", "API"):
            value = self.well.get(mnemonic)
            if value:
                return value
        return None

    @property
    def is_las2_unwrapped(self) -> bool:
        """True where lasio is the better tool for the data section."""
        version = (self.version or "2.0").split()[0]
        try:
            major = float(version)
        except ValueError:
            major = 2.0
        return major < 3.0 and (self.wrap or "NO").upper() == "NO"


def scan_header(path: Path) -> LasHeader:
    """Read a LAS header directly. Never parses the data section.

    Fast and total: it does not care how large or how odd the data section is,
    which is what makes it safe to run over every file. Section markers start
    with ``~`` and the letter after it names the section; ``~A`` (or the LAS 3.0
    ``~..._data...`` forms) begins the data.
    """
    header = LasHeader(path=path)
    try:
        text, _encoding = read_text(path)
    except OSError as exc:
        header.error = f"unreadable: {exc}"
        return header

    section = ""
    for number, line in enumerate(text.splitlines()):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("~"):
            name = stripped[1:].strip()
            # A LAS 3.0 data section names its own definition section after a
            # pipe: '~Phase_data_RMDATA | Phase_Definition_RMDATA'. Only the
            # part before the pipe names *this* section, and testing the whole
            # line for '_DEFINITION' reads the entire data section as curve
            # definitions.
            upper = name.split("|")[0].strip().upper()
            section = upper[:1]
            # LAS 3.0 pairs a '~<name>_Definition' section, which defines
            # curves, with a '~<name>_Data' section holding them. Neither
            # starts with C or A, so the LAS 2.0 letter test misses both and
            # the file looks like it has no curves at all.
            if upper.startswith("A") or "_DATA" in upper:
                header.data_start_line = number + 1
                break
            if "_DEFINITION" in upper or upper.endswith("_CURVE"):
                section = "C"
            continue

        match = _HEADER_LINE.match(stripped)
        if not match:
            continue
        mnemonic, unit, remainder = (group.strip() for group in match.groups())
        mnemonic = mnemonic.upper()
        # Description is everything after the last colon; the value keeps any
        # colons of its own.
        value, _sep, description = remainder.rpartition(":")
        if not _sep:
            value, description = remainder, ""
        value, description = value.strip(), description.strip()

        if section == "V":
            if mnemonic == "VERS":
                header.version = value or unit
            elif mnemonic == "WRAP":
                header.wrap = value or unit
            elif mnemonic == "DLM":
                header.delimiter_name = value or unit
        elif section == "W":
            header.well[mnemonic] = value
            if mnemonic == "NULL":
                header.null_value = value
        elif section == "C":
            header.curves.append({
                "mnemonic": mnemonic,
                "unit": unit or None,
                "api_code": value or None,
                "description": description or None,
            })

    if not header.curves:
        header.error = header.error or "no ~CURVE section"
    return header


class _LasReader(SourceReader):
    source_system = "LOG"
    identifier_column = "well_name"
    landing_subdir = "log"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._failures: list[tuple[str, str]] = []

    def source_files(self) -> list[Path]:
        root = self.settings.landing_dir / self.landing_subdir
        if not root.exists():
            return []
        return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() == ".las")

    def parse_failures(self) -> list[tuple[str, str]]:
        """(file, reason) for every file this reader could not read."""
        return list(self._failures)


class LasCurveHeaderReader(_LasReader):
    """One row per curve per file: what was logged, in what unit, over what range."""

    table = "bronze.las_curve_header"
    business_columns = HEADER_COLUMNS

    def read(self, replay_date: date) -> Iterator[pa.RecordBatch]:
        if replay_date != STATIC_LOAD_DATE:
            return
        batcher = self.batcher(replay_date)

        for path in self.source_files():
            header = scan_header(path)
            if header.error and not header.curves:
                self._failures.append((self.relative(path), header.error))
                continue
            index_curve = header.curves[0] if header.curves else {}
            common = {
                "well_name": header.identity,
                "uwi": header.well.get("UWI"),
                "field": header.well.get("FLD"),
                "company": header.well.get("COMP"),
                "service_company": header.well.get("SRVC"),
                "date_declared": header.well.get("DATE"),
                "null_value_declared": header.null_value,
                "las_version": header.version,
                "wrapped": header.wrap,
                "delimiter_declared": header.delimiter_name,
                "start": header.well.get("STRT"),
                "stop": header.well.get("STOP"),
                "step": header.well.get("STEP"),
                "index_mnemonic": index_curve.get("mnemonic"),
                "index_unit": index_curve.get("unit"),
                "_source_identifier": header.identity,
            }
            for index, curve in enumerate(header.curves):
                record = dict(common)
                record.update({
                    "curve_index": str(index),
                    "mnemonic": curve["mnemonic"],
                    "unit": curve["unit"],
                    "api_code": curve["api_code"],
                    "description": curve["description"],
                })
                yield from batcher.add(record, self.relative(path))

        if batcher.pending:
            yield batcher.flush()


class LasSampleReader(_LasReader):
    """One row per index value per curve.

    The index curve — depth or time, whichever the file lists first — is not a
    sample of itself; it is the ``index_value`` every other curve is measured
    at.

    ``max_files`` bounds a demonstration load. It defaults to unbounded; the
    load job sets it and the load report states the value, so a bounded run is
    never mistaken for a complete one.
    """

    table = "bronze.las_sample"
    business_columns = SAMPLE_COLUMNS

    def __init__(self, *args, max_files: int | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.max_files = max_files

    def read(self, replay_date: date) -> Iterator[pa.RecordBatch]:
        if replay_date != STATIC_LOAD_DATE:
            return
        batcher = self.batcher(replay_date)
        files = self.source_files()
        if self.max_files is not None:
            # Smallest first, so a bounded run covers the most files rather
            # than the most bytes.
            files = sorted(files, key=lambda p: p.stat().st_size)[: self.max_files]

        for path in files:
            header = scan_header(path)
            if not header.curves:
                self._failures.append((self.relative(path), header.error or "no curves"))
                continue
            rows = self._rows(path, header)
            if rows is None:
                continue
            relative = self.relative(path)
            for record in rows:
                yield from batcher.add(record, relative)

        if batcher.pending:
            yield batcher.flush()

    def _rows(self, path: Path, header: LasHeader) -> Iterator[dict[str, str | None]] | None:
        if header.is_las2_unwrapped:
            values = self._values_via_lasio(path, header)
            if values is None:
                values = self._values_direct(path, header)
        else:
            values = self._values_direct(path, header)
        return values

    def _values_via_lasio(self, path: Path, header: LasHeader):
        """LAS 2.0 data through lasio, the library the brief names."""
        import lasio

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                las = lasio.read(str(path), engine="normal", ignore_header_errors=True)
            except Exception as exc:
                self._failures.append((self.relative(path), f"lasio: {type(exc).__name__}"))
                return None
        if not las.curves:
            return None

        index_curve = las.curves[0]
        index_data = index_curve.data
        identity = header.identity

        def generate():
            for curve in las.curves[1:]:
                data = curve.data
                if data is None or index_data is None:
                    continue
                for position in range(min(len(index_data), len(data))):
                    yield {
                        "well_name": identity,
                        "mnemonic": curve.mnemonic,
                        "index_mnemonic": index_curve.mnemonic,
                        "index_value": str(index_data[position]),
                        "index_unit": index_curve.unit,
                        "value": str(data[position]),
                        "null_value_declared": header.null_value,
                        "_source_identifier": identity,
                    }

        return generate()

    def _values_direct(self, path: Path, header: LasHeader):
        """Data section read with the delimiter the file declares.

        For LAS 3.0 and anything lasio cannot take. Values are split and stored
        verbatim — no float conversion, so nothing about the source's own
        spelling is lost on the way into bronze.
        """
        if header.data_start_line is None:
            self._failures.append((self.relative(path), "no data section"))
            return None

        text, _encoding = read_text(path)
        lines = text.splitlines()[header.data_start_line:]
        names = [curve["mnemonic"] for curve in header.curves]
        identity = header.identity
        delimiter = header.delimiter

        def generate():
            for line in lines:
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or stripped.startswith("~"):
                    continue
                parts = (
                    [p.strip() for p in stripped.split(delimiter)]
                    if delimiter else stripped.split()
                )
                if len(parts) < 2:
                    continue
                index_value = parts[0]
                for position, value in enumerate(parts[1:], start=1):
                    if position >= len(names):
                        break
                    yield {
                        "well_name": identity,
                        "mnemonic": names[position],
                        "index_mnemonic": names[0],
                        "index_value": index_value,
                        "index_unit": header.curves[0]["unit"],
                        "value": value,
                        "null_value_declared": header.null_value,
                        "_source_identifier": identity,
                    }

        return generate()
