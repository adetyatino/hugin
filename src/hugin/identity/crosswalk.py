"""BR-12 — build ``silver.wellbore_identity`` from every identity in the data.

An identity is any string a source system used to say *which hole this is*: an
archive name, a folder name, a file name, an XML element, a spreadsheet column,
an Eclipse well name. This module collects all of them, resolves what it can,
and writes down what it cannot.

The order of authority is fixed, and it is the reason stage e exists in
:mod:`hugin.identity.normalize`:

1.  an official identifier (NPD number, W/B number, UUID) recorded next to the
    name by the system that wrote it,
2.  the name itself, put through stages a-d,
3.  nothing — the identity goes to ``wellbore_identity_unresolved`` with a
    reason, and is counted in the coverage report.

Why that order, concretely. Production data writes wellbore ``NO 15/9-F-4 AH``
and, in the same row, NPD code 5693, whose registered name is ``15/9-F-4``.
Reading the name alone invents a sidetrack ``AH`` that no register knows. The
identifier is authoritative, so it wins and the disagreement is reported rather
than smoothed over.

Nothing here deletes or guesses. Every distinct identity string that was seen
appears exactly once across the two output tables.

Outputs, all under ``data/_inventory/``:

    wellbore-identity.csv             the crosswalk (silver.wellbore_identity)
    wellbore-identity-unresolved.csv  what did not resolve, and why
    identity-crosswalk.json           counts and conflicts, for the report

Standard library only. The Excel workbook is read with ``zipfile`` plus
``ElementTree`` for two columns; see ADR 0001 before adding a dependency for it.
"""

from __future__ import annotations

