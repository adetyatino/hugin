"""Reading the shapes this dataset actually ships, with the standard library.

Two things live here because more than one stage needs them and neither is worth
a dependency:

*   ``.xlsx`` — a zip of XML parts. The whole of Volve's production history is
    one such file and there is no CSV form of it anywhere in the delivery
    (docs/data-inventory.md, finding 7). ADR 0001 records why this is written
    out rather than imported.
*   text decoding — the delivery mixes ASCII, UTF-8 and cp1252 across sources,
    and some files carry Scandinavian letters. Guessing wrong turns ``Æ`` into
    two characters or a crash.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterator
from pathlib import Path

__all__ = ["decode_text", "read_text", "sheet_names", "xlsx_rows", "xlsx_table"]

XLSX_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

#: Tried in order. UTF-8 first because a UTF-8 file decoded as cp1252 is
#: mojibake rather than an error, so the strict attempt has to come first;
#: cp1252 never fails, which is why it is last.
TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252")


def decode_text(raw: bytes, encodings: tuple[str, ...] = TEXT_ENCODINGS) -> tuple[str, str]:
    """Decode bytes, returning ``(text, encoding_used)``.

    The encoding actually used is returned rather than discarded: it is a fact
    about the source file, and bronze records facts about source files.
    """
    for encoding in encodings:
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return raw.decode("cp1252", errors="replace"), "cp1252+replace"


def read_text(path: Path) -> tuple[str, str]:
    """Read a text file without assuming its encoding."""
    return decode_text(path.read_bytes())


def _column_letters(reference: str) -> str:
    return "".join(char for char in reference if char.isalpha())


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    # A shared string can be split across several runs; join them all.
    return [
        "".join(node.text or "" for node in item.iter(f"{XLSX_NS}t"))
        for item in root.findall(f"{XLSX_NS}si")
    ]


def sheet_names(path: Path) -> dict[str, str]:
    """Sheet name -> part path, in workbook order."""
    with zipfile.ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        target_by_id = {
            node.get("Id"): node.get("Target", "") for node in rels
        }
        out: dict[str, str] = {}
        for index, sheet in enumerate(workbook.iter(f"{XLSX_NS}sheet"), start=1):
            rid = next(
                (v for k, v in sheet.attrib.items() if k.endswith("}id")), None
            )
            target = target_by_id.get(rid or "", f"worksheets/sheet{index}.xml")
            if not target.startswith("xl/"):
                target = "xl/" + target.lstrip("/")
            out[sheet.get("name", f"sheet{index}")] = target
        return out


def xlsx_rows(path: Path, sheet_part: str) -> Iterator[dict[str, str]]:
    """Stream one worksheet as ``{column letter: value}``, values as written.

    Streamed with ``iterparse``: the daily production sheet is 14 MB of XML and
    there is no reason to hold it. Empty cells are absent from the dict rather
    than present as None, so a caller can tell "no cell" from "empty cell".
    """
    with zipfile.ZipFile(path) as archive:
        shared = _shared_strings(archive)
        with archive.open(sheet_part) as handle:
            for _event, row in ET.iterparse(handle, events=("end",)):
                if row.tag != f"{XLSX_NS}row":
                    continue
                cells: dict[str, str] = {}
                for cell in row.findall(f"{XLSX_NS}c"):
                    cell_type = cell.get("t")
                    if cell_type == "inlineStr":
                        node = cell.find(f"{XLSX_NS}is")
                        value = (
                            "".join(t.text or "" for t in node.iter(f"{XLSX_NS}t"))
                            if node is not None else None
                        )
                    else:
                        node = cell.find(f"{XLSX_NS}v")
                        value = node.text if node is not None else None
                        if cell_type == "s" and value is not None:
                            index = int(value)
                            value = shared[index] if index < len(shared) else None
                    if value is not None:
                        cells[_column_letters(cell.get("r", ""))] = value
                yield cells
                row.clear()


def xlsx_table(
    path: Path,
    sheet_part: str,
    *,
    header_row: int = 1,
    skip_rows: int = 0,
) -> Iterator[dict[str, str]]:
    """Stream a worksheet as ``{column name: value}`` using a header row.

    ``skip_rows`` drops rows between the header and the data — the monthly
    production sheet puts its units on the row below the header, which is a
    second header rather than a record.

    Rows with no populated cell at all are skipped: the monthly sheet ends with
    one, and a blank trailer is not a record.
    """
    names: dict[str, str] = {}
    for index, cells in enumerate(xlsx_rows(path, sheet_part), start=1):
        if index < header_row:
            continue
        if index == header_row:
            names = {letter: value.strip() for letter, value in cells.items()}
            continue
        if index <= header_row + skip_rows:
            continue
        if not cells:
            continue
        yield {
            names.get(letter, letter): value for letter, value in cells.items()
        }
