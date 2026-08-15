"""SEIS/VSP — SEG-Y headers only. Never the traces.

A SEG-Y file opens with a fixed 3,600-byte preamble:

    bytes 0..3199      textual header, 40 lines of 80 characters, **EBCDIC**
    bytes 3200..3599   binary header, big-endian integers at fixed offsets
    bytes 3600..3839   first trace header, 240 bytes

Everything a catalogue needs — survey geometry, sample interval, trace count,
coordinate units — is in those 3,840 bytes. The Volve seismic volume is 1.17 TB.
Reading its header costs under four kilobytes, and SPEC.md section 2 makes that
the point: you get the metadata of a terabyte survey without moving it.

Two modes, same parser:

*   **local** — a file on disk. The delivery ships 136 borehole-seismic
    ``.SEGY`` files under VSP; no surface seismic volume was delivered.
*   **remote** — an HTTP range request for the first 3,840 bytes. Nothing is
    downloaded beyond that, and the reader refuses to fall back to a full GET
    if the server ignores the Range header, because a silent 1.17 TB download
    is not a fallback.

The textual header is EBCDIC (``cp037``), not ASCII. Decoding it as ASCII does
not raise — it produces plausible-looking rubbish, which is worse.
"""

from __future__ import annotations

import re
import struct
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pyarrow as pa

from hugin.ingestion.base import SourceReader
from hugin.ingestion.las import STATIC_LOAD_DATE

__all__ = [
    "BINARY_HEADER_FIELDS",
    "SegyHeaderReader",
    "parse_binary_header",
    "parse_textual_header",
    "parse_trace_header",
    "read_header_bytes",
    "read_remote_header_bytes",
]

TEXTUAL_HEADER_BYTES = 3200
BINARY_HEADER_BYTES = 400
TRACE_HEADER_BYTES = 240
HEADER_BYTES = TEXTUAL_HEADER_BYTES + BINARY_HEADER_BYTES + TRACE_HEADER_BYTES

#: (name, offset within the binary header, struct format). Offsets are the
#: SEG-Y revision 1 standard positions, zero-based from byte 3200.
BINARY_HEADER_FIELDS: tuple[tuple[str, int, str], ...] = (
    ("job_id", 0, ">i"),
    ("line_number", 4, ">i"),
    ("reel_number", 8, ">i"),
    ("traces_per_ensemble", 12, ">h"),
    ("aux_traces_per_ensemble", 14, ">h"),
    ("sample_interval_us", 16, ">h"),
    ("sample_interval_us_original", 18, ">h"),
    ("samples_per_trace", 20, ">h"),
    ("samples_per_trace_original", 22, ">h"),
    ("data_sample_format_code", 24, ">h"),
    ("ensemble_fold", 26, ">h"),
    ("trace_sorting_code", 28, ">h"),
    ("measurement_system", 54, ">h"),
    ("segy_revision", 300, ">h"),
    ("fixed_length_trace_flag", 302, ">h"),
    ("extended_textual_headers", 304, ">h"),
)

#: The trace header fields that say *where* a trace is.
TRACE_HEADER_FIELDS: tuple[tuple[str, int, str], ...] = (
    ("trace_sequence_line", 0, ">i"),
    ("trace_sequence_file", 4, ">i"),
    ("field_record_number", 8, ">i"),
    ("trace_number", 12, ">i"),
    ("scalar_elevation", 68, ">h"),
    ("scalar_coordinates", 70, ">h"),
    ("source_x", 72, ">i"),
    ("source_y", 76, ">i"),
    ("group_x", 80, ">i"),
    ("group_y", 84, ">i"),
    ("coordinate_units", 88, ">h"),
    ("samples_in_trace", 114, ">h"),
    ("sample_interval_in_trace_us", 116, ">h"),
    ("inline_number", 188, ">i"),
    ("crossline_number", 192, ">i"),
)

BUSINESS_COLUMNS = (
    "survey_file",
    "access_mode",
    "textual_header",
    *[name for name, _offset, _format in BINARY_HEADER_FIELDS],
    *[f"trace1_{name}" for name, _offset, _format in TRACE_HEADER_FIELDS],
)


def parse_textual_header(raw: bytes) -> str:
    """Decode the 3,200-byte textual header from EBCDIC into 40 lines.

    ``cp037`` is the EBCDIC code page SEG-Y uses. A file written in ASCII
    instead decodes to noise, which is detectable: the first card of a
    conforming header starts with ``C 1`` or ``C01``.
    """
    text = raw[:TEXTUAL_HEADER_BYTES].decode("cp037", errors="replace")
    if not text.lstrip().upper().startswith("C"):
        ascii_text = raw[:TEXTUAL_HEADER_BYTES].decode("ascii", errors="replace")
        if ascii_text.lstrip().upper().startswith("C"):
            text = ascii_text
    return "\n".join(text[index : index + 80].rstrip() for index in range(0, len(text), 80))