import argparse
import collections
import csv
import datetime as _dt
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from hugin.identity.normalize import (
    Identifier,
    apply_field_prefix,
    classify_identifier,
    normalize,
    split_simulator_role,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
LANDING_DIR = DATA_DIR / "landing"
INVENTORY_DIR = DATA_DIR / "_inventory"
DOCS_DIR = REPO_ROOT / "docs"

NAME_MAPPING_PATH = INVENTORY_DIR / "name-mapping.csv"
IDENTITY_PATH = INVENTORY_DIR / "wellbore-identity.csv"
UNRESOLVED_PATH = INVENTORY_DIR / "wellbore-identity-unresolved.csv"
CROSSWALK_JSON = INVENTORY_DIR / "identity-crosswalk.json"

#: Curated mappings, if a human ever has to make a call the rules cannot.
#: Committed alongside the code so the decision is reviewable; empty today.
MANUAL_MAPPING_PATH = INVENTORY_DIR / "identity-manual-mapping.csv"

XLSX_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

#: WITSML labels a well's original hole "<well name> - Main Wellbore". The label
#: is a descriptor, not an identity, so the name does not normalise on its own.
#: Where the well is known, that wellbore is the well's own canonical wellbore.
MAIN_WELLBORE_SUFFIX = re.compile(r"^(?P<well>.+?)\s+-\s+Main Wellbore$", re.I)

CONF_IDENTIFIER = 1.0
CONF_EXACT = 1.0
CONF_NORMALIZED = 0.95
CONF_MAIN_WELLBORE = 0.90
CONF_MANUAL = 0.90
CONF_ASSUMED_FIELD_PREFIX = 0.70

#: How the assumed block is described in evidence text.
FIELD_PREFIX_LABEL = "15/9"


@dataclass
class Observation:
    """One identity string as one source system wrote it."""

    source_system: str
    source_identifier: str
    identity_kind: str
    context: str
    identifiers: tuple[tuple[str, str], ...] = ()
    operator_hint: str | None = None
    occurrences: int = 1
    note: str = ""
    #: True when this name is the *register's own name* for the identifier
    #: beside it, and may therefore teach the index what that identifier means.
    #: Production writes ``NO 15/9-F-11 H`` next to NPD code 7078, but 7078's
    #: registered name is ``15/9-F-11``, in the very next column. Letting the
    #: first teach the index would make the register agree with the operator's
    #: spelling and destroy the only independent check we have.
    defines_identifier: bool = False


#: Why an identity did not resolve. The category is what a reader acts on; the
#: reason text underneath it says which stage refused and why.
REASON_CATEGORIES = {
    "IDENTIFIER_WITHOUT_A_NAME": (
        "an official identifier that no source in this dataset ever paired with "
        "a name. The wellbore is real; nothing here says which one it is."
    ),
    "NOT_A_WELL_NAME": (
        "the string does not name a wellbore at all — a delivery folder, a "
        "planned location, a document title, or a placeholder value."
    ),
    "SUFFIX_NOT_A_SIDETRACK": (
        "a well name whose trailing text is not a sidetrack code. Resolving it "
        "needs an official identifier from the source, or a manual decision."
    ),
    "NEEDS_ASSUMED_BLOCK": (
        "resolvable only by assuming the block and quadrant the name omits, and "
        "no source that stated its own block knows the result."
    ),
}


def categorise_failure(observation: Observation, reason: str) -> str:
    """Group a refusal into something a reader can act on."""
    if observation.identifiers and classify_identifier(observation.source_identifier):
        return "IDENTIFIER_WITHOUT_A_NAME"
    if reason.startswith("unrecognised_suffix"):
        return "SUFFIX_NOT_A_SIDETRACK"
    if "assuming block" in reason:
        return "NEEDS_ASSUMED_BLOCK"
    return "NOT_A_WELL_NAME"


@dataclass
class NameReading:
    """What a written name resolves to on the name path alone."""

    wellbore_name: str | None = None
    method: str = ""
    confidence: float = 0.0
    evidence: str = ""
    failure: str | None = None


def read_name(text: str) -> NameReading:
    """Resolve one written name, including the descriptors WITSML appends.

    Used both to resolve an identity and to learn what an identifier names, so
    the two can never disagree about how a name is read.
    """
    parsed = normalize(text)
    if parsed.wellbore_name:
        exact = text == parsed.wellbore_name
        return NameReading(
            wellbore_name=parsed.wellbore_name,
            method="EXACT" if exact else "NORMALIZED",
            confidence=CONF_EXACT if exact else CONF_NORMALIZED,
            evidence=(
                "already canonical" if exact
                else f"stages a-d; decided at {parsed.decided_by}"
            ),
        )

    # WITSML names a well's original hole "<well> - Main Wellbore". The suffix
    # is a descriptor, not a sidetrack code, so the name cannot normalise on its
    # own. Note that the well part may itself carry a sidetrack letter: the
    # Statoil well master registers 15/9-F-15 A as a *well* with its own main
    # wellbore, where NPD registers it as a wellbore of well 15/9-F-15. Both
    # describe the same hole, and both land on the same wellbore_uid here.
    main = MAIN_WELLBORE_SUFFIX.match(text)
    if main:
        inner = normalize(main.group("well"))
        if inner.wellbore_name:
            return NameReading(
                wellbore_name=inner.wellbore_name, method="NORMALIZED",
                confidence=CONF_MAIN_WELLBORE,
                evidence=(
                    "WITSML 'Main Wellbore' descriptor: the original hole of "
                    f"well {inner.wellbore_name}"
                ),
            )

    return NameReading(failure=parsed.failure or "no_match")


@dataclass
class Resolution:
    wellbore_uid: str | None = None
    well_code: str | None = None
    sidetrack_code: str | None = None
    match_method: str = ""
    match_confidence: float = 0.0
    evidence: str = ""
    failure: str = ""


@dataclass
class IdentifierIndex:
    """Official identifier -> canonical wellbore name, with its provenance."""

    by_value: dict[tuple[str, str], str] = field(default_factory=dict)
    evidence: dict[tuple[str, str], str] = field(default_factory=dict)
    conflicts: list[dict] = field(default_factory=list)

    def add(self, ident: Identifier, wellbore_name: str, source: str) -> None:
        key = (ident.kind, ident.value)
        known = self.by_value.get(key)
        if known is None:
            self.by_value[key] = wellbore_name
            self.evidence[key] = source
        elif known != wellbore_name:
            # Never overwrite: a single identifier naming two wellbores is a
            # finding, not something to resolve by taking the last one seen.
            self.conflicts.append({
                "identifier": f"{ident.kind} {ident.value}",
                "first": known,
                "first_source": self.evidence[key],
                "second": wellbore_name,
                "second_source": source,
            })

    def lookup(self, identifiers: tuple[tuple[str, str], ...]) -> tuple[str | None, str]:
        for kind, value in identifiers:
            hit = self.by_value.get((kind, value))
            if hit:
                return hit, f"{kind} {value} (from {self.evidence[(kind, value)]})"
        return None, ""


# --------------------------------------------------------------------------
# Collection
# --------------------------------------------------------------------------

def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def read_mapping_rows() -> list[dict]:
    if not NAME_MAPPING_PATH.exists():
        raise SystemExit(
            f"{NAME_MAPPING_PATH} is missing. Run 'make extract' first — the "
            f"crosswalk reads the original names from it, not from disk."
        )
    with open(NAME_MAPPING_PATH, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def observe_archive_and_folder_names(rows: list[dict]) -> list[Observation]:
    """Archive names and the in-archive root folder names.

    Both are read from ``entry_path_original``, never from the landing path: the
    landing path holds a slug this pipeline invented, and BR-12 must see the
    name the source system wrote.
    """
    out: list[Observation] = []

    archives = collections.Counter(r["archive"] for r in rows)
    for archive, count in sorted(archives.items()):
        out.append(Observation(
            source_system="ARCHIVE", source_identifier=Path(archive).stem,
            identity_kind="ARCHIVE_NAME", context=archive, occurrences=count,
        ))

    roots: dict[tuple[str, str], int] = collections.Counter()
    for r in rows:
        first = r["entry_path_original"].replace("\\", "/").split("/")[0]
        roots[(r["source_code"], first)] += 1
    for (code, name), count in sorted(roots.items()):
        out.append(Observation(
            source_system=code, source_identifier=name,
            identity_kind="ARCHIVE_ROOT_FOLDER", context=f"{code} landing root",
            occurrences=count,
        ))
    return out


def observe_well_wellbore_folders(rows: list[dict]) -> list[Observation]:
    """The ``WellWellbore/<well>/<wellbore>/`` tree of the EDM export.

    Directory components only. ``WellWellbore/15_9-F-10/Well Summary F-10.pdf``
    puts a document at the well level, and a document title is not an identity
    the well was filed under — the folder above it already is.
    """
    out: dict[tuple[str, str], int] = collections.Counter()
    for r in rows:
        parts = r["entry_path_original"].replace("\\", "/").split("/")
        if len(parts) < 4 or parts[1] != "WellWellbore":
            continue
        out[("WELL_FOLDER", parts[2])] += 1
        if len(parts) >= 5:  # parts[3] is a directory, not the file itself
            out[("WELLBORE_FOLDER", parts[3])] += 1
    return [
        Observation(
            source_system="TRAJ", source_identifier=name, identity_kind=kind,
            context="Well_technical_data/WellWellbore", occurrences=count,
        )
        for (kind, name), count in sorted(out.items())
    ]


def observe_ddr_file_names(rows: list[dict]) -> list[Observation]:
    """Daily drilling report file names: ``15_9_F_15_D_2008_02_29.xml``."""
    stems: dict[str, int] = collections.Counter()
    for r in rows:
        if r["source_code"] != "DDR":
            continue
        stem = Path(r["entry_path_original"]).stem
        stem = re.sub(r"_\d{4}_\d{2}_\d{2}$", "", stem)
        if stem:
            stems[stem] += 1
    return [
        Observation(
            source_system="DDR", source_identifier=stem, identity_kind="FILE_NAME",
            context="Daily Drilling Report file names", occurrences=count,
        )
        for stem, count in sorted(stems.items())
    ]


def _xml_identity(path: Path) -> dict | None:
    """First identity-bearing element of a WITSML-family document."""
    holders = {
        "well", "wellbore", "message", "trajectory", "log", "bhaRun",
        "tubular", "rig", "wbGeometry", "mudLog", "drillReport",
    }
    attrs: dict[str, str] | None = None
    values: dict[str, str] = {}
    aliases: list[tuple[str, str, str]] = []
    tag_seen = ""
    try:
        for event, el in ET.iterparse(path, events=("start", "end")):
            tag = _local(el.tag)
            if event == "start" and attrs is None and tag in holders:
                attrs = {_local(k): v for k, v in el.attrib.items()}
                tag_seen = tag
            elif event == "end" and attrs is not None:
                if tag in ("nameWell", "nameWellbore") and tag not in values:
                    values[tag] = (el.text or "").strip()
                elif tag == "name" and "name" not in values and el.text:
                    values["name"] = el.text.strip()
                elif tag in ("wellAlias", "wellboreAlias"):
                    alias_name = alias_system = ""
                    for child in el:
                        if _local(child.tag) == "name":
                            alias_name = (child.text or "").strip()
                        elif _local(child.tag) == "namingSystem":
                            alias_system = (child.text or "").strip()
                    if alias_name:
                        aliases.append((tag, alias_system, alias_name))
                elif tag in ("commonData", "statusInfo"):
                    break
    except (ET.ParseError, OSError):
        return None
    if attrs is None:
        return None
    return {"tag": tag_seen, "attrs": attrs, "values": values, "aliases": aliases}


def observe_witsml_family_xml(source_system: str, root: Path) -> list[Observation]:
    """WITSML / EDM trajectory XML: names plus the uids written beside them."""
    seen: dict[tuple, int] = collections.Counter()
    context: dict[tuple, str] = {}
    for path in sorted(root.rglob("*.xml")):
        if not path.is_file():
            continue
        doc = _xml_identity(path)
        if doc is None:
            continue
        attrs, values = doc["attrs"], doc["values"]
        rel = str(path.relative_to(REPO_ROOT)).replace("\\", "/")

        uid_well = attrs.get("uidWell") or (attrs.get("uid") if doc["tag"] == "well" else "")
        uid_bore = attrs.get("uidWellbore") or (attrs.get("uid") if doc["tag"] == "wellbore" else "")
        name_well = values.get("nameWell") or (values.get("name", "") if doc["tag"] == "well" else "")
        name_bore = values.get("nameWellbore") or (
            values.get("name", "") if doc["tag"] == "wellbore" else ""
        )

        if name_well:
            key = ("WELL", name_well, uid_well)
            seen[key] += 1
            context.setdefault(key, rel)
        if name_bore:
            key = ("WELLBORE", name_bore, uid_bore)
            seen[key] += 1
            context.setdefault(key, rel)

    out: list[Observation] = []
    for (level, name, uid), count in sorted(seen.items()):
        ident = classify_identifier(uid) if uid else None
        out.append(Observation(
            source_system=source_system, source_identifier=name,
            identity_kind=f"XML_NAME_{level}", context=context[(level, name, uid)],
            identifiers=((ident.kind, ident.value),) if ident else (),
            occurrences=count,
            # The system that issued the uid also wrote this name for it.
            defines_identifier=bool(ident),
        ))
        if ident:
            out.append(Observation(
                source_system=source_system, source_identifier=ident.value,
                identity_kind=f"XML_UID_{level}", context=context[(level, name, uid)],
                identifiers=((ident.kind, ident.value),), occurrences=count,
            ))
    return out


def observe_ddr_xml(root: Path) -> list[Observation]:
    """Daily drilling reports carry the NPD register alias — the one national
    identifier in this dataset."""
    seen: dict[tuple, int] = collections.Counter()
    context: dict[tuple, str] = {}
    for path in sorted(root.rglob("*.xml")):
        if not path.is_file():
            continue
        doc = _xml_identity(path)
        if doc is None:
            continue
        rel = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        values, aliases = doc["values"], doc["aliases"]

        npd_number = next(
            (n for kind, system, n in aliases if system.upper() == "NPD NUMBER"), ""
        )
        bore_alias = next(
            (n for kind, system, n in aliases
             if kind == "wellboreAlias" and system.upper() == "NPD CODE"), ""
        )
        well_alias = next(
            (n for kind, system, n in aliases
             if kind == "wellAlias" and system.upper() == "NPD CODE"), ""
        )
        idents = tuple(
            (i.kind, i.value) for i in [classify_identifier(npd_number)] if i
        )

        for kind, name, attach in (
            ("XML_NAME_WELL", values.get("nameWell", ""), idents),
            ("XML_NAME_WELLBORE", values.get("nameWellbore", ""), ()),
            ("NPD_CODE_WELL", well_alias, idents),
            ("NPD_CODE_WELLBORE", bore_alias, ()),
            ("NPD_NUMBER", npd_number, idents),
        ):
            if not name:
                continue
            key = (kind, name, attach)
            seen[key] += 1
            context.setdefault(key, rel)

    return [
        Observation(
            source_system="DDR", source_identifier=name, identity_kind=kind,
            context=context[(kind, name, idents)], identifiers=idents, occurrences=count,
            # Only the alias the report itself labels "NPD code" is the NPD
            # register's name for that NPD number.
            defines_identifier=kind == "NPD_CODE_WELL",
        )
        for (kind, name, idents), count in sorted(seen.items())
    ]


def _xlsx_rows(path: Path, sheet: str):
    """Yield sheet rows as {column letter: value}. Two columns are all we want.

    ``.xlsx`` is a zip of XML parts: cell values that are strings are indices
    into a shared string table. Written out here rather than taken as a
    dependency — see ADR 0001.
    """
    with zipfile.ZipFile(path) as zf:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            shared = [
                "".join(t.text or "" for t in si.iter(f"{XLSX_NS}t"))
                for si in root.findall(f"{XLSX_NS}si")
            ]
        with zf.open(sheet) as handle:
            for _event, row in ET.iterparse(handle, events=("end",)):
                if row.tag != f"{XLSX_NS}row":
                    continue
                cells: dict[str, str | None] = {}
                for cell in row.findall(f"{XLSX_NS}c"):
                    column = "".join(c for c in cell.get("r", "") if c.isalpha())
                    value_el = cell.find(f"{XLSX_NS}v")
                    value = value_el.text if value_el is not None else None
                    if cell.get("t") == "s" and value is not None:
                        value = shared[int(value)]
                    cells[column] = value
                yield cells
                row.clear()


def observe_production_workbook(path: Path) -> list[Observation]:
    """Production data names each wellbore twice: as the operator writes it, and
    as NPD registers it, with the NPD code beside both."""
    if not path.exists():
        return []
    rel = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    seen: dict[tuple, int] = collections.Counter()

    for cells in _xlsx_rows(path, "xl/worksheets/sheet1.xml"):
        code, npd, npd_name = cells.get("B"), cells.get("C"), cells.get("D")
        if not code or code == "WELL_BORE_CODE":
            continue
        ident = classify_identifier(npd or "")
        idents = ((ident.kind, ident.value),) if ident else ()
        seen[("WELL_BORE_CODE", code, idents)] += 1
        if npd_name:
            seen[("NPD_WELL_BORE_NAME", npd_name, idents)] += 1
        if npd:
            seen[("NPD_WELL_BORE_CODE", npd, idents)] += 1

    for cells in _xlsx_rows(path, "xl/worksheets/sheet2.xml"):
        name, npd = cells.get("A"), cells.get("B")
        if not name or name == "Wellbore name":
            continue
        ident = classify_identifier(npd or "")
        idents = ((ident.kind, ident.value),) if ident else ()
        seen[("MONTHLY_WELLBORE_NAME", name, idents)] += 1

    return [
        Observation(
            source_system="PROD", source_identifier=name, identity_kind=kind,
            context=rel, identifiers=idents, occurrences=count,
            defines_identifier=kind in ("NPD_WELL_BORE_NAME", "MONTHLY_WELLBORE_NAME"),
        )
        for (kind, name, idents), count in sorted(seen.items())
    ]


def observe_las_headers(root: Path) -> list[Observation]:
    """LAS ``~WELL`` mnemonics. The messiest names in the dataset live here."""
    wanted = {"WELL", "UWI", "API"}
    seen: dict[tuple, int] = collections.Counter()
    context: dict[tuple, str] = {}

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() != ".las":
            continue
        rel = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        try:
            text = path.read_text(encoding="utf-8", errors="replace")[:8000]
        except OSError:
            continue
        section = ""
        operator = None
        header: list[tuple[str, str]] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("~"):
                section = stripped[1:2].upper()
                if section not in ("W", "V"):
                    break
                continue
            if section != "W" or not stripped or stripped.startswith("#") or "." not in stripped:
                continue
            mnemonic, rest = stripped.split(".", 1)
            mnemonic = mnemonic.strip().upper()
            body = rest.split(":", 1)[0]
            if not rest.startswith(" "):  # a unit is attached to the dot
                body = re.sub(r"^\S*\s", "", body, count=1)
            value = body.strip()
            if mnemonic == "COMP" and value:
                operator = value
            elif mnemonic in wanted and value:
                header.append((mnemonic, value))
        for mnemonic, value in header:
            key = (f"LAS_{mnemonic}", value, operator)
            seen[key] += 1
            context.setdefault(key, rel)

    return [
        Observation(
            source_system="LOG", source_identifier=value, identity_kind=kind,
            context=context[(kind, value, operator)], operator_hint=operator,
            occurrences=count,
        )
        for (kind, value, operator), count in sorted(
            seen.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2] or "")
        )
    ]


