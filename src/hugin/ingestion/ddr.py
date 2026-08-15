"""DDR — daily drilling reports, one row per reported activity.

The delivery ships each report three times: ``.xml``, ``.html`` and ``.pdf``,
1,759 of each, same basename. They are the same report rendered three ways, so
this reader takes the XML and treats the HTML as a fallback for a report whose
XML is missing. PDF is ignored in this phase, as the brief directs.

Format facts, measured (docs/data-dictionary.md):

*   XML is WITSML 1.4.0.0 under the ``witsml:`` prefix bound to
    ``http://www.witsml.org/schemas/1series``, against an NPD-profiled schema.
    Note the version differs from the drilling-telemetry exports (1.4.1.1) and
    the prefix binding differs from their default namespace, so the namespace
    is detected, never assumed.
*   The report's own date is ``dTimEnd``, written with a local offset
    (``+01:00`` in winter, ``+02:00`` in summer). The file name carries the same
    date: ``15_9_F_14_2016_08_04.xml`` ends on 2016-08-04. The file name is used
    to find candidate files for a replay date; the XML then confirms it.
*   Dates appear as ISO 8601 date-time and as plain ``YYYY-MM-DD``.
*   Units written in the file: ``dega``, ``m``, ``m/h``.
*   ``wellAlias``/``wellboreAlias`` carry the NPD register name and number —
    the only nationally authoritative identifier in the delivery, and what makes
    DDR the source that teaches BR-12 what every NPD number means.

Activity comments are free text, multi-line, and occasionally contain the
characters that would break a delimited format. They are stored as written.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path

import pyarrow as pa
from lxml import etree

from hugin.ingestion.base import SourceReader

__all__ = ["DDRActivityReader", "report_date_from_name"]

#: ``15_9_F_14_2016_08_04`` -> the trailing date.
_NAME_DATE = re.compile(r"_(\d{4})_(\d{2})_(\d{2})$")

BUSINESS_COLUMNS = (
    "report_date",
    "name_well",
    "name_wellbore",
    "npd_code_well",
    "npd_code_wellbore",
    "npd_number",
    "rig_alias",
    "document_name",
    "document_owner",
    "version_kind",
    "create_date",
    "dtim_start",
    "dtim_end",
    "activity_seq",
    "activity_dtim_start",
    "activity_dtim_end",
    "activity_md",
    "activity_md_uom",
    "phase",
    "proprietary_code",
    "state",
    "state_detail_activity",
    "comments",
    "source_format",
)


def report_date_from_name(path: Path) -> date | None:
    """The report date encoded in the file name, or None."""
    match = _NAME_DATE.search(path.stem)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def _local_name(tag: object) -> str:
    return str(tag).rsplit("}", 1)[-1]


def _date_of(value: str) -> date | None:
    """Date part of a WITSML timestamp, in the offset the source wrote it.

    ``2016-08-04T00:00:00+02:00`` is 2016-08-04 locally and 2016-08-03 in UTC.
    The file name says 2016-08-04, so the source means local, and converting
    would move a third of the reports to the previous day.
    """
    text = (value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None


class DDRActivityReader(SourceReader):
    """One row per activity within a daily drilling report."""

    source_system = "DDR"
    table = "bronze.ddr_activity"
    business_columns = BUSINESS_COLUMNS
    identifier_column = "name_wellbore"

    #: XML first; HTML only where a report has no XML form.
    XML_DIR = "Daily Drilling Report - XML Version"
    HTML_DIR = "Daily Drilling report - HTML Version"

    def root(self) -> Path:
        return self.settings.landing_dir / "ddr"

    def source_files(self) -> list[Path]:
        root = self.root()
        return sorted(root.rglob("*.xml")) if root.exists() else []

    def _files_for(self, replay_date: date) -> tuple[list[Path], list[Path]]:
        """(xml files, html files with no xml sibling) for one replay date."""
        root = self.root()
        if not root.exists():
            return [], []
        xml = [p for p in root.rglob("*.xml") if report_date_from_name(p) == replay_date]
        covered = {p.stem for p in xml}
        html = [
            p for p in root.rglob("*.html")
            if report_date_from_name(p) == replay_date and p.stem not in covered
        ]
        return sorted(xml), sorted(html)

    def read(self, replay_date: date) -> Iterator[pa.RecordBatch]:
        xml_files, html_files = self._files_for(replay_date)
        batcher = self.batcher(replay_date)

        for path in xml_files:
            for record in self._read_xml(path, replay_date):
                yield from batcher.add(record, self.relative(path))

        for path in html_files:
            for record in self._read_html(path, replay_date):
                yield from batcher.add(record, self.relative(path))

        if batcher.pending:
            yield batcher.flush()

    # -- XML ---------------------------------------------------------------

    def _read_xml(self, path: Path, replay_date: date) -> Iterator[dict[str, str | None]]:
        """Stream one report. Namespace is read from the document, not assumed."""
        try:
            tree = etree.parse(str(path))
        except (etree.XMLSyntaxError, OSError):
            return
        root = tree.getroot()

        report = next(
            (el for el in root.iter() if _local_name(el.tag) == "drillReport"), None
        )
        if report is None:
            return

        header: dict[str, str | None] = {name: None for name in BUSINESS_COLUMNS}
        header["source_format"] = "xml"
        aliases: list[tuple[str, str, str]] = []
        activities: list[etree._Element] = []

        for child in report:
            tag = _local_name(child.tag)
            text = (child.text or "").strip() if child.text else None
            if tag == "nameWell":
                header["name_well"] = text
            elif tag == "nameWellbore":
                header["name_wellbore"] = text
            elif tag == "dTimStart":
                header["dtim_start"] = text
            elif tag == "dTimEnd":
                header["dtim_end"] = text
            elif tag == "versionKind":
                header["version_kind"] = text
            elif tag == "createDate":
                header["create_date"] = text
            elif tag in ("wellAlias", "wellboreAlias"):
                name = system = ""
                for node in child:
                    if _local_name(node.tag) == "name":
                        name = (node.text or "").strip()
                    elif _local_name(node.tag) == "namingSystem":
                        system = (node.text or "").strip()
                if name:
                    aliases.append((tag, system, name))
            elif tag == "rigAlias":
                name = next(
                    (n.text for n in child if _local_name(n.tag) == "name" and n.text), None
                )
                header["rig_alias"] = name.strip() if name else None
            elif tag == "activity":
                activities.append(child)

        for kind, system, name in aliases:
            upper = system.upper()
            if upper == "NPD NUMBER":
                header["npd_number"] = name
            elif upper == "NPD CODE" and kind == "wellAlias":
                header["npd_code_well"] = name
            elif upper == "NPD CODE" and kind == "wellboreAlias":
                header["npd_code_wellbore"] = name

        info = next((el for el in root.iter() if _local_name(el.tag) == "documentInfo"), None)
        if info is not None:
            for node in info:
                tag = _local_name(node.tag)
                if tag == "documentName":
                    header["document_name"] = (node.text or "").strip()
                elif tag == "owner":
                    header["document_owner"] = (node.text or "").strip()

        # The report's own date decides; the file name only nominated it.
        actual = _date_of(header["dtim_end"] or "") or report_date_from_name(path)
        if actual != replay_date:
            return
        header["report_date"] = actual.isoformat() if actual else None

        if not activities:
            # A report with no activity is still a report that exists on that
            # day. Emitting the header alone keeps the day countable.
            yield dict(header)
            return

        for sequence, activity in enumerate(activities, start=1):
            record = dict(header)
            record["activity_seq"] = str(sequence)
            for node in activity:
                tag = _local_name(node.tag)
                text = (node.text or "").strip() if node.text else None
                if tag == "dTimStart":
                    record["activity_dtim_start"] = text
                elif tag == "dTimEnd":
                    record["activity_dtim_end"] = text
                elif tag == "md":
                    record["activity_md"] = text
                    record["activity_md_uom"] = node.get("uom")
                elif tag == "phase":
                    record["phase"] = text
                elif tag == "proprietaryCode":
                    record["proprietary_code"] = text
                elif tag == "state":
                    record["state"] = text
                elif tag == "stateDetailActivity":
                    record["state_detail_activity"] = text
                elif tag == "comments":
                    record["comments"] = text
            yield record

    # -- HTML fallback ------------------------------------------------------

    def _read_html(self, path: Path, replay_date: date) -> Iterator[dict[str, str | None]]:
        """Fallback for a report with no XML form.

        Imported lazily: this path is expected to run zero times against this
        delivery, where every report has an XML sibling, and a missing optional
        dependency should not stop the XML path from working.
        """
        try:
            from selectolax.parser import HTMLParser
        except ImportError:  # pragma: no cover - selectolax is a declared dep
            return

        raw = path.read_bytes()
        tree = HTMLParser(raw.decode("utf-8", errors="replace"))
        header: dict[str, str | None] = {name: None for name in BUSINESS_COLUMNS}
        header["source_format"] = "html"
        header["report_date"] = replay_date.isoformat()

        # The HTML rendering is a table per section; identity sits in the first
        # cells that follow the labels the XML uses as element names.
        text_by_label: dict[str, str] = {}
        for row in tree.css("tr"):
            cells = [c.text(strip=True) for c in row.css("td, th")]
            if len(cells) >= 2 and cells[0]:
                text_by_label.setdefault(cells[0].rstrip(":").strip().lower(), cells[1])

        header["name_well"] = text_by_label.get("well")
        header["name_wellbore"] = text_by_label.get("wellbore")

        for sequence, row in enumerate(tree.css("tr"), start=1):
            cells = [c.text(strip=True) for c in row.css("td")]
            if len(cells) < 3:
                continue
            record = dict(header)
            record["activity_seq"] = str(sequence)
            record["comments"] = " | ".join(cells)
            yield record