def _unpack(raw: bytes, fields: tuple[tuple[str, int, str], ...], base: int) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, offset, fmt in fields:
        start = base + offset
        size = struct.calcsize(fmt)
        chunk = raw[start : start + size]
        out[name] = str(struct.unpack(fmt, chunk)[0]) if len(chunk) == size else None
    return out


def parse_binary_header(raw: bytes) -> dict[str, str]:
    """Binary header fields, big-endian, at their standard offsets."""
    return _unpack(raw, BINARY_HEADER_FIELDS, TEXTUAL_HEADER_BYTES)


def parse_trace_header(raw: bytes) -> dict[str, str]:
    """First trace header: where the survey starts and how it is gridded."""
    values = _unpack(raw, TRACE_HEADER_FIELDS, TEXTUAL_HEADER_BYTES + BINARY_HEADER_BYTES)
    return {f"trace1_{name}": value for name, value in values.items()}


def read_header_bytes(path: Path) -> bytes:
    """The first 3,840 bytes of a local file, and not one byte more."""
    with open(path, "rb") as handle:
        return handle.read(HEADER_BYTES)


def read_remote_header_bytes(url: str, timeout: float = 30.0) -> bytes:
    """The first 3,840 bytes of a remote file, over an HTTP range request.

    Refuses to accept a response that is not a 206 Partial Content. A server
    that ignores ``Range`` answers 200 with the whole body, and for this dataset
    the whole body is 1.17 TB — a fallback that would quietly become a download.
    """
    import httpx

    headers = {"Range": f"bytes=0-{HEADER_BYTES - 1}"}
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(url, headers=headers)
        if response.status_code != 206:
            raise RuntimeError(
                f"{url} answered {response.status_code}, not 206 Partial Content: "
                f"the server ignored the Range header. Refusing to read the whole "
                f"object — that is the download this reader exists to avoid."
            )
        return response.content


class SegyHeaderReader(SourceReader):
    """One row per SEG-Y file: its headers, never its traces.

    ``remote_urls`` switches the reader to range requests. Local and remote
    produce identical rows apart from ``access_mode``, because the parsing is
    the same bytes either way.
    """

    source_system = "SEIS"
    table = "bronze.segy_header"
    business_columns = BUSINESS_COLUMNS
    identifier_column = None

    def __init__(self, *args, remote_urls: list[str] | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.remote_urls = remote_urls or []

    def source_files(self) -> list[Path]:
        root = self.settings.landing_dir
        if not root.exists():
            return []
        return sorted(
            p for p in root.rglob("*") if p.is_file() and p.suffix.lower() == ".segy"
        )

    def read(self, replay_date: date) -> Iterator[pa.RecordBatch]:
        if replay_date != STATIC_LOAD_DATE:
            return
        batcher = self.batcher(replay_date)

        for path in self.source_files():
            raw = read_header_bytes(path)
            record = self._record(raw, str(path.name), "local")
            # The borehole surveys are per-well; the well is in the path, and
            # the textual header names it too.
            record["_source_identifier"] = _identity_from_textual(record["textual_header"])
            yield from batcher.add(record, self.relative(path))

        for url in self.remote_urls:
            raw = read_remote_header_bytes(url)
            record = self._record(raw, url, "remote_range")
            record["_source_identifier"] = _identity_from_textual(record["textual_header"])
            yield from batcher.add(record, url)

        if batcher.pending:
            yield batcher.flush()

    def _record(self, raw: bytes, survey_file: str, mode: str) -> dict[str, str | None]:
        return {
            "survey_file": survey_file,
            "access_mode": mode,
            "textual_header": parse_textual_header(raw),
            **parse_binary_header(raw),
            **parse_trace_header(raw),
        }


def _identity_from_textual(header: str) -> str | None:
    """A well name written into the textual header, if there is one.

    The VSP headers carry lines like ``WELL : 15/9-F-15A``. Returned as
    written; BR-12 does the normalising.
    """
    # A card can hold two labelled fields: 'CLIENT SURVEY : ... WELL : 15/9-F-15A'.
    # Splitting on the first colon returns the whole card, so match the label.
    pattern = re.compile(r"\bWELL\s*:\s*(.+?)\s*$", re.I)
    for line in header.splitlines():
        match = pattern.search(line)
        if match and match.group(1):
            return match.group(1).strip()
    return None