def observe_eclipse_welspecs(root: Path) -> list[Observation]:
    """Well names declared in Eclipse ``WELSPECS`` records.

    Only WELSPECS — the keyword that *defines* a well. Completion and rate
    keywords repeat the same names and would add nothing but noise.
    """
    seen: dict[str, int] = collections.Counter()
    context: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.upper() not in (".SCH", ".DATA", ".INC", ".ECL"):
            continue
        rel = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        in_section = False
        for line in text.splitlines():
            stripped = line.strip()
            if not in_section:
                if stripped.upper().startswith("WELSPECS"):
                    in_section = True
                continue
            if stripped.startswith("--") or not stripped:
                continue
            if stripped == "/":
                in_section = False
                continue
            match = re.match(r"^'([^']+)'", stripped)
            if match:
                name = match.group(1).strip()
                seen[name] += 1
                context.setdefault(name, rel)
    return [
        Observation(
            source_system="SIM", source_identifier=name, identity_kind="ECLIPSE_WELSPECS",
            context=context[name], occurrences=count,
        )
        for name, count in sorted(seen.items())
    ]


def collect_observations(rows: list[dict]) -> list[Observation]:
    observations: list[Observation] = []
    observations += observe_archive_and_folder_names(rows)
    observations += observe_well_wellbore_folders(rows)
    observations += observe_ddr_file_names(rows)
    observations += observe_witsml_family_xml("WITSML", LANDING_DIR / "witsml")
    observations += observe_witsml_family_xml("TRAJ", LANDING_DIR / "traj")
    observations += observe_ddr_xml(LANDING_DIR / "ddr")
    observations += observe_production_workbook(
        LANDING_DIR / "prod" / "Production_data" / "Volve production data.xlsx"
    )
    observations += observe_las_headers(LANDING_DIR / "log")
    observations += observe_las_headers(LANDING_DIR / "vsp")
    observations += observe_eclipse_welspecs(LANDING_DIR / "sim")
    return observations


