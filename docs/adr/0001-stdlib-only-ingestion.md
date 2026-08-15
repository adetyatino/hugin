# ADR 0001 — The ingestion stage uses the standard library only

Status: accepted
Date: 2026-08-12
Scope: `src/hugin/ingestion/`

## Context

The ingestion brief requires standard library only, and asks that any wish for a
third-party package be written down here first. This ADR records that no
dependency was added, and marks the one place where the question will come back.

The ingestion stage does four things: read zip central directories, compare
archives by checksum, decide where entries land, and copy bytes. `zipfile`,
`binascii`, `csv`, `json` and `pathlib` cover all of it. Nothing was missing.

## Decision

No dependency is added. `pytest` is used to run the tests and is a development
tool, not an import of the shipped module: `inventory.py` imports nothing outside
the standard library, and `python -m hugin.ingestion.inventory` runs on a bare
CPython 3.12.

## Where this will be revisited

`PROD` is delivered as one Excel workbook, `Production_data/Volve production
data.xlsx`. There is no CSV form of it anywhere in the dataset.

It would be easy to claim this forces a dependency. It does not. `.xlsx` is a zip
of XML parts, so `zipfile` plus `xml.etree.ElementTree` can read it, and the two
awkward parts are well understood: strings live in a shared string table
(`sharedStrings.xml`) that cell records reference by index, and dates are stored
as serial numbers against the 1900 epoch with a deliberate leap-year bug that a
reader has to reproduce.

So the real trade-off, when a parser is actually written:

- **stdlib**: no supply chain, no version pinning, but the date-serial and
  shared-string handling must be written and tested by us.
- **`openpyxl`**: those two problems are solved and widely exercised, at the cost
  of a dependency in the ingestion path.

Either is defensible. The decision is deferred because this session writes no
parsers, and taking a dependency now would be taking it for code that does not
exist yet.

## Consequences

- Ingestion runs anywhere CPython 3.12 runs, with no install step.
- CRC verification, checksums and encoding probes all use `binascii`/`zipfile`,
  which read the CRC32 values already present in the central directory. This is
  why duplicate detection costs no extraction.
- Reading `.xlsx` content is out of scope until the ADR above is settled.
- If a future stage needs DLIS, SEG-Y or LAS parsing, that is a new decision and
  a new ADR. Note that those formats dominate the dataset by volume: this ADR
  binds the ingestion stage only, not the pipeline as a whole.
