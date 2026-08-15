"""WITSML — drilling telemetry, streamed with lxml iterparse.

**What this delivery actually contains, and does not.** The brief asks for the
``log`` element and its ``mnemonicList``, emitted as a columnar time series.
That parser is here and it is namespace-driven, but it will find nothing in this
delivery: ``mnemonicList`` appears in **zero** of the 10,773 extracted files.
The ``log/`` directories hold only ``MetaFileInfo.txt`` files that *list the
names* of logs — "12.25 in Section - Time Log", "Real Time MWD/LWD data - 8.5in.
Pilot - MD Log" — which the export never wrote out. The curves exist in the
source system; they were not delivered.

That absence is worth stating plainly because it changes what layer 2 of
SPEC.md can be built from: the streaming throughput demonstration has no real
WITSML curve data behind it, and the calibrated fixtures of SPEC.md section 10
are the honest way to supply volume for it.

What the delivery *does* contain, and what this module therefore also reads:

    message      3,944 documents — timestamped drilling messages with a depth
    mudLog       1 document — geology intervals with ROP and WOB statistics
    bhaRun, tubular, rig, wbGeometry, trajectory

The message documents are real drilling telemetry of a coarser kind, and
dropping them because they are not the element the brief named would lose the
only time-indexed drilling data in the dataset.

**Namespace handling.** Version is read from the document, never hardcoded.
WITSML 1.3 binds ``http://www.witsml.org/schemas/131`` and 1.4 binds
``http://www.witsml.org/schemas/1series``; this delivery is 1.4.1.1 throughout,
and the DDR export is 1.4.0.0 under a prefixed binding of the same namespace.
Matching on local names, with the namespace recorded per document, handles all
of them without a version test.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path

import pyarrow as pa
from lxml import etree

from hugin.ingestion.base import SourceReader

__all__ = [
    "WitsmlLogDataReader",
    "WitsmlLogHeaderReader",
    "WitsmlMessageReader",
    "document_namespace",
    "survey_document_types",
]

LOG_HEADER_COLUMNS = (
    "namespace",
    "schema_version",
    "uid_well",
    "uid_wellbore",
    "uid_log",
    "name_well",
    "name_wellbore",
    "log_name",
    "index_type",
    "index_curve",
    "start_index",
    "end_index",
    "direction",
    "curve_seq",
    "mnemonic",
    "unit",
    "curve_description",
)

LOG_DATA_COLUMNS = (
    "namespace",
    "schema_version",
    "uid_well",
    "uid_wellbore",
    "uid_log",
    "name_well",
    "name_wellbore",
    "log_name",
    "index_value",
    "mnemonic",
    "unit",
    "value",
)

MESSAGE_COLUMNS = (
    "namespace",
    "schema_version",
    "uid_well",
    "uid_wellbore",
    "uid_message",
    "name_well",
    "name_wellbore",
    "message_name",
    "dtim",
    "md",
    "md_uom",
    "type_message",
    "message_text",
    "source_name",
)


def _local(tag: object) -> str:
    return str(tag).rsplit("}", 1)[-1]


def _namespace(tag: object) -> str | None:
    text = str(tag)
    return text[1:].split("}", 1)[0] if text.startswith("{") else None


def document_namespace(path: Path) -> tuple[str | None, str | None]:
    """``(namespace, version)`` of a WITSML document, read from the document.

    Cheap: stops at the root element. Both 1.3 and 1.4 are recognised because
    neither is assumed — the namespace is whatever the file declares.
    """
    try:
        for _event, element in etree.iterparse(str(path), events=("start",)):
            return _namespace(element.tag), element.get("version")
    except (etree.XMLSyntaxError, OSError):
        return None, None
    return None, None


def survey_document_types(root: Path) -> dict[str, int]:
    """Count WITSML document types present under a directory.

    Used to state what the delivery holds rather than assume it: this is how
    the absence of ``log`` documents was established.
    """
    counts: dict[str, int] = {}
    for path in sorted(root.rglob("*.xml")):
        if not path.is_file():
            continue
        try:
            for _event, element in etree.iterparse(str(path), events=("start",)):
                name = _local(element.tag)
                # The root is a plural collection: <messages>, <logs>, <wells>.
                counts[name] = counts.get(name, 0) + 1
                break
        except (etree.XMLSyntaxError, OSError):
            counts["unparseable"] = counts.get("unparseable", 0) + 1
    return counts


class _WitsmlReader(SourceReader):
    source_system = "WITSML"
    identifier_column = "name_wellbore"

    def root(self) -> Path:
        return self.settings.landing_dir / "witsml"

    def source_files(self) -> list[Path]:
        root = self.root()
        if not root.exists():
            return []
        return sorted(p for p in root.rglob("*.xml") if p.is_file())

    def _header(self, element: etree._Element, path: Path) -> dict[str, str | None]:
        namespace, version = _namespace(element.tag), None
        parent = element.getparent()
        if parent is not None:
            version = parent.get("version")
        header = {
            "namespace": namespace,
            "schema_version": version or element.get("version"),
            "uid_well": element.get("uidWell"),
            "uid_wellbore": element.get("uidWellbore"),
        }
        for child in element:
            tag = _local(child.tag)
            if tag == "nameWell":
                header["name_well"] = (child.text or "").strip() or None
            elif tag == "nameWellbore":
                header["name_wellbore"] = (child.text or "").strip() or None
        return header


class WitsmlLogHeaderReader(_WitsmlReader):
    """One row per curve declared in a ``log`` document's ``logCurveInfo``.

    Yields nothing against this delivery: it contains no ``log`` documents. The
    code path is namespace-driven and tested against a synthetic 1.3 and 1.4
    document, so a delivery that does contain them needs no change here.
    """

    table = "bronze.witsml_log_header"
    business_columns = LOG_HEADER_COLUMNS

    def read(self, replay_date: date) -> Iterator[pa.RecordBatch]:
        batcher = self.batcher(replay_date)
        for path in self.source_files():
            for record in _iter_log_curves(path, replay_date):
                yield from batcher.add(record, self.relative(path))
        if batcher.pending:
            yield batcher.flush()


class WitsmlLogDataReader(_WitsmlReader):
    """One row per (index value, mnemonic) from a ``log`` document's ``logData``.

    ``mnemonicList`` is a comma-separated header and each ``data`` element is a
    comma-separated row aligned to it; the pair is what makes the section
    columnar. Splitting the row without the list, or assuming a fixed column
    order, silently mislabels every curve.
    """

    table = "bronze.witsml_log_data"
    business_columns = LOG_DATA_COLUMNS

    def read(self, replay_date: date) -> Iterator[pa.RecordBatch]:
        batcher = self.batcher(replay_date)
        for path in self.source_files():
            for record in _iter_log_data(path, replay_date):
                yield from batcher.add(record, self.relative(path))
        if batcher.pending:
            yield batcher.flush()


class WitsmlMessageReader(_WitsmlReader):
    """One row per drilling message — the time-indexed data this delivery has."""

    table = "bronze.witsml_message"
    business_columns = MESSAGE_COLUMNS

    def read(self, replay_date: date) -> Iterator[pa.RecordBatch]:
        batcher = self.batcher(replay_date)

        for path in self.source_files():
            try:
                context = etree.iterparse(str(path), events=("end",))
            except (etree.XMLSyntaxError, OSError):
                continue
            relative = self.relative(path)
            try:
                for _event, element in context:
                    if _local(element.tag) != "message":
                        continue
                    record = self._header(element, path)
                    record["uid_message"] = element.get("uid")
                    for child in element:
                        tag = _local(child.tag)
                        text = (child.text or "").strip() if child.text else None
                        if tag == "name":
                            record["message_name"] = text
                        elif tag == "dTim":
                            record["dtim"] = text
                        elif tag == "md":
                            record["md"] = text
                            record["md_uom"] = child.get("uom")
                        elif tag == "typeMessage":
                            record["type_message"] = text
                        elif tag == "messageText":
                            record["message_text"] = text
                        elif tag == "commonData":
                            for node in child:
                                if _local(node.tag) == "sourceName":
                                    record["source_name"] = (node.text or "").strip() or None
                    element.clear()

                    if _date_of(record.get("dtim")) != replay_date:
                        continue
                    yield from batcher.add(record, relative)
            except etree.XMLSyntaxError:
                continue

        if batcher.pending:
            yield batcher.flush()


def _date_of(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _log_elements(path: Path) -> Iterator[etree._Element]:
    try:
        for _event, element in etree.iterparse(str(path), events=("end",)):
            if _local(element.tag) == "log":
                yield element
                element.clear()
    except (etree.XMLSyntaxError, OSError):
        return


def _log_header(element: etree._Element) -> dict[str, str | None]:
    parent = element.getparent()
    header: dict[str, str | None] = {
        "namespace": _namespace(element.tag),
        "schema_version": (parent.get("version") if parent is not None else None)
        or element.get("version"),
        "uid_well": element.get("uidWell"),
        "uid_wellbore": element.get("uidWellbore"),
        "uid_log": element.get("uid"),
        "name_well": None,
        "name_wellbore": None,
        "log_name": None,
        "index_type": None,
        "index_curve": None,
        "start_index": None,
        "end_index": None,
        "direction": None,
    }
    mapping = {
        "nameWell": "name_well",
        "nameWellbore": "name_wellbore",
        "name": "log_name",
        "indexType": "index_type",
        "indexCurve": "index_curve",
        "startIndex": "start_index",
        "endIndex": "end_index",
        "startDateTimeIndex": "start_index",
        "endDateTimeIndex": "end_index",
        "direction": "direction",
    }
    for child in element:
        column = mapping.get(_local(child.tag))
        if column and header.get(column) is None:
            header[column] = (child.text or "").strip() or None
    return header


def _iter_log_curves(path: Path, replay_date: date) -> Iterator[dict[str, str | None]]:
    for element in _log_elements(path):
        header = _log_header(element)
        header["_source_identifier"] = header["name_wellbore"] or header["name_well"]
        sequence = 0
        for child in element:
            if _local(child.tag) != "logCurveInfo":
                continue
            sequence += 1
            record = dict(header)
            record["curve_seq"] = str(sequence)
            for node in child:
                tag = _local(node.tag)
                text = (node.text or "").strip() if node.text else None
                if tag == "mnemonic":
                    record["mnemonic"] = text
                elif tag == "unit":
                    record["unit"] = text
                elif tag in ("curveDescription", "description"):
                    record["curve_description"] = text
            yield record


def _iter_log_data(path: Path, replay_date: date) -> Iterator[dict[str, str | None]]:
    for element in _log_elements(path):
        header = _log_header(element)
        header["_source_identifier"] = header["name_wellbore"] or header["name_well"]

        for child in element:
            if _local(child.tag) != "logData":
                continue
            mnemonics: list[str] = []
            units: list[str] = []
            for node in child:
                tag = _local(node.tag)
                text = (node.text or "").strip() if node.text else ""
                if tag == "mnemonicList":
                    mnemonics = [m.strip() for m in text.split(",")]
                elif tag == "unitList":
                    units = [u.strip() for u in text.split(",")]
                elif tag == "data" and mnemonics:
                    values = [v.strip() for v in text.split(",")]
                    if not values:
                        continue
                    index_value = values[0]
                    if _date_of(index_value) not in (None, replay_date):
                        continue
                    for position, value in enumerate(values[1:], start=1):
                        if position >= len(mnemonics):
                            break
                        record = dict(header)
                        record.update({
                            "index_value": index_value,
                            "mnemonic": mnemonics[position],
                            "unit": units[position] if position < len(units) else None,
                            "value": value,
                        })
                        yield record