# --------------------------------------------------------------------------
# Resolution
# --------------------------------------------------------------------------

def merge_observations(observations: list[Observation]) -> list[Observation]:
    """One row per (source_system, source_identifier), as BR-12 requires.

    The same name written in twenty files is one identity, not twenty. The
    identifiers and contexts seen alongside it are merged.
    """
    merged: dict[tuple[str, str], Observation] = {}
    for obs in observations:
        key = (obs.source_system, obs.source_identifier)
        if key not in merged:
            merged[key] = Observation(
                source_system=obs.source_system, source_identifier=obs.source_identifier,
                identity_kind=obs.identity_kind, context=obs.context,
                identifiers=obs.identifiers, operator_hint=obs.operator_hint,
                occurrences=obs.occurrences, defines_identifier=obs.defines_identifier,
            )
            continue
        existing = merged[key]
        existing.occurrences += obs.occurrences
        existing.identifiers = tuple(dict.fromkeys(existing.identifiers + obs.identifiers))
        if obs.identity_kind not in existing.identity_kind:
            existing.identity_kind += f"|{obs.identity_kind}"
        existing.operator_hint = existing.operator_hint or obs.operator_hint
        # One occurrence entitled to define the identifier is enough.
        existing.defines_identifier = existing.defines_identifier or obs.defines_identifier
    return sorted(merged.values(), key=lambda o: (o.source_system, o.source_identifier))


def build_identifier_index(observations: list[Observation]) -> IdentifierIndex:
    """Learn what each official identifier names, from sources entitled to say.

    Only observations flagged ``defines_identifier`` teach the index: a name is
    evidence about an identifier when it is that identifier's own registered
    name, not merely when it sits nearby.
    """
    index = IdentifierIndex()
    for obs in observations:
        if not obs.identifiers or not obs.defines_identifier:
            continue
        reading = read_name(obs.source_identifier)
        if reading.wellbore_name is None:
            continue
        for kind, value in obs.identifiers:
            index.add(
                Identifier(kind, value),  # type: ignore[arg-type]
                reading.wellbore_name,
                f"{obs.source_system} {obs.identity_kind} {obs.source_identifier!r}",
            )
    return index


def read_manual_mappings() -> dict[tuple[str, str], dict]:
    """Read the human-curated mappings, if any.

    The file leads with comment lines explaining what belongs in it, so they are
    stripped before the header is read rather than after: a commented first line
    would otherwise become the header and every column name with it.
    """
    if not MANUAL_MAPPING_PATH.exists():
        return {}
    with open(MANUAL_MAPPING_PATH, newline="", encoding="utf-8") as fh:
        lines = [line for line in fh if not line.lstrip().startswith("#")]
    return {
        (row["source_system"], row["source_identifier"]): row
        for row in csv.DictReader(lines)
        if row.get("source_system") and row.get("wellbore_uid")
    }


def resolve(
    observations: list[Observation],
    index: IdentifierIndex,
    manual: dict[tuple[str, str], dict] | None = None,
    corroborated: set[str] | None = None,
) -> dict[tuple[str, str], Resolution]:
    """Resolve every observation. Order of authority: manual, identifier, name.

    ``corroborated`` is the set of wellbore uids already established by sources
    that named their own block and quadrant. A name that only resolves because
    this module supplied the block (Eclipse well names) must appear in it, or it
    stays unresolved.
    """
    manual = manual or {}
    corroborated = corroborated if corroborated is not None else set()
    out: dict[tuple[str, str], Resolution] = {}

    for obs in observations:
        key = (obs.source_system, obs.source_identifier)

        if key in manual:
            row = manual[key]
            parsed = normalize(row["wellbore_uid"])
            out[key] = Resolution(
                wellbore_uid=row["wellbore_uid"], well_code=parsed.well_code,
                sidetrack_code=parsed.sidetrack_code, match_method="MANUAL",
                match_confidence=CONF_MANUAL,
                evidence=f"manual mapping: {row.get('reason', '')}",
            )
            continue

        by_identifier, identifier_evidence = index.lookup(obs.identifiers)
        reading = read_name(obs.source_identifier)
        by_name = reading.wellbore_name

        if by_identifier and by_name and by_identifier != by_name:
            resolved = normalize(by_identifier)
            out[key] = Resolution(
                wellbore_uid=by_identifier, well_code=resolved.well_code,
                sidetrack_code=resolved.sidetrack_code,
                match_method="IDENTIFIER", match_confidence=CONF_IDENTIFIER,
                evidence=(
                    f"{identifier_evidence}; overrules the name, which parses to "
                    f"{by_name!r}"
                ),
            )
            continue

        if by_name:
            resolved = normalize(by_name)
            out[key] = Resolution(
                wellbore_uid=by_name, well_code=resolved.well_code,
                sidetrack_code=resolved.sidetrack_code,
                match_method=reading.method, match_confidence=reading.confidence,
                evidence=reading.evidence
                + (f"; corroborated by {identifier_evidence}" if by_identifier else ""),
            )
            continue

        if by_identifier:
            resolved = normalize(by_identifier)
            out[key] = Resolution(
                wellbore_uid=by_identifier, well_code=resolved.well_code,
                sidetrack_code=resolved.sidetrack_code, match_method="IDENTIFIER",
                match_confidence=CONF_IDENTIFIER, evidence=identifier_evidence,
            )
            continue

        # Simulator names omit the block and may carry a role prefix instead
        # (P- for producer, I- for injector). Resolvable only where a source
        # that did name its own block already knows the wellbore.
        # Keyed on the kind, not the source system: the Eclipse delivery also
        # contributes an archive folder name, which is not a well name and must
        # not be explained as one.
        if "ECLIPSE_WELSPECS" in obs.identity_kind:
            out[key] = _resolve_simulator_name(obs.source_identifier, corroborated)
            continue

        out[key] = Resolution(match_method="", failure=reading.failure or "no_match")

    return out


def _resolve_simulator_name(name: str, corroborated: set[str]) -> Resolution:
    """Eclipse well name -> wellbore, but only with corroboration.

    ``P-F-14`` is a producer at F-14, and this is the only source in the dataset
    that names a well without saying which block it is in. Supplying the block
    is an assumption, so the result has to be confirmed by a source that stated
    its own block, and carries reduced confidence either way. ``I-F4G`` reads as
    ``15/9-F-4 G`` under the same assumption and nothing confirms it, so it stays
    unresolved rather than inventing a sidetrack.
    """
    role, remainder = split_simulator_role(name)
    reading = read_name(apply_field_prefix(remainder))
    described = f"simulator {role.lower()} name" if role else "simulator well name"

    if reading.wellbore_name and reading.wellbore_name in corroborated:
        resolved = normalize(reading.wellbore_name)
        return Resolution(
            wellbore_uid=reading.wellbore_name, well_code=resolved.well_code,
            sidetrack_code=resolved.sidetrack_code, match_method="NORMALIZED",
            match_confidence=CONF_ASSUMED_FIELD_PREFIX,
            evidence=(
                f"{described}; block {FIELD_PREFIX_LABEL} assumed because the name "
                f"omits it, then corroborated by a source that named its own block"
            ),
        )
    if reading.wellbore_name:
        return Resolution(match_method="", failure=(
            f"{described} normalises to {reading.wellbore_name!r} only after "
            f"assuming block {FIELD_PREFIX_LABEL}, and no source that names its "
            f"own block knows that wellbore"
        ))
    return Resolution(match_method="", failure=(
        f"{described}: {reading.failure or 'no well number'} even after assuming "
        f"block {FIELD_PREFIX_LABEL}"
    ))


def build_crosswalk() -> dict:
    """Collect, resolve, and return everything the outputs and report need."""
    rows = read_mapping_rows()
    observations = merge_observations(collect_observations(rows))
    index = build_identifier_index(observations)
    manual = read_manual_mappings()

    # Pass 1 establishes the wellbores that sources naming their own block know
    # about; pass 2 lets simulator names lean on that and nothing else.
    first = resolve(observations, index, manual, corroborated=set())
    corroborated = {r.wellbore_uid for r in first.values() if r.wellbore_uid}
    final = resolve(observations, index, manual, corroborated=corroborated)

    resolved_rows: list[dict] = []
    unresolved_rows: list[dict] = []
    for obs in observations:
        key = (obs.source_system, obs.source_identifier)
        res = final[key]
        parsed = normalize(obs.source_identifier)
        operator = parsed.operator_label or obs.operator_hint or ""
        common = {
            "source_system": obs.source_system,
            "source_identifier": obs.source_identifier,
            "identity_kind": obs.identity_kind,
            "occurrences": obs.occurrences,
            "first_seen_in": obs.context,
        }
        if res.wellbore_uid:
            resolved_rows.append({
                **common,
                "wellbore_uid": res.wellbore_uid,
                "well_code": res.well_code or "",
                "sidetrack_code": res.sidetrack_code or "",
                "operator_label": operator,
                "match_method": res.match_method,
                "match_confidence": f"{res.match_confidence:.2f}",
                "official_identifiers": ";".join(f"{k}:{v}" for k, v in obs.identifiers),
                "evidence": res.evidence,
            })
        else:
            reason = res.failure or "no_match"
            unresolved_rows.append({
                **common,
                "operator_label": operator,
                "official_identifiers": ";".join(f"{k}:{v}" for k, v in obs.identifiers),
                "reason_category": categorise_failure(obs, reason),
                "reason": reason,
            })

    resolved_rows.sort(key=lambda r: (r["wellbore_uid"], r["source_system"], r["source_identifier"]))
    unresolved_rows.sort(key=lambda r: (r["source_system"], r["source_identifier"]))

    return {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "identity_count": len(observations),
        "resolved": resolved_rows,
        "unresolved": unresolved_rows,
        "identifier_index": {
            f"{kind} {value}": name for (kind, value), name in sorted(index.by_value.items())
        },
        "identifier_conflicts": index.conflicts,
    }


# --------------------------------------------------------------------------
# Outputs
# --------------------------------------------------------------------------

RESOLVED_COLUMNS = [
    "source_system", "source_identifier", "wellbore_uid", "well_code",
    "sidetrack_code", "operator_label", "match_method", "match_confidence",
    "identity_kind", "occurrences", "official_identifiers", "evidence",
    "first_seen_in",
]
UNRESOLVED_COLUMNS = [
    "source_system", "source_identifier", "reason_category", "reason",
    "identity_kind", "occurrences", "operator_label", "official_identifiers",
    "first_seen_in",
]


def write_outputs(crosswalk: dict) -> None:
    INVENTORY_DIR.mkdir(parents=True, exist_ok=True)
    for path, columns, key in (
        (IDENTITY_PATH, RESOLVED_COLUMNS, "resolved"),
        (UNRESOLVED_PATH, UNRESOLVED_COLUMNS, "unresolved"),
    ):
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(crosswalk[key])
    CROSSWALK_JSON.write_text(
        json.dumps(crosswalk, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def write_report(crosswalk: dict) -> None:
    resolved, unresolved = crosswalk["resolved"], crosswalk["unresolved"]
    total = len(resolved) + len(unresolved)
    out: list[str] = []
    A = out.append

    A("# Identity resolution report (BR-12)")
    A("")
    A(f"Generated {crosswalk['generated_at']}.")
    A("")
    A("Every string any source system used to say *which hole this is* — archive")
    A("names, folder names, file names, XML elements, spreadsheet columns, Eclipse")
    A("well names. Each appears exactly once below, either resolved to a canonical")
    A("`wellbore_uid` or listed as unresolved with the reason. Nothing is dropped and")
    A("nothing is guessed.")
    A("")

    A("## 1. Coverage")
    A("")
    pct = (len(resolved) / total * 100) if total else 0.0
    A(f"- **{total}** distinct identities, over {len(_by(resolved, 'source_system')) } source systems")
    A(f"- **{len(resolved)} resolved** ({pct:.1f}%) to "
      f"**{len({r['wellbore_uid'] for r in resolved})}** distinct wellbores")
    A(f"- **{len(unresolved)} unresolved** ({100 - pct:.1f}%), listed in full in section 4")
    A("")

    A("### By match method")
    A("")
    A("| match_method | Identities | Confidence | What it means |")
    A("|---|---:|---:|---|")
    meanings = {
        "EXACT": "the source already wrote the canonical form",
        "IDENTIFIER": "an official identifier (NPD / W / UUID) decided it",
        "NORMALIZED": "stages a-d rewrote the name into canonical form",
        "MANUAL": "a human decision recorded in identity-manual-mapping.csv",
    }
    for method, rows in sorted(_by(resolved, "match_method").items()):
        confidences = sorted({r["match_confidence"] for r in rows})
        A(f"| `{method}` | {len(rows)} | {', '.join(confidences)} | {meanings.get(method, '')} |")
    A("")

    A("### By source system")
    A("")
    A("| source_system | Resolved | Unresolved | Wellbores reached |")
    A("|---|---:|---:|---:|")
    systems = sorted(
        {r["source_system"] for r in resolved} | {r["source_system"] for r in unresolved}
    )
    for system in systems:
        res = [r for r in resolved if r["source_system"] == system]
        unres = [r for r in unresolved if r["source_system"] == system]
        A(f"| `{system}` | {len(res)} | {len(unres)} | {len({r['wellbore_uid'] for r in res})} |")
    A("")

    A("## 2. The crosswalk")
    A("")
    A("`silver.wellbore_identity`, grouped by the wellbore each identity resolves to.")
    A("")
    for uid in sorted({r["wellbore_uid"] for r in resolved}):
        members = [r for r in resolved if r["wellbore_uid"] == uid]
        well = members[0]["well_code"]
        side = members[0]["sidetrack_code"]
        heading = f"### `{uid}`"
        A(heading)
        A("")
        A(f"well_code `{well}`"
          + (f", sidetrack_code `{side}`" if side else ", no sidetrack (original hole)")
          + f" — {len(members)} identities")
        A("")
        A("| source_system | source_identifier | match_method | conf. | seen | evidence |")
        A("|---|---|---|---:|---:|---|")
        for r in sorted(members, key=lambda r: (r["source_system"], r["source_identifier"])):
            A(f"| `{_cell(r['source_system'])}` | `{_cell(r['source_identifier'])}` "
              f"| {r['match_method']} | {r['match_confidence']} | {r['occurrences']} "
              f"| {_cell(r['evidence'])} |")
        A("")

    A("## 3. Official identifiers")
    A("")
    A("What each identifier was found to name, and where that was learnt.")
    A("")
    A("| Identifier | Names wellbore |")
    A("|---|---|")
    for ident, name in sorted(crosswalk["identifier_index"].items()):
        A(f"| `{ident}` | `{name}` |")
    A("")
    if crosswalk["identifier_conflicts"]:
        A("**Conflicts** — one identifier naming two wellbores. Not resolved here:")
        A("")
        for c in crosswalk["identifier_conflicts"]:
            A(f"- `{c['identifier']}`: `{c['first']}` (from {c['first_source']}) "
              f"vs `{c['second']}` (from {c['second_source']})")
        A("")
    else:
        A("No identifier was found naming two different wellbores.")
        A("")

    A("## 4. Unresolved")
    A("")
    A("`silver.wellbore_identity_unresolved`. These are kept, counted, and reported.")
    A("Guessing any of them would attribute data to the wrong hole, which is worse")
    A("than a gap because it looks like an answer.")
    A("")
    if not unresolved:
        A("Nothing unresolved.")
        A("")
    for category in sorted({r["reason_category"] for r in unresolved}):
        members = [r for r in unresolved if r["reason_category"] == category]
        A(f"### {category} — {len(members)}")
        A("")
        A(REASON_CATEGORIES.get(category, ""))
        A("")
        A("| source_system | source_identifier | seen | why |")
        A("|---|---|---:|---|")
        for r in members:
            A(f"| `{_cell(r['source_system'])}` | `{_cell(r['source_identifier'])}` "
              f"| {r['occurrences']} | {_cell(r['reason'])} |")
        A("")

    A("## 5. What would settle the unresolved ones")
    A("")
    counts = collections.Counter(r["reason_category"] for r in unresolved)
    A("| Category | Identities | Settled by |")
    A("|---|---:|---|")
    settled_by = {
        "IDENTIFIER_WITHOUT_A_NAME": (
            "a source that pairs the identifier with a name — the Sodir "
            "FactPages `REF` source would do it for NPD numbers"
        ),
        "NOT_A_WELL_NAME": (
            "nothing. These are not wellbores and should stay out of "
            "`dim_wellbore`; they are listed so the count is honest"
        ),
        "SUFFIX_NOT_A_SIDETRACK": "an official identifier, or a manual mapping",
        "NEEDS_ASSUMED_BLOCK": (
            "a manual mapping, if someone who knows the model can confirm it"
        ),
    }
    for category, count in sorted(counts.items()):
        A(f"| `{category}` | {count} | {settled_by.get(category, '')} |")
    A("")
    A("The procedure for adding a resolution by hand is to append a row to")
    A("`data/_inventory/identity-manual-mapping.csv` with a reason; it is read")
    A("ahead of every rule, and shows up as `match_method = MANUAL`.")
    A("")

    (DOCS_DIR / "identity-report.md").write_text("\n".join(out) + "\n", encoding="utf-8")


def _cell(text: str) -> str:
    """Escape a value for a markdown table cell.

    Merged identity kinds are joined with '|', which would otherwise open a new
    column and shear the table.
    """
    return str(text).replace("|", r"\|")


def _by(rows: list[dict], key: str) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = collections.defaultdict(list)
    for row in rows:
        out[row[key]].append(row)
    return dict(out)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m hugin.identity.crosswalk",
        description="BR-12: build silver.wellbore_identity from the landed data.",
    )
    parser.add_argument(
        "command", choices=("build", "report"),
        help="build: scan and write the crosswalk. report: rewrite docs from it.",
    )
    args = parser.parse_args(argv)

    if args.command == "build":
        crosswalk = build_crosswalk()
        write_outputs(crosswalk)
        print(f"identities        : {crosswalk['identity_count']}")
        print(f"resolved          : {len(crosswalk['resolved'])}")
        print(f"unresolved        : {len(crosswalk['unresolved'])}")
        print(f"distinct wellbores: {len({r['wellbore_uid'] for r in crosswalk['resolved']})}")
        print(f"wrote {IDENTITY_PATH.relative_to(REPO_ROOT)}")
        print(f"wrote {UNRESOLVED_PATH.relative_to(REPO_ROOT)}")
    else:
        crosswalk = json.loads(CROSSWALK_JSON.read_text(encoding="utf-8"))

    write_report(crosswalk)
    print(f"wrote {(DOCS_DIR / 'identity-report.md').relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
