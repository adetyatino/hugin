"""Factual inventory, duplicate detection and targeted extraction of the Volve archives.

This module deliberately contains no domain parsing and no data model. It only
looks at what the ZIP central directories say, decides where bytes should land,
and records every name it had to change.

Phases:
  A  inventory      read central directories, no extraction
  B  duplicates     group archives by content checksum
  C  classification assign source codes from evidence, not from file names
  D  extraction     targeted, idempotent, safe extraction into data/landing/
  E  report         docs/data-inventory.md and docs/data-dictionary.md

CLI:
  python -m hugin.ingestion.inventory scan
  python -m hugin.ingestion.inventory extract
  python -m hugin.ingestion.inventory report
"""

from __future__ import annotations

import argparse
import binascii
import collections
import csv
import ctypes
import datetime as _dt
import json
import os
import posixpath
import re
import shutil
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------
# Locations
# --------------------------------------------------------------------------

#: The archive folder is READ-ONLY. Nothing in this module ever opens it for
#: writing, renames anything inside it, or deletes from it.
DEFAULT_ARCHIVE_DIR = Path(r"C:\Apply Kerja\DE\volve")

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
INVENTORY_DIR = DATA_DIR / "_inventory"
LANDING_DIR = DATA_DIR / "landing"
DOCS_DIR = REPO_ROOT / "docs"
SOURCE_README_DIR = DOCS_DIR / "source-readme"

MANIFEST_PATH = INVENTORY_DIR / "archive-manifest.json"
DUPLICATES_PATH = INVENTORY_DIR / "duplicates.json"
DUPLICATE_LIST_PATH = INVENTORY_DIR / "duplicate-list.txt"
NAME_MAPPING_PATH = INVENTORY_DIR / "name-mapping.csv"

SAMPLE_ENTRY_COUNT = 20

# --------------------------------------------------------------------------
# Source codes
# --------------------------------------------------------------------------

SOURCE_CODES = {
    "PROD": "daily and monthly production per well (tabular)",
    "WITSML": "drilling telemetry (WITSML XML, or CSV when already parsed)",
    "LOG": "well logs (LAS and other log files)",
    "TRAJ": "directional surveys (EDT/EDM/Compass)",
    "DDR": "Daily Drilling Report (HTML, PDF, XML)",
    "GEOM": "geophysical interpretation (fault polygons, horizons, picks, perforations)",
    "SIM": "Eclipse simulation output (PRT and input decks)",
    "VSP": "checkshot / vertical seismic profile",
    "SEIS": "SEG-Y surface seismic",
    "DOC": "other documents and reports",
}

UNCLASSIFIED = "UNCLASSIFIED"

#: Landing sub-directory per source code. UNCLASSIFIED is handled separately.
LANDING_SUBDIR = {
    "PROD": "prod",
    "WITSML": "witsml",
    "LOG": "log",
    "TRAJ": "traj",
    "DDR": "ddr",
    "GEOM": "geom",
    "SIM": "sim",
    "VSP": "vsp",
    "SEIS": "seis",
    "DOC": "doc",
}

# --------------------------------------------------------------------------
# Windows path handling
# --------------------------------------------------------------------------

WINDOWS_INVALID_CHARS = ':*?"<>|'
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *{f"COM{i}" for i in range(1, 10)},
    *{f"LPT{i}" for i in range(1, 10)},
}


def long_paths_enabled() -> bool | None:
    """Read HKLM registry LongPathsEnabled. None when it cannot be read."""
    if os.name != "nt":
        return True
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\FileSystem",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "LongPathsEnabled")
            return bool(value)
    except OSError:
        return None


def extended_path(path: Path) -> str:
    r"""Return a string usable by the OS even when it exceeds MAX_PATH.

    Applies the \\?\ prefix on Windows for absolute paths that are long enough
    to matter. The prefix is harmless when long path support is already on.
    """
    if os.name != "nt":
        return str(path)
    text = str(path)
    if text.startswith("\\\\?\\"):
        return text
    if not os.path.isabs(text):
        return text
    if len(text) < 240:
        return text
    if text.startswith("\\\\"):
        return "\\\\?\\UNC\\" + text[2:]
    return "\\\\?\\" + text


def free_disk_bytes(path: Path) -> int:
    probe = path
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    if os.name == "nt":
        free = ctypes.c_ulonglong(0)
        ok = ctypes.windll.kernel32.GetDiskFreeSpaceExW(  # type: ignore[attr-defined]
            ctypes.c_wchar_p(str(probe)), None, None, ctypes.pointer(free)
        )
        if ok:
            return int(free.value)
    return shutil.disk_usage(str(probe)).free


# --------------------------------------------------------------------------
# Name handling
# --------------------------------------------------------------------------

def make_slug(source_name: str) -> str:
    """Filesystem-safe form of a source-given name.

    Rules fixed by the ingestion brief:
      - ``$47$`` encodes a forward slash in the source system; restore it as a
        hyphen, because a slash is not valid inside a directory name
      - spaces become underscores
      - everything else is kept as-is

    The slug exists only for the filesystem. The original name stays in the
    mapping table and is what identity resolution uses later.
    """
    slug = source_name.replace("_$47$_", "-").replace("$47$", "-")
    slug = slug.replace(" ", "_")
    return slug


def sanitize_component(component: str) -> tuple[str, list[str]]:
    """Make one path component valid on Windows. Returns (new, reasons)."""
    reasons: list[str] = []
    new = component

    bad = sorted({c for c in new if c in WINDOWS_INVALID_CHARS})
    if bad:
        for ch in WINDOWS_INVALID_CHARS:
            new = new.replace(ch, "_")
        reasons.append("invalid_windows_char:" + "".join(bad))

    ctrl = sorted({c for c in new if ord(c) < 32})
    if ctrl:
        new = "".join("_" if ord(c) < 32 else c for c in new)
        reasons.append("control_char:" + ",".join(str(ord(c)) for c in ctrl))

    stripped = new.rstrip(" .")
    if stripped != new:
        # Windows silently drops trailing dots and spaces; make it explicit.
        new = stripped + "_" if stripped else "_"
        reasons.append("trailing_dot_or_space")

    stem = new.split(".")[0].upper()
    if stem in WINDOWS_RESERVED_NAMES:
        new = new + "_"
        reasons.append(f"reserved_device_name:{stem}")

    if not new:
        new = "_"
        reasons.append("empty_component")

    return new, reasons


def sanitize_relative_path(rel_path: str) -> tuple[str, list[str], bool]:
    """Sanitize a zip entry path. Returns (safe_path, reasons, is_safe).

    ``is_safe`` is False when the entry escapes the destination directory after
    normalisation (path traversal), in which case the caller must refuse it.
    """
    reasons: list[str] = []
    raw = rel_path.replace("\\", "/")
    if raw != rel_path:
        reasons.append("backslash_to_slash")

    if raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        return "", ["absolute_path_rejected"], False

    parts: list[str] = []
    for part in raw.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            return "", ["path_traversal_rejected"], False
        clean, part_reasons = sanitize_component(part)
        reasons.extend(part_reasons)
        parts.append(clean)

    if not parts:
        return "", ["empty_path_rejected"], False

    return "/".join(parts), reasons, True


def normalize_entry_name(name: str, root_prefix: str) -> str:
    """Entry name normalised for content comparison across archives.

    The archive's own top-level folder is stripped, so two archives that hold
    the same payload under differently named roots still compare equal. Case and
    separators are normalised too.
    """
    n = name.replace("\\", "/")
    if root_prefix and n.startswith(root_prefix):
        n = n[len(root_prefix):]
    return n.strip("/").lower()


# --------------------------------------------------------------------------
# Phase A: inventory
# --------------------------------------------------------------------------

@dataclass
class EncodingNote:
    entry_as_read: str
    utf8_flag: bool
    as_utf8: str | None
    as_latin1: str | None
    differs: bool


@dataclass
class ArchiveScan:
    name: str
    path: str
    archive_size_bytes: int
    entry_count: int
    file_count: int
    dir_count: int
    implied_dir_count: int
    max_depth: int
    compressed_bytes: int
    uncompressed_bytes: int
    ext_counts: dict
    sample_entries: list
    longest_path_length: int
    longest_path: str
    utf8_flag_set_count: int
    utf8_flag_all_set: bool
    root_prefix: str
    encoding_notes: list = field(default_factory=list)
    content_checksum: str = ""
    raw_name_checksum: str = ""
    classification: dict = field(default_factory=dict)
    error: str | None = None


def _spread_sample(names: list[str], count: int) -> list[str]:
    """Pick ``count`` names spread across the list, not the first ``count``."""
    if len(names) <= count:
        return list(names)
    step = len(names) / count
    picked = [names[min(len(names) - 1, int(i * step))] for i in range(count)]
    # Deduplicate while preserving the spread order.
    seen: set[str] = set()
    out: list[str] = []
    for n in picked:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _detect_root_prefix(names: list[str]) -> str:
    """Return the single shared top-level folder, or '' when there isn't one."""
    tops = {n.replace("\\", "/").split("/")[0] for n in names if n.strip()}
    if len(tops) == 1:
        only = tops.pop()
        # Only a prefix if entries actually live below it.
        if any(n.replace("\\", "/").startswith(only + "/") for n in names):
            return only + "/"
    return ""


def _encoding_probe(info: zipfile.ZipInfo) -> EncodingNote | None:
    """Re-decode a non-UTF-8-flagged name and report every reading of it.

    ``zipfile`` decodes entry names as cp437 when the UTF-8 flag is clear. This
    dataset carries Scandinavian letters, so a name can be mangled. We recover
    the raw bytes and report the utf-8 and latin-1 readings alongside the cp437
    one instead of silently picking a winner.
    """
    utf8_flag = bool(info.flag_bits & 0x800)
    name = info.filename
    if utf8_flag:
        # Already decoded as UTF-8 by zipfile; nothing was guessed.
        if any(ord(c) > 127 for c in name):
            return EncodingNote(name, True, name, None, False)
        return None
    try:
        raw = name.encode("cp437")
    except UnicodeEncodeError:
        return None
    if all(b < 0x80 for b in raw):
        return None  # pure ASCII: every codec agrees

    try:
        as_utf8 = raw.decode("utf-8")
    except UnicodeDecodeError:
        as_utf8 = None
    as_latin1 = raw.decode("latin-1")
    differs = (as_utf8 is not None and as_utf8 != name) or (as_latin1 != name)
    return EncodingNote(name, False, as_utf8, as_latin1, differs)


def scan_archive(path: Path) -> ArchiveScan:
    """Phase A + the checksum half of Phase B, without extracting anything."""
    size = path.stat().st_size
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        return ArchiveScan(
            name=path.name, path=str(path), archive_size_bytes=size,
            entry_count=0, file_count=0, dir_count=0, implied_dir_count=0, max_depth=0,
            compressed_bytes=0, uncompressed_bytes=0, ext_counts={},
            sample_entries=[], longest_path_length=0, longest_path="",
            utf8_flag_set_count=0, utf8_flag_all_set=False, root_prefix="",
            error=f"{type(exc).__name__}: {exc}",
        )

    with zf:
        infos = zf.infolist()

    names = [i.filename for i in infos]
    root_prefix = _detect_root_prefix(names)

    ext_counts: collections.Counter = collections.Counter()
    file_count = dir_count = 0
    compressed = uncompressed = 0
    max_depth = 0
    longest = ""
    utf8_set = 0
    encoding_notes: list[EncodingNote] = []
    # Most archives here carry no explicit directory entries at all: the tree
    # exists only as slashes inside file names. Counting entries flagged as
    # directories would report "0 directories" for an archive five levels deep,
    # so the directories implied by the file paths are counted alongside.
    implied_dirs: set[str] = set()

    for info in infos:
        name = info.filename.replace("\\", "/")
        if info.flag_bits & 0x800:
            utf8_set += 1
        note = _encoding_probe(info)
        if note is not None:
            encoding_notes.append(note)

        depth = len([p for p in name.strip("/").split("/") if p])
        max_depth = max(max_depth, depth)
        if len(name) > len(longest):
            longest = name

        if info.is_dir():
            dir_count += 1
            implied_dirs.add(name.strip("/"))
            continue

        file_count += 1
        compressed += info.compress_size
        uncompressed += info.file_size
        ext = posixpath.splitext(name)[1].lower() or "<noext>"
        ext_counts[ext] += 1
        parent = posixpath.dirname(name.strip("/"))
        while parent:
            implied_dirs.add(parent)
            parent = posixpath.dirname(parent)

    # Content checksum: sorted (normalised name, uncompressed size, CRC32).
    # CRC32 is present in the central directory, so this costs no extraction.
    triples = sorted(
        (normalize_entry_name(i.filename, root_prefix), i.file_size, i.CRC)
        for i in infos
        if not i.is_dir()
    )
    payload = "\n".join(f"{n}|{s}|{c:08x}" for n, s, c in triples).encode("utf-8")
    content_checksum = f"{binascii.crc32(payload) & 0xFFFFFFFF:08x}-{len(triples)}"

    raw_triples = sorted(
        (i.filename.replace("\\", "/"), i.file_size, i.CRC)
        for i in infos
        if not i.is_dir()
    )
    raw_payload = "\n".join(f"{n}|{s}|{c:08x}" for n, s, c in raw_triples).encode("utf-8")
    raw_checksum = f"{binascii.crc32(raw_payload) & 0xFFFFFFFF:08x}-{len(raw_triples)}"

    file_names = [i.filename for i in infos if not i.is_dir()]

    return ArchiveScan(
        name=path.name,
        path=str(path),
        archive_size_bytes=size,
        entry_count=len(infos),
        file_count=file_count,
        dir_count=dir_count,
        implied_dir_count=len(implied_dirs),
        max_depth=max_depth,
        compressed_bytes=compressed,
        uncompressed_bytes=uncompressed,
        ext_counts=dict(ext_counts.most_common()),
        sample_entries=_spread_sample(sorted(file_names), SAMPLE_ENTRY_COUNT),
        longest_path_length=len(longest),
        longest_path=longest,
        utf8_flag_set_count=utf8_set,
        utf8_flag_all_set=bool(infos) and utf8_set == len(infos),
        root_prefix=root_prefix,
        encoding_notes=[vars(n) for n in encoding_notes],
        content_checksum=content_checksum,
        raw_name_checksum=raw_checksum,
    )


# --------------------------------------------------------------------------
# Phase C: evidence-based classification
# --------------------------------------------------------------------------

@dataclass
class Verdict:
    code: str
    evidence: list[str]
    confidence: str


def _pct(part: int, total: int) -> float:
    return 0.0 if not total else round(100.0 * part / total, 1)


def classify_entries(names: list[str]) -> Verdict:
    """Assign a source code from the content of a group of entry names.

    Scores are driven by extension mix, characteristic entry names and
    directory-structure patterns. Names are used as *evidence*, never as labels:
    a rule only fires on a structural pattern the source system itself created.
    """
    files = [n for n in names if not n.endswith("/")]
    total = len(files)
    if not total:
        return Verdict(UNCLASSIFIED, ["group contains no files"], "none")

    lower = [n.lower() for n in files]

    # A folder holding nothing but a placeholder is evidence of deliberate
    # ABSENCE. Classifying it from its directory name would invent a product
    # the source explicitly did not ship.
    placeholders = [n for n in lower if "left_intentionally_empty" in posixpath.basename(n)]
    if placeholders and len(placeholders) == total:
        return Verdict(
            UNCLASSIFIED,
            [
                f"all {total} entries are 'left_intentionally_empty' placeholders: "
                "the source shipped this folder deliberately empty, so there is no "
                "content to classify"
            ],
            "placeholder",
        )

    ext = collections.Counter(posixpath.splitext(n)[1].lower() or "<noext>" for n in lower)

    def ext_share(*exts: str) -> tuple[int, float]:
        c = sum(ext.get(e, 0) for e in exts)
        return c, _pct(c, total)

    def name_hits(pattern: str) -> tuple[int, float]:
        rx = re.compile(pattern)
        c = sum(1 for n in lower if rx.search(n))
        return c, _pct(c, total)

    scores: dict[str, float] = collections.defaultdict(float)
    evidence: dict[str, list[str]] = collections.defaultdict(list)

    def add(code: str, weight: float, text: str) -> None:
        scores[code] += weight
        evidence[code].append(text)

    # --- SIM: Eclipse decks and run output -------------------------------
    c, p = ext_share(".grdecl", ".data", ".sch", ".inc", ".incl", ".prt",
                     ".e100", ".eclrun", ".unrst", ".unsmry", ".msg", ".rsm")
    if c:
        add("SIM", p + 20, f"{p}% of entries carry Eclipse deck/output extensions ({c}/{total})")
    c, p = name_hits(r"eclipse|_sim_model|volve_20\d\d\.")
    if c:
        add("SIM", p, f"{p}% of entry names contain an Eclipse model marker ({c}/{total})")

    # --- DDR: the source system foldered these by report format ----------
    c, p = name_hits(r"daily drilling report")
    if c:
        add("DDR", p + 30, f"{p}% of entries sit under a 'Daily Drilling Report' folder ({c}/{total})")
    c, p = name_hits(r"/\d{2}_\d[^/]*_(19|20)\d\d_\d\d_\d\d\.(html|xml|pdf)$")
    if c:
        add("DDR", p, f"{p}% of entries use the per-well per-day report filename pattern ({c}/{total})")

    # --- VSP / SEIS ------------------------------------------------------
    c, p = ext_share(".segy", ".sgy")
    vsp_ctx, _ = name_hits(r"vsp|checkshot")
    if c and vsp_ctx:
        add("VSP", p + 25, f"{p}% SEG-Y entries, all under a VSP/checkshot path ({c}/{total})")
    elif c:
        add("SEIS", p + 25, f"{p}% of entries are SEG-Y outside any VSP context ({c}/{total})")
    c, p = name_hits(r"checkshot")
    if c:
        add("VSP", p + 10, f"{p}% of entry names contain 'checkshot' ({c}/{total})")

    # --- WITSML vs TRAJ: same archives, different subtrees ---------------
    c, p = name_hits(r"/trajectory/")
    if c:
        add("TRAJ", p + 25, f"{p}% of entries sit in a WITSML trajectory/ subtree ({c}/{total})")
    # WITSML 1.3/1.4 object type names, as created by the export tool itself.
    c, p = name_hits(
        r"/(log|message|_wellboreinfo|_wellinfo|mudlog|rig|bharun|tubular"
        r"|wbgeometry|opsreport|fluidsreport|cementjob|risk|surveyprogram"
        r"|convcore|sidewallcore|dtsinstalledsystem)/"
    )
    if c:
        add("WITSML", p + 20, f"{p}% of entries sit in WITSML object subtrees ({c}/{total})")
    c, p = name_hits(r"metafileinfo|metadatafileinfo")
    if c:
        add("WITSML", p + 10, f"{p}% of entries are WITSML export manifests ({c}/{total})")
    c, p = ext_share(".xml")
    if c and p > 50:
        add("WITSML", 5, f"{p}% of entries are XML ({c}/{total})")

    # --- TRAJ from the well-technical side (Compass / EDM) ---------------
    c, p = name_hits(r"compass|survey report|/edm\.xml|\.edt$|definitive survey")
    if c:
        add("TRAJ", p + 15, f"{p}% of entry names carry a Compass/EDM survey marker ({c}/{total})")
    # Compass names every exported wellpath by its status. The suffix is written
    # by the software, so it is a structural signal, not a guess from wording.
    # Without this the EDT/EDM export reads as DOC purely because it ships as PDF.
    c, p = name_hits(r"_(plan|prototype|actual|definitive)(\.[a-z0-9]+)?$")
    if c:
        add("TRAJ", p + 20, f"{p}% of entry names end in a Compass wellpath status "
                            f"(_PLAN/_PROTOTYPE/_ACTUAL/_DEFINITIVE) ({c}/{total})")

    # --- LOG -------------------------------------------------------------
    # .dex is deliberately absent: it is a biostratigraphy exchange file and only
    # ever turns up in 12.BIOSTRAT folders, which hold reports rather than logs.
    # Counting it as log evidence made those two-file folders flip between LOG
    # and DOC depending on whether one filename happened to contain "report".
    c, p = ext_share(".las", ".dlis", ".lis", ".asc", ".cgm", ".pds")
    if c:
        add("LOG", p + 10, f"{p}% of entries carry well-log extensions ({c}/{total})")
    # Deliberately NOT keyed on the `NN.` numbered-folder convention these
    # per-well archives use. That numbering describes how the delivery is
    # organised, not what is in it: 08.VSP_VELOCITY, 12.BIOSTRAT and
    # 14.DIV.REPORTS are all numbered folders holding entirely different data.
    # Scoring it as log evidence made every numbered folder look like a log.
    c, p = name_hits(r"wl_raw|wl_computed|wlc_|mud_log|lwd_")
    if c:
        add("LOG", p, f"{p}% of entry names use the wireline/LWD naming convention ({c}/{total})")

    # --- PROD ------------------------------------------------------------
    c, p = name_hits(r"production[ _]data|production_data")
    if c:
        add("PROD", p + 25, f"{p}% of entries sit under a production-data folder ({c}/{total})")

    # --- GEOM ------------------------------------------------------------
    c, p = name_hits(r"fault_|fault[- ]|horizon|well[ _]?pick|facies|_perf|-perf|top reservoir|top resevoir")
    if c:
        add("GEOM", p + 10, f"{p}% of entry names carry a fault/horizon/pick/perforation marker ({c}/{total})")

    # --- DOC -------------------------------------------------------------
    c, p = ext_share(".pdf", ".doc", ".docx", ".ppt", ".pptx")
    if c:
        add("DOC", p, f"{p}% of entries are documents ({c}/{total})")
    c, p = name_hits(r"report|discovery|pud|licen[cs]e")
    if c:
        add("DOC", p * 0.5, f"{p}% of entry names look like report/licence documents ({c}/{total})")

    if not scores:
        top_exts = ", ".join(f"{e} x{n}" for e, n in ext.most_common(5))
        return Verdict(
            UNCLASSIFIED,
            [f"no rule matched; extension mix is {top_exts}"],
            "none",
        )

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best, best_score = ranked[0]
    runner_up, runner_score = (ranked[1] if len(ranked) > 1 else (None, 0.0))

    ev = list(evidence[best])
    if best_score < 25:
        ev.append(f"weak evidence: top score {best_score:.0f} below threshold 25")
        return Verdict(UNCLASSIFIED, ev, "low")
    if runner_up and runner_score > 0 and best_score - runner_score < 8:
        ev.extend(evidence[runner_up])
        ev.append(
            f"conflicting evidence: {best} ({best_score:.0f}) vs "
            f"{runner_up} ({runner_score:.0f}) are within 8 points"
        )
        return Verdict(UNCLASSIFIED, ev, "conflicted")

    confidence = "high" if best_score >= 60 else "medium"
    if runner_up and runner_score >= 25:
        ev.append(f"secondary signal present: {runner_up} scored {runner_score:.0f}")
    return Verdict(best, ev, confidence)


MAX_SUBDIR_DEPTH = 3


def _split_by_component(names: list[str], root_prefix: str, depth: int) -> dict:
    """Group entries by their path component at ``depth`` below the archive root.

    Entries that have no component that deep are collected under ``.``.
    """
    groups: dict[str, list[str]] = collections.defaultdict(list)
    for n in names:
        rel = n[len(root_prefix):] if root_prefix and n.startswith(root_prefix) else n
        parts = [p for p in rel.replace("\\", "/").split("/") if p]
        # A component at this depth only exists if something lives below it.
        key = "/".join(parts[:depth]) if len(parts) > depth else "."
        groups[key].append(n)
    return groups


def _classify_subtree(names: list[str], root_prefix: str, depth: int) -> dict:
    """Classify subdirectories, descending only where the evidence is unclear.

    A single depth does not fit every archive. WITSML exports nest as
    ``<root>/1/trajectory/`` and ``<root>/1/log/``, so splitting at depth 1 folds
    surveys and telemetry into one group; the well-technical delivery separates
    cleanly at depth 1.

    So: split, then descend into a group when either
      * its own verdict was unclassified, or
      * the finer split disagrees with itself, i.e. the children carry two or
        more distinct codes. A group that is internally heterogeneous must be
        mapped per subdirectory even when a majority code would have won.

    The second condition is what keeps ``1/trajectory`` mapping to TRAJ in every
    WITSML archive rather than only in the ones where no code won outright.
    """
    result: dict[str, dict] = {}
    for key, members in sorted(_split_by_component(names, root_prefix, depth).items()):
        verdict = classify_entries(members)
        deeper = _split_by_component(members, root_prefix, depth + 1)
        splittable = (
            depth < MAX_SUBDIR_DEPTH
            and key != "."
            and len([k for k in deeper if k != "."]) > 1
        )
        if splittable:
            child = _classify_subtree(members, root_prefix, depth + 1)
            child_codes = {v["code"] for v in child.values()} - {UNCLASSIFIED}
            heterogeneous = len(child_codes) > 1
            resolved = verdict.code == UNCLASSIFIED and bool(child_codes)
            # A finer split must not leave more files unexplained than the
            # coarser one did. Without this, a confidently classified group can
            # shatter into dozens of tiny unclassified fragments, which is a
            # worse description of the data, not a more precise one.
            unclassified_before = len(members) if verdict.code == UNCLASSIFIED else 0
            unclassified_after = sum(
                v["file_count"] for v in child.values() if v["code"] == UNCLASSIFIED
            )
            if (heterogeneous or resolved) and unclassified_after <= unclassified_before:
                result.update(child)
                continue
        result[key] = {
            "code": verdict.code,
            "confidence": verdict.confidence,
            "evidence": verdict.evidence,
            "file_count": len(members),
            "depth": depth,
        }
    return result


def classify_archive(zip_path: Path, root_prefix: str) -> dict:
    """Classify an archive, splitting per subdirectory when it is mixed."""
    with zipfile.ZipFile(zip_path) as zf:
        names = [i.filename for i in zf.infolist() if not i.is_dir()]

    whole = classify_entries(names)
    per_subdir = _classify_subtree(names, root_prefix, 1)

    distinct = {g["code"] for g in per_subdir.values()}
    weighted = collections.Counter()
    for g in per_subdir.values():
        weighted[g["code"]] += g["file_count"]

    mixed = len(distinct - {UNCLASSIFIED}) > 1

    return {
        "archive_code": whole.code,
        "archive_confidence": whole.confidence,
        "archive_evidence": whole.evidence,
        "mixed": mixed,
        "codes_present": sorted(distinct),
        "file_counts_by_code": dict(weighted.most_common()),
        "per_subdir": per_subdir,
    }


def _matching_subdir_key(entry_name: str, scan: dict) -> str | None:
    """Longest per-subdir key that this entry lives under."""
    cls = scan["classification"]
    root_prefix = scan["root_prefix"]
    rel = (
        entry_name[len(root_prefix):]
        if root_prefix and entry_name.startswith(root_prefix)
        else entry_name
    )
    parts = [p for p in rel.replace("\\", "/").split("/") if p]
    for depth in range(min(len(parts) - 1, MAX_SUBDIR_DEPTH), 0, -1):
        key = "/".join(parts[:depth])
        if key in cls["per_subdir"]:
            return key
    return "." if "." in cls["per_subdir"] else None


def code_for_entry(entry_name: str, scan: dict) -> tuple[str, str]:
    """Resolve the source code for one entry. Returns (code, decided_by)."""
    cls = scan["classification"]
    key = _matching_subdir_key(entry_name, scan)
    sub = cls["per_subdir"].get(key) if key else None

    if cls["mixed"]:
        if sub:
            return sub["code"], f"subdir:{key}"
        return UNCLASSIFIED, f"subdir:{key}:unknown"
    if cls["archive_code"] != UNCLASSIFIED:
        return cls["archive_code"], "archive"
    if sub and sub["code"] != UNCLASSIFIED:
        return sub["code"], f"subdir:{key}"
    return UNCLASSIFIED, "archive"


# --------------------------------------------------------------------------
# Phase B: duplicate grouping
# --------------------------------------------------------------------------

def cross_archive_files(scans: list[dict], zip_paths: dict[str, Path]) -> dict:
    """Find files that appear in more than one archive, and say whether they agree.

    Archive-level checksums only catch whole archives that are copies of each
    other. Deliveries here overlap partially instead: the same survey ships both
    inside a per-well archive and inside a dedicated one. Comparing (basename,
    uncompressed size, CRC32) across archives shows where those overlaps agree
    byte for byte and, more usefully, where they do not.

    A pair with the same name and the same size but a different CRC is the
    interesting case: it cannot be explained by one copy being truncated, so it
    is either a re-processing or a corrupted copy, and it needs a human.
    """
    by_key: dict[tuple, list[dict]] = collections.defaultdict(list)
    for scan in scans:
        if scan.get("error"):
            continue
        path = zip_paths.get(scan["name"])
        if path is None:
            continue
        with zipfile.ZipFile(path) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                base = posixpath.basename(info.filename).lower()
                by_key[(base, info.file_size)].append({
                    "archive": scan["name"],
                    "entry": info.filename,
                    "crc": info.CRC,
                })

    agreeing = 0
    raw_conflicts: list[dict] = []
    pair_agree: collections.Counter = collections.Counter()
    pair_conflict: collections.Counter = collections.Counter()

    for (base, size), members in by_key.items():
        archives = sorted({m["archive"] for m in members})
        if len(archives) < 2:
            continue
        identical = len({m["crc"] for m in members}) == 1
        for i, a in enumerate(archives):
            for b in archives[i + 1:]:
                (pair_agree if identical else pair_conflict)[(a, b)] += 1
        if identical:
            agreeing += 1
        else:
            raw_conflicts.append({
                "basename": base,
                "size_bytes": size,
                "archives": archives,
                "copies": [
                    {"archive": m["archive"], "entry": m["entry"], "crc32": f"{m['crc']:08x}"}
                    for m in sorted(members, key=lambda m: m["archive"])
                ],
            })

    # A name clash across archives only means something if those archives
    # demonstrably share content elsewhere. Two WITSML exports of *different*
    # wellbores both contain 1.xml, 100.xml and MetaFileInfo.txt; identical
    # names of identical length there are coincidence, because a sequence number
    # carries no identity. Requiring corroborating agreement between the same
    # pair of archives separates a genuine byte conflict from that noise,
    # without hardcoding a list of filenames to ignore.
    MIN_AGREE = 3
    MIN_RATIO = 0.5

    def corroborated(conflict: dict) -> bool:
        archives = conflict["archives"]
        for i, a in enumerate(archives):
            for b in archives[i + 1:]:
                agree = pair_agree[(a, b)]
                clash = pair_conflict[(a, b)]
                if agree >= MIN_AGREE and agree / (agree + clash) >= MIN_RATIO:
                    return True
        return False

    conflicts = [c for c in raw_conflicts if corroborated(c)]
    coincidental = [c for c in raw_conflicts if not corroborated(c)]

    return {
        "method": (
            "files sharing a basename and uncompressed size across two or more "
            "archives, compared by CRC32 from the central directory. A CRC "
            "mismatch is only reported as a conflict when the same pair of "
            f"archives also agrees on at least {MIN_AGREE} other shared files "
            f"and on at least {int(MIN_RATIO * 100)}% of them; otherwise the "
            "shared name is treated as coincidence."
        ),
        "files_in_more_than_one_archive": agreeing + len(raw_conflicts),
        "identical_everywhere": agreeing,
        "same_name_same_size_different_crc": len(conflicts),
        "coincidental_name_collisions": len(coincidental),
        "coincidental_examples": sorted(
            {c["basename"] for c in coincidental}
        )[:10],
        "conflicts": sorted(conflicts, key=lambda c: c["basename"]),
        "overlapping_archive_pairs": [
            {
                "archives": list(pair),
                "identical_files": pair_agree[pair],
                "conflicting_files": pair_conflict[pair],
            }
            for pair in sorted(
                set(pair_agree) | set(pair_conflict),
                key=lambda p: -(pair_agree[p] + pair_conflict[p]),
            )[:15]
        ],
    }


def group_duplicates(scans: list[dict]) -> dict:
    by_checksum: dict[str, list[dict]] = collections.defaultdict(list)
    for s in scans:
        if s.get("error"):
            continue
        by_checksum[s["content_checksum"]].append(s)

    groups = []
    duplicate_names: list[str] = []
    for checksum, members in sorted(by_checksum.items()):
        if len(members) < 2:
            continue
        # Canonical = shortest name; ties broken alphabetically for determinism.
        ordered = sorted(members, key=lambda s: (len(s["name"]), s["name"]))
        canonical = ordered[0]["name"]
        dups = [m["name"] for m in ordered[1:]]
        duplicate_names.extend(dups)
        groups.append({
            "content_checksum": checksum,
            "file_count": ordered[0]["file_count"],
            "uncompressed_bytes": ordered[0]["uncompressed_bytes"],
            "canonical": canonical,
            "duplicates": dups,
            "members": [m["name"] for m in ordered],
            "raw_name_checksums": {m["name"]: m["raw_name_checksum"] for m in ordered},
            "note": (
                "identical payload under different archive root names"
                if len({m["raw_name_checksum"] for m in ordered}) > 1
                else "identical payload and identical entry paths"
            ),
        })

    return {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "comparison": (
            "crc32 of sorted (root-stripped lowercased entry name, uncompressed "
            "size, entry CRC32) triples read from the zip central directory"
        ),
        "group_count": len(groups),
        "duplicate_archive_count": len(duplicate_names),
        "policy": "duplicates are skipped during extraction and never deleted",
        "groups": groups,
        "duplicate_archives": sorted(duplicate_names),
    }


# --------------------------------------------------------------------------
# Phase D: extraction
# --------------------------------------------------------------------------

#: Matched against the entry's basename, anywhere within it. Producer-written
#: documentation does not always sit at the start of a filename: this dataset
#: ships `EDT_EDM_read_me.txt` and `read me.txt` alongside the plain
#: `README.txt`, and the first of those is the only description of the EDM
#: survey export anywhere in the delivery.
README_PATTERN = re.compile(r"read[\s_\-]?me|licen[cs]e|inventory|disclaimer", re.I)


@dataclass
class MappingRow:
    archive: str
    entry_path_original: str
    entry_path_extracted: str
    source_code: str
    rename_reason: str
    encoding_note: str


class DestinationRegistry:
    """Guarantees injectivity of destination paths on a case-insensitive FS."""

    def __init__(self) -> None:
        self._by_lower: dict[str, str] = {}

    def claim(self, dest_rel: str) -> tuple[str, str]:
        """Return (unique_dest_rel, reason). Reason is '' when unchanged.

        Called exactly once per archive entry, so a repeat claim always means a
        second, distinct entry wants a destination already taken. That includes
        the case where the two destinations are byte-identical because
        sanitisation collapsed different originals onto one name (``a:b`` and
        ``a*b`` both become ``a_b``). Treating that as "same entry" would map two
        originals onto one file and lose one of them, so every repeat is
        suffixed.
        """
        key = dest_rel.lower()
        if key not in self._by_lower:
            self._by_lower[key] = dest_rel
            return dest_rel, ""
        incumbent = self._by_lower[key]
        kind = (
            "sanitised_name_collision_with"
            if incumbent == dest_rel
            else "case_insensitive_collision_with"
        )
        stem, dot, ext = dest_rel.rpartition(".")
        counter = 1
        while True:
            candidate = (
                f"{stem}__{counter}.{ext}" if dot else f"{dest_rel}__{counter}"
            )
            ckey = candidate.lower()
            if ckey not in self._by_lower:
                self._by_lower[ckey] = candidate
                return candidate, f"{kind}:{incumbent}"
            counter += 1


def landing_root_for(code: str, scan: dict) -> Path:
    """Destination root for a source code within one archive.

    The two codes the brief spells out (``witsml``, ``log``) carry a ``<slug>``
    level derived from the source-given name. The same rule is applied to the
    other codes as well: several archives contribute to ``doc``, ``geom`` and
    ``traj``, so without that level their entry paths would collide. The slug is
    a filesystem artefact only; the original name is kept in name-mapping.csv.
    """
    if code == UNCLASSIFIED:
        return LANDING_DIR / "_unclassified" / make_slug(Path(scan["name"]).stem)
    source_name = scan["root_prefix"].rstrip("/") or Path(scan["name"]).stem
    return LANDING_DIR / LANDING_SUBDIR[code] / make_slug(source_name)


def _crc_of_file(path: Path, chunk: int = 1 << 20) -> int:
    crc = 0
    with open(extended_path(path), "rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            crc = binascii.crc32(block, crc)
    return crc & 0xFFFFFFFF


def _encoding_note_for(info: zipfile.ZipInfo) -> str:
    note = _encoding_probe(info)
    if note is None:
        return ""
    if note.utf8_flag:
        return "utf8_flag_set; name decoded as UTF-8 by the archive itself"
    parts = [f"utf8_flag_clear; cp437_reading={note.entry_as_read!r}"]
    if note.as_utf8 is not None and note.as_utf8 != note.entry_as_read:
        parts.append(f"utf8_reading={note.as_utf8!r}")
    if note.as_latin1 != note.entry_as_read:
        parts.append(f"latin1_reading={note.as_latin1!r}")
    return "; ".join(parts)


def extract_archives(
    archive_dir: Path,
    manifest: dict,
    duplicates: dict,
    verify_crc: bool = True,
    prune_orphans: bool = True,
) -> dict:
    dup_set = set(duplicates["duplicate_archives"])
    scans = [s for s in manifest["archives"] if not s.get("error")]

    total_uncompressed = sum(
        s["uncompressed_bytes"] for s in scans if s["name"] not in dup_set
    )
    free = free_disk_bytes(DATA_DIR)
    lp = long_paths_enabled()

    preflight = {
        "uncompressed_bytes_to_write": total_uncompressed,
        "free_disk_bytes": free,
        "sufficient_disk": free > total_uncompressed * 1.1,
        "long_paths_enabled": lp,
        "long_path_strategy": (
            "LongPathsEnabled=1; \\\\?\\ prefix still applied above 240 chars"
            if lp else "LongPathsEnabled off or unreadable; \\\\?\\ prefix applied"
        ),
        "archives_skipped_as_duplicate": sorted(dup_set),
    }
    print("--- extraction preflight ---")
    print(f"  to write        : {total_uncompressed / 1e9:.2f} GB uncompressed")
    print(f"  free disk       : {free / 1e9:.2f} GB")
    print(f"  sufficient      : {preflight['sufficient_disk']}")
    print(f"  LongPathsEnabled: {lp}")
    if not preflight["sufficient_disk"]:
        raise SystemExit("Refusing to extract: not enough free disk space.")

    registry = DestinationRegistry()
    rows: list[MappingRow] = []
    stats = collections.Counter()
    rejected: list[dict] = []
    readmes: list[dict] = []

    LANDING_DIR.mkdir(parents=True, exist_ok=True)
    SOURCE_README_DIR.mkdir(parents=True, exist_ok=True)

    for scan in scans:
        if scan["name"] in dup_set:
            stats["archives_skipped_duplicate"] += 1
            continue

        zip_path = archive_dir / scan["name"]
        print(f"  extracting {scan['name']} ...", flush=True)
        stats["archives_extracted"] += 1

        with zipfile.ZipFile(zip_path) as zf:
            for info in zf.infolist():
                original = info.filename
                code, _decided = code_for_entry(original, scan)
                root = landing_root_for(code, scan)
                root_prefix = scan["root_prefix"]
                rel_raw = (
                    original[len(root_prefix):]
                    if root_prefix and original.startswith(root_prefix)
                    else original
                )

                if info.is_dir() and not rel_raw.strip("/"):
                    # The archive's own root directory entry. Stripping the root
                    # prefix leaves nothing; it denotes the landing root itself.
                    Path(extended_path(root)).mkdir(parents=True, exist_ok=True)
                    stats["archive_root_dirs_created"] += 1
                    continue

                safe_rel, reasons, ok = sanitize_relative_path(rel_raw)
                if not ok:
                    rejected.append({
                        "archive": scan["name"],
                        "entry": original,
                        "reason": reasons[0] if reasons else "rejected",
                    })
                    stats["entries_rejected"] += 1
                    continue

                if info.is_dir():
                    # Empty directories are preserved as directories.
                    target = root / safe_rel
                    Path(extended_path(target)).mkdir(parents=True, exist_ok=True)
                    stats["dirs_created"] += 1
                    continue

                claim_key = f"{root.as_posix()}/{safe_rel}"
                unique_key, collision_reason = registry.claim(claim_key)
                if collision_reason:
                    reasons.append(collision_reason)
                    safe_rel = unique_key[len(root.as_posix()) + 1:]

                target = root / safe_rel
                Path(extended_path(target.parent)).mkdir(parents=True, exist_ok=True)

                needs_write = True
                if target.exists():
                    same_size = target.stat().st_size == info.file_size
                    if same_size and (not verify_crc or _crc_of_file(target) == info.CRC):
                        needs_write = False
                        stats["files_skipped_already_correct"] += 1

                if needs_write:
                    with zf.open(info) as src, open(extended_path(target), "wb") as dst:
                        shutil.copyfileobj(src, dst, 1 << 20)
                    stats["files_written"] += 1
                    if info.file_size == 0:
                        stats["zero_byte_files"] += 1

                if README_PATTERN.search(posixpath.basename(original)):
                    # Flatten the whole in-archive path into the copy's name, so
                    # two 'license.txt' files from different subdirectories of
                    # one archive cannot overwrite each other and the reader can
                    # still see where each came from.
                    flat, _r, _ok = sanitize_relative_path(rel_raw)
                    dest_name = f"{Path(scan['name']).stem}__{flat.replace('/', '__')}"
                    dest = SOURCE_README_DIR / dest_name
                    shutil.copyfile(extended_path(target), extended_path(dest))
                    readmes.append({
                        "archive": scan["name"],
                        "entry": original,
                        "copied_to": str(dest.relative_to(REPO_ROOT)).replace("\\", "/"),
                    })

                rows.append(MappingRow(
                    archive=scan["name"],
                    entry_path_original=original,
                    entry_path_extracted=str(
                        target.relative_to(REPO_ROOT)
                    ).replace("\\", "/"),
                    source_code=code,
                    rename_reason=";".join(dict.fromkeys(reasons)),
                    encoding_note=_encoding_note_for(info),
                ))
                stats["files_mapped"] += 1

    INVENTORY_DIR.mkdir(parents=True, exist_ok=True)
    with open(NAME_MAPPING_PATH, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "archive", "entry_path_original", "entry_path_extracted",
            "source_code", "rename_reason", "encoding_note",
        ])
        for r in sorted(rows, key=lambda r: (r.archive, r.entry_path_original)):
            writer.writerow([
                r.archive, r.entry_path_original, r.entry_path_extracted,
                r.source_code, r.rename_reason, r.encoding_note,
            ])

    # Orphans: files left in the landing tree by an earlier run that the current
    # mapping no longer produces, e.g. after a classification changed and an
    # entry moved to a different source code. The landing tree is derived output
    # and must be a pure function of the archives plus the manifest, so a stale
    # file is a defect. Nothing outside data/landing/ is ever touched, and the
    # read-only archive folder is not involved.
    expected = {r.entry_path_extracted for r in rows}
    orphans: list[str] = []
    if LANDING_DIR.exists():
        for path in LANDING_DIR.rglob("*"):
            if not path.is_file():
                continue
            rel = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
            if rel not in expected:
                orphans.append(rel)

    pruned: list[str] = []
    unprunable: list[dict] = []
    if orphans and prune_orphans:
        for rel in orphans:
            target = REPO_ROOT / rel
            if LANDING_DIR.resolve() not in target.resolve().parents:
                continue  # refuse to touch anything outside the landing tree
            try:
                os.remove(extended_path(target))
            except OSError as exc:
                # A file can be locked by another program (an open Excel
                # workbook leaves a ~$ lock file next to it). Report it and
                # carry on rather than aborting the whole extraction.
                unprunable.append({"path": rel, "error": f"{type(exc).__name__}: {exc}"})
                continue
            pruned.append(rel)
        stats["orphans_pruned"] = len(pruned)
        if unprunable:
            stats["orphans_locked"] = len(unprunable)
    elif orphans:
        stats["orphans_found_kept"] = len(orphans)

    result = {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "preflight": preflight,
        "stats": dict(sorted(stats.items())),
        "rejected_entries": rejected,
        "source_readmes": readmes,
        "orphans": orphans,
        "orphans_pruned": pruned,
        "orphans_unprunable": unprunable,
    }
    print("--- extraction stats ---")
    for k, v in result["stats"].items():
        print(f"  {k}: {v}")
    return result


# --------------------------------------------------------------------------
# Phase E: reporting helpers (format facts only, no domain interpretation)
# --------------------------------------------------------------------------

TEXT_EXTS = {".las", ".asc", ".txt", ".csv", ".prt", ".grdecl", ".inc", ".incl",
             ".sch", ".data", ".msg", ".rsm", ".html", ".xml", ".ecl", ".e100"}


def sniff_encoding(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig (BOM present)"
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16 (BOM present)"
    try:
        raw.decode("ascii")
        return "ascii"
    except UnicodeDecodeError:
        pass
    try:
        raw.decode("utf-8")
        return "utf-8 (no BOM)"
    except UnicodeDecodeError:
        return "not utf-8; cp1252/latin-1 readable"


def decode_best(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


DATE_PATTERNS = [
    (r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", "ISO 8601 date-time (YYYY-MM-DDThh:mm:ss)"),
    (r"\b\d{4}-\d{2}-\d{2}\b", "YYYY-MM-DD"),
    (r"\b\d{2}\.\d{2}\.\d{4}\b", "DD.MM.YYYY"),
    (r"\b\d{2}/\d{2}/\d{4}\b", "DD/MM/YYYY or MM/DD/YYYY (ambiguous)"),
    (r"\b\d{2}-[A-Z]{3}-\d{4}\b", "DD-MON-YYYY"),
    (r"\b\d{1,2} [A-Z]{3} \d{4}\b", "D MON YYYY"),
]

SENTINEL_PATTERNS = [
    (r"(?<![\d.])-999\.2500(?![\d])", "-999.2500"),
    (r"(?<![\d.])-999\.25(?![\d])", "-999.25"),
    (r"(?<![\d.])-999(?:\.0+)?(?![\d.])", "-999"),
    (r"(?<![\d.])-9999(?:\.0+)?(?![\d.])", "-9999"),
    (r"\bNULL\b", "NULL"),
    (r"\bNaN\b", "NaN"),
    (r"(?<![\d.])1E\+?30(?![\d])", "1E+30"),
]


def profile_text(path: Path, max_bytes: int = 240_000) -> dict:
    with open(extended_path(path), "rb") as fh:
        raw = fh.read(max_bytes)
    text = decode_best(raw)
    lines = text.splitlines()

    delim_counts = {
        "comma": sum(l.count(",") for l in lines[:200]),
        "semicolon": sum(l.count(";") for l in lines[:200]),
        "tab": sum(l.count("\t") for l in lines[:200]),
        "whitespace-aligned": sum(1 for l in lines[:200] if re.search(r"\S {2,}\S", l)),
    }
    delimiter = max(delim_counts, key=lambda k: delim_counts[k]) if any(delim_counts.values()) else "none detected"

    dates = [label for rx, label in DATE_PATTERNS if re.search(rx, text)]
    sentinels = [label for rx, label in SENTINEL_PATTERNS if re.search(rx, text)]
    non_ascii = sorted({c for c in text if ord(c) > 127})

    units: list[str] = []
    # LAS mnemonic.unit lines and WITSML uom attributes are declared in-file.
    units += re.findall(r"^\s*[A-Z0-9_]+\s*\.([A-Za-z0-9/%\-]+)\s", text, re.M)[:40]
    units += re.findall(r'uom="([^"]+)"', text)[:40]
    units += re.findall(r"^\s*(METRIC|FIELD|LAB)\s*$", text, re.M)[:5]

    header = ""
    for line in lines[:60]:
        if line.strip():
            header = line.strip()
            break

    return {
        "encoding": sniff_encoding(raw),
        "line_ending": "CRLF" if b"\r\n" in raw else ("LF" if b"\n" in raw else "none/one line"),
        "delimiter": delimiter,
        "delimiter_counts": delim_counts,
        "first_non_empty_line": header,
        "date_formats": dates,
        "sentinels": sentinels,
        "non_ascii_chars": non_ascii[:40],
        "units_declared": sorted(set(u for u in units if u))[:25],
        "line_count_sampled": len(lines),
    }


def head_lines(path: Path, n: int = 30) -> list[str]:
    with open(extended_path(path), "rb") as fh:
        raw = fh.read(200_000)
    return decode_best(raw).splitlines()[:n]


def hexdump(path: Path, n: int = 256) -> list[str]:
    with open(extended_path(path), "rb") as fh:
        raw = fh.read(n)
    out = []
    for off in range(0, len(raw), 16):
        chunk = raw[off:off + 16]
        hexpart = " ".join(f"{b:02x}" for b in chunk).ljust(47)
        asciipart = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        out.append(f"{off:08x}  {hexpart}  |{asciipart}|")
    return out


def xml_structure(path: Path, depth: int = 2) -> list[str]:
    """Element structure to two levels. Never dumps raw content."""
    import xml.etree.ElementTree as ET

    def local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1] if "}" in tag else tag

    try:
        with open(extended_path(path), "rb") as fh:
            raw = fh.read(3_000_000)
        root = ET.fromstring(raw)
    except (ET.ParseError, OSError) as exc:
        return [f"<could not parse: {type(exc).__name__}: {exc}>"]

    lines = [f"{local(root.tag)}   [attrs: {', '.join(root.attrib) or 'none'}]"]
    level1 = collections.Counter(local(c.tag) for c in root)
    for name, count in level1.items():
        first = next(c for c in root if local(c.tag) == name)
        lines.append(f"  {name} x{count}   [attrs: {', '.join(first.attrib) or 'none'}]")
        if depth > 1:
            level2 = collections.Counter(local(g.tag) for g in first)
            for gname, gcount in list(level2.items())[:12]:
                lines.append(f"    {gname} x{gcount}")
    return lines


# --------------------------------------------------------------------------
# CLI commands
# --------------------------------------------------------------------------

def _iter_archives(archive_dir: Path) -> list[Path]:
    return sorted(
        (p for p in archive_dir.iterdir() if p.is_file() and p.suffix.lower() == ".zip"),
        key=lambda p: p.name,
    )


def cmd_scan(args: argparse.Namespace) -> int:
    archive_dir = Path(args.archive_dir)
    archives = _iter_archives(archive_dir)
    print(f"Scanning {len(archives)} archives in {archive_dir} (no extraction)")

    scans = []
    for path in archives:
        scan = scan_archive(path)
        record = vars(scan)
        if not scan.error:
            record["classification"] = classify_archive(path, scan.root_prefix)
        print(
            f"  {scan.name}: {scan.entry_count} entries, "
            f"{scan.uncompressed_bytes / 1e6:.1f} MB uncompressed, "
            f"code={record.get('classification', {}).get('archive_code', 'ERROR')}"
        )
        scans.append(record)

    non_zip = sorted(
        p.name for p in archive_dir.iterdir()
        if p.is_file() and p.suffix.lower() != ".zip"
    )

    # Sibling folders that also hold archives. A second copy of the dataset next
    # door is a real hazard: it can drift out of step with this one and be picked
    # up as authoritative by mistake. Compared by filename only, which is cheap.
    our_names = {p.name for p in archives}
    siblings = []
    try:
        for sib in sorted(archive_dir.parent.iterdir()):
            if not sib.is_dir() or sib.resolve() == archive_dir.resolve():
                continue
            sib_names = {p.name for p in sib.iterdir() if p.is_file() and p.suffix.lower() == ".zip"}
            if not sib_names:
                continue
            siblings.append({
                "path": str(sib),
                "archive_count": len(sib_names),
                "shared_with_this_folder": len(our_names & sib_names),
                "only_here": sorted(our_names - sib_names),
                "only_there": sorted(sib_names - our_names),
            })
    except OSError:
        siblings = []

    manifest = {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "archive_dir": str(archive_dir),
        "archive_dir_is_read_only_by_policy": True,
        "archive_count": len(scans),
        "non_zip_files_present": non_zip,
        "sibling_archive_folders": siblings,
        "source_codes": SOURCE_CODES,
        "archives": scans,
    }

    INVENTORY_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {MANIFEST_PATH.relative_to(REPO_ROOT)}")

    duplicates = group_duplicates(scans)
    duplicates["cross_archive_files"] = cross_archive_files(
        scans, {p.name: p for p in archives}
    )
    DUPLICATES_PATH.write_text(json.dumps(duplicates, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"wrote {DUPLICATES_PATH.relative_to(REPO_ROOT)} "
        f"({duplicates['group_count']} duplicate groups, "
        f"{duplicates['duplicate_archive_count']} duplicate archives)"
    )

    if args.quarantine_duplicates:
        lines = [
            "# Archives whose content is byte-identical to a canonical archive.",
            "# This script never deletes anything. Review before acting.",
            "",
        ]
        for group in duplicates["groups"]:
            lines.append(f"# canonical: {group['canonical']}")
            for name in group["duplicates"]:
                lines.append(str(Path(args.archive_dir) / name))
            lines.append("")
        DUPLICATE_LIST_PATH.write_text("\n".join(lines), encoding="utf-8")
        print(f"wrote {DUPLICATE_LIST_PATH.relative_to(REPO_ROOT)}")

    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    if not MANIFEST_PATH.exists():
        raise SystemExit("Run 'scan' first: archive-manifest.json is missing.")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    duplicates = json.loads(DUPLICATES_PATH.read_text(encoding="utf-8"))
    result = extract_archives(
        Path(args.archive_dir), manifest, duplicates,
        verify_crc=not args.no_crc,
        prune_orphans=not args.keep_orphans,
    )
    (INVENTORY_DIR / "extraction-report.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"wrote {NAME_MAPPING_PATH.relative_to(REPO_ROOT)}")
    return 0


def _human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024.0
    return str(n)


def _representative_files(rows: list[dict]) -> dict:
    """One representative extracted file per source code, preferring a
    format that shows the most about the code."""
    preferred = {
        "PROD": [".xlsx", ".csv", ".txt"],
        "WITSML": [".xml"],
        "LOG": [".las", ".asc", ".dlis"],
        "TRAJ": [".xml", ".txt"],
        "DDR": [".xml", ".html", ".pdf"],
        "GEOM": [".grdecl", ".xlsx", ".las"],
        "SIM": [".prt", ".data", ".grdecl", ".sch"],
        "VSP": [".txt", ".asc", ".segy"],
        "SEIS": [".segy"],
        "DOC": [".pdf", ".txt"],
    }
    by_code: dict[str, list[dict]] = collections.defaultdict(list)
    for r in rows:
        by_code[r["source_code"]].append(r)

    chosen: dict[str, dict] = {}
    for code, members in by_code.items():
        order = preferred.get(code, [])
        def rank(row: dict) -> tuple:
            ext = posixpath.splitext(row["entry_path_extracted"])[1].lower()
            idx = order.index(ext) if ext in order else len(order)
            return (idx, len(row["entry_path_extracted"]))
        best = sorted(members, key=rank)[0]
        chosen[code] = best
    return chosen


def cmd_report(args: argparse.Namespace) -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    duplicates = json.loads(DUPLICATES_PATH.read_text(encoding="utf-8"))
    extraction = {}
    ext_report = INVENTORY_DIR / "extraction-report.json"
    if ext_report.exists():
        extraction = json.loads(ext_report.read_text(encoding="utf-8"))

    rows: list[dict] = []
    if NAME_MAPPING_PATH.exists():
        with open(NAME_MAPPING_PATH, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))

    write_inventory_doc(manifest, duplicates, extraction, rows)
    write_dictionary_doc(manifest, rows)
    print(f"wrote {(DOCS_DIR / 'data-inventory.md').relative_to(REPO_ROOT)}")
    print(f"wrote {(DOCS_DIR / 'data-dictionary.md').relative_to(REPO_ROOT)}")
    return 0


def write_inventory_doc(manifest: dict, duplicates: dict, extraction: dict, rows: list[dict]) -> None:
    dup_set = set(duplicates["duplicate_archives"])
    out: list[str] = []
    A = out.append

    A("# Volve archive inventory")
    A("")
    A(f"Generated {manifest['generated_at']} from `{manifest['archive_dir']}`.")
    A("")
    A("The archive folder is read-only by policy: nothing in it was written, renamed,")
    A("moved or deleted. Every output lives in this repository.")
    A("")
    A("Folder and file names inside the archives are treated as **data**, not labels.")
    A("Every name this pipeline had to change is recorded in")
    A("`data/_inventory/name-mapping.csv` with its original alongside it.")
    A("")

    # 1. Summary table
    A("## 1. Archive summary")
    A("")
    A("| Archive | Source code | Entries | Dominant ext | Compressed | Uncompressed | Status |")
    A("|---|---|---:|---|---:|---:|---|")
    for s in manifest["archives"]:
        if s.get("error"):
            A(f"| `{s['name']}` | ERROR | – | – | {_human(s['archive_size_bytes'])} | – | unreadable: {s['error']} |")
            continue
        cls = s["classification"]
        code = (
            "MIXED: " + ", ".join(c for c in cls["codes_present"] if c != UNCLASSIFIED)
            if cls["mixed"] else cls["archive_code"]
        )
        dom = next(iter(s["ext_counts"]), "–")
        dom_n = s["ext_counts"].get(dom, 0)
        if s["name"] in dup_set:
            status = "skipped (duplicate)"
        elif cls["archive_code"] == UNCLASSIFIED and not cls["mixed"]:
            status = "extracted to `_unclassified/`"
        else:
            status = "extracted"
        A(
            f"| `{s['name']}` | {code} | {s['entry_count']} | "
            f"`{dom}` ({_pct(dom_n, s['file_count'])}%) | "
            f"{_human(s['compressed_bytes'])} | {_human(s['uncompressed_bytes'])} | {status} |"
        )
    A("")

    A("### Structural facts")
    A("")
    A("Directory counts are given twice on purpose. Most of these archives carry no")
    A("directory entries at all — the tree exists only as slashes inside file names —")
    A("so the first column reads 0 for an archive that is plainly five levels deep.")
    A("The second column counts the directories those file paths imply.")
    A("")
    A("| Archive | Dir entries | Dirs implied by paths | Max depth | Longest path | UTF-8 flag |")
    A("|---|---:|---:|---:|---:|---|")
    for s in manifest["archives"]:
        if s.get("error"):
            continue
        if s["utf8_flag_all_set"]:
            flag = "all entries"
        elif s["utf8_flag_set_count"] == 0:
            flag = "no entries (cp437)"
        else:
            flag = f"{s['utf8_flag_set_count']} of {s['entry_count']} entries"
        A(
            f"| `{s['name']}` | {s['dir_count']} | {s.get('implied_dir_count', '–')} | "
            f"{s['max_depth']} | {s['longest_path_length']} chars | {flag} |"
        )
    A("")

    A("### Per-subdirectory codes for mixed archives")
    A("")
    any_mixed = False
    for s in manifest["archives"]:
        if s.get("error") or not s["classification"]["mixed"]:
            continue
        any_mixed = True
        A(f"**`{s['name']}`**")
        A("")
        A("| Subdirectory | Code | Files | Confidence | Leading evidence |")
        A("|---|---|---:|---|---|")
        for key, sub in s["classification"]["per_subdir"].items():
            ev = sub["evidence"][0] if sub["evidence"] else "–"
            A(f"| `{key}` | {sub['code']} | {sub['file_count']} | {sub['confidence']} | {ev} |")
        A("")
    if not any_mixed:
        A("No archive required per-subdirectory mapping.")
        A("")

    A("### Classification evidence, per archive")
    A("")
    for s in manifest["archives"]:
        if s.get("error"):
            continue
        cls = s["classification"]
        A(f"- **`{s['name']}`** → `{cls['archive_code']}` (confidence: {cls['archive_confidence']})")
        for ev in cls["archive_evidence"]:
            A(f"  - {ev}")
    A("")

    # 2. Duplicates
    A("## 2. Duplicate groups")
    A("")
    A(f"Comparison method: {duplicates['comparison']}.")
    A("Archives are compared by **content, never by name**. Duplicates are skipped")
    A("during extraction and are never deleted.")
    A("")
    if not duplicates["groups"]:
        A("**No duplicate groups were found.** All "
          f"{manifest['archive_count']} archives have distinct content checksums.")
        A("")
        A("This is worth stating explicitly, because the brief expected duplicates from")
        A("double downloads and `(1)`-suffixed names. Neither is present in this folder:")
        A("no filename carries a `(1)` suffix, and no two archives share a payload.")
    else:
        for g in duplicates["groups"]:
            A(f"- checksum `{g['content_checksum']}` — {g['file_count']} files, {_human(g['uncompressed_bytes'])}")
            A(f"  - canonical (shortest name): `{g['canonical']}`")
            for d in g["duplicates"]:
                A(f"  - duplicate: `{d}`")
            A(f"  - note: {g['note']}")
    A("")

    # 3. Unclassified
    A("## 3. Unclassified archives and subdirectories")
    A("")
    found_unc = False
    for s in manifest["archives"]:
        if s.get("error"):
            continue
        cls = s["classification"]
        if cls["archive_code"] == UNCLASSIFIED and not cls["mixed"]:
            found_unc = True
            A(f"- **`{s['name']}`** → `UNCLASSIFIED` (confidence: {cls['archive_confidence']})")
            for ev in cls["archive_evidence"]:
                A(f"  - {ev}")
        for key, sub in cls["per_subdir"].items():
            if sub["code"] == UNCLASSIFIED:
                found_unc = True
                A(f"- **`{s['name']}` → `{key}/`** → `UNCLASSIFIED` ({sub['file_count']} files, confidence: {sub['confidence']})")
                for ev in sub["evidence"]:
                    A(f"  - {ev}")
    if not found_unc:
        A("Nothing was left unclassified.")
    A("")

    # 4. Representative files
    A("## 4. Representative file per source code")
    A("")
    reps = _representative_files(rows)
    for code in sorted(SOURCE_CODES):
        A(f"### {code} — {SOURCE_CODES[code]}")
        A("")
        rep = reps.get(code)
        if rep is None:
            A("_No file in this dataset carries this code. See section 6._")
            A("")
            continue
        path = REPO_ROOT / rep["entry_path_extracted"]
        A(f"- Original entry: `{rep['entry_path_original']}`")
        A(f"- Archive: `{rep['archive']}`")
        A(f"- Extracted to: `{rep['entry_path_extracted']}`")
        if not path.exists():
            A("")
            A("_File not present on disk; run `extract` first._")
            A("")
            continue
        A(f"- Size on disk: {_human(path.stat().st_size)}")
        A("")
        ext = path.suffix.lower()
        if ext == ".xml":
            A("Element structure, two levels deep (not raw content):")
            A("")
            A("```")
            out.extend(xml_structure(path))
            A("```")
        elif ext in TEXT_EXTS:
            A("First 30 lines:")
            A("")
            A("```")
            out.extend(head_lines(path, 30))
            A("```")
        else:
            A(f"Binary format (`{ext}`) — hexdump of the first 256 bytes:")
            A("")
            A("```")
            out.extend(hexdump(path, 256))
            A("```")
        A("")

    # 5. Findings
    A("## 5. Temuan yang perlu tindak lanjut")
    A("")
    for line in _findings(manifest, duplicates, extraction, rows):
        A(line)
    A("")

    # 6. Missing sources
    A("## 6. Sumber yang belum tersedia")
    A("")
    present = {r["source_code"] for r in rows}
    missing = [c for c in SOURCE_CODES if c not in present]
    if missing:
        A("These source codes are defined by the ingestion brief but **no archive in")
        A("this folder produces a single file under them**:")
        A("")
        for c in missing:
            A(f"- **{c}** — {SOURCE_CODES[c]}")
        A("")
    else:
        A("Every defined source code is represented by at least one extracted file.")
        A("")
    A("Counts of extracted files per code:")
    A("")
    A("| Code | Files extracted |")
    A("|---|---:|")
    counts = collections.Counter(r["source_code"] for r in rows)
    for code, n in counts.most_common():
        A(f"| {code} | {n} |")
    A("")

    (DOCS_DIR).mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "data-inventory.md").write_text("\n".join(out) + "\n", encoding="utf-8")


def _findings(manifest: dict, duplicates: dict, extraction: dict, rows: list[dict]) -> list[str]:
    """Things that did not match the brief's expectations, recorded as-is."""
    F: list[str] = []
    A = F.append

    EXPECTED_ARCHIVES = 24  # the count stated in the ingestion brief
    n_arch = manifest["archive_count"]
    non_zip = ", ".join("`" + n + "`" for n in manifest["non_zip_files_present"]) or "none"
    if n_arch == EXPECTED_ARCHIVES:
        A(f"1. **The folder holds {n_arch} archives, matching the brief.** An earlier run")
        A("   of this tool found only 20 and recorded the shortfall; the four remaining")
        A("   downloads have since landed and are included here. Alongside them sits one")
        A(f"   non-zip file ({non_zip}), a licence/terms")
        A("   PDF loose beside the archives rather than inside one.")
    else:
        A(f"1. **The folder holds {n_arch} archives, not {EXPECTED_ARCHIVES}.** The brief")
        A(f"   expects {EXPECTED_ARCHIVES} `.zip` files. {n_arch} are present, plus one")
        A(f"   non-zip file ({non_zip}), which is a licence/terms PDF sitting loose")
        A("   beside the archives rather than inside one. The missing archives were not")
        A("   silently substituted; if a download is still in flight, re-run `make")
        A("   inventory` once it completes.")
    A("")

    # Archives whose names point at the same wellbore but whose content differs.
    # Derived, not hardcoded: the well token is the tail of the archive stem
    # after the last recognisable well separator.
    by_well: dict[str, list[dict]] = collections.defaultdict(list)
    for s in manifest["archives"]:
        if s.get("error"):
            continue
        stem = Path(s["name"]).stem
        m = re.search(r"(\d+)[_$47$]*[_\-]?9-?F-?\s?(\d+\s?[A-Z]?)$", stem)
        if m:
            by_well[f"F-{m.group(2).replace(' ', '')}"].append(s)
    lookalikes = {
        well: sorted(members, key=lambda s: s["file_count"])
        for well, members in by_well.items()
        if len(members) > 1
        and len({s["content_checksum"] for s in members}) == len(members)
    }

    if not duplicates["groups"]:
        A("2. **No duplicate archives exist.** The brief anticipated double downloads and")
        A("   `(1)`-suffixed names. Content checksums are all distinct and no filename")
        A("   carries a `(1)` suffix.")
        if lookalikes:
            A("")
            A(f"   {len(lookalikes)} sets of archives *name* the same wellbore while holding")
            A("   different content. They are deliberately all kept:")
            A("")
            for well, members in sorted(lookalikes.items()):
                sizes = " vs ".join(
                    f"`{s['name']}` ({s['file_count']} files)" for s in members
                )
                A(f"   - **{well}**: {sizes}")
            A("")
            A("   In each set the larger archive is a different, much fuller export of the")
            A("   same wellbore, not a second copy of the smaller one. Comparing by name")
            A("   alone would have discarded real data here.")
    else:
        A(f"2. **{duplicates['group_count']} duplicate group(s) found**; see section 2.")
    A("")

    siblings = manifest.get("sibling_archive_folders", [])
    if siblings:
        A("3. **A second copy of the dataset sits next to this one, and it is now out of")
        A("   date.**")
        for sib in siblings:
            A("")
            A(f"   `{sib['path']}` holds {sib['archive_count']} archives, "
              f"{sib['shared_with_this_folder']} of which share a filename with this folder.")
            if sib["only_here"]:
                A(f"   Missing from it ({len(sib['only_here'])}): "
                  + ", ".join("`" + n + "`" for n in sib["only_here"]) + ".")
            if sib["only_there"]:
                A(f"   Present only there ({len(sib['only_there'])}): "
                  + ", ".join("`" + n + "`" for n in sib["only_there"]) + ".")
        A("")
        A("   Only the folder named in the brief was scanned. The divergence is the")
        A("   point: an earlier run of this tool saw both folders holding the same 20")
        A("   archives, and the four newer downloads landed in this one alone. Anything")
        A("   reading the other folder is now working from a stale subset. Comparison is")
        A("   by filename only — no content checksum was taken across folders.")
    else:
        A("3. **No sibling folder holds a second copy of the dataset.** The parent")
        A("   directory contains no other folder with `.zip` archives in it.")
    A("")

    A("4. **Nested archives are present and were not recursed into.** Some archives")
    A("   contain `.zip` entries of their own (for example inside `15_9-F-12.zip`,")
    A("   `15_9-F-14.zip`, `15_9-F-15 D.zip` and `Volve_Well_technical_data.zip`).")
    A("   They were extracted as opaque files. Whatever they hold is not represented")
    A("   in the per-code counts above.")
    A("")

    A("5. **`GEOM` has no archive of its own.** Fault polygons exist only as")
    A("   `FAULT_*.GRDECL` inside the Eclipse model archive, facies/pick spreadsheets")
    A("   only inside the per-well log archives under `05.PETROPHYSICAL INTERPRETATION/`,")
    A("   and perforation logs only as `WL_RAW_PROD_CCL-PERF*` entries. Geophysical")
    A("   interpretation is therefore embedded in other deliveries rather than")
    A("   delivered as a product, which the per-subdirectory mapping reflects.")
    A("")

    segy = [
        r for r in rows
        if posixpath.splitext(r["entry_path_original"])[1].lower() in (".segy", ".sgy")
    ]
    segy_codes = collections.Counter(r["source_code"] for r in segy)
    segy_dirs = collections.Counter(
        posixpath.dirname(r["entry_path_original"]) for r in segy
    )
    A(f"6. **`SEIS` is absent while SEG-Y is present.** All {len(segy)} `.segy` files")
    A("   are borehole seismic, not surface seismic, and are coded")
    A(f"   {', '.join(f'`{c}` ({n})' for c, n in segy_codes.most_common())}.")
    A("   They arrive twice, from two separate deliveries of the same F-15 A survey:")
    A("")
    for d, n in segy_dirs.most_common():
        A(f"   - `{d}` — {n} files")
    A("")
    A("   The per-well archive carries a copy under `08.VSP_VELOCITY` and the dedicated")
    A("   seismic archive carries one under `VSP/`. The 34 basenames match exactly and")
    A("   both sets total 123,548,304 bytes. Archive-level duplicate detection does not")
    A("   group them, correctly: the archives as wholes are different. Both copies are")
    A("   kept. See the conflict noted below before treating either as authoritative.")
    A("   No surface seismic volume was delivered.")
    A("")

    A("7. **`PROD` arrives as a single Excel workbook**, not as tabular text:")
    A("   `Production_data/Volve production data.xlsx` (2.2 MB). There is no CSV form")
    A("   of it anywhere in the dataset, so the whole production history — the code")
    A("   with the fewest files — sits in one binary file. It is not blocked: `.xlsx`")
    A("   is a zip of XML parts and the standard library can read it with `zipfile`")
    A("   plus `ElementTree`. Whether to do that or take a dependency is a real")
    A("   decision, recorded in `docs/adr/0001-stdlib-only-ingestion.md`.")
    A("")

    A("8. **Four `left_intentionally_empty.txt` markers** stand in for content in")
    A("   `Well_technical_data/CasingSeat/`, `CasingWear/`, `Compass/` and `WellPlan/`.")
    A("   The `Compass` one matters: it means the directional-survey product named in")
    A("   the brief was deliberately not shipped in that folder. The surveys that do")
    A("   exist come from the WITSML `trajectory/` subtrees and from")
    A("   `WellWellbore/*/Standard Survey Report_*` files instead.")
    A("   These four folders are reported as `UNCLASSIFIED` on purpose. An earlier")
    A("   pass coded `Compass/` as `TRAJ` on the strength of its directory name; that")
    A("   was wrong, because the only file in it is a marker saying the folder is")
    A("   empty. A placeholder is evidence of absence, so it is no longer allowed to")
    A("   drive a source code.")
    A("")

    utf8_archives = [
        s["name"] for s in manifest["archives"]
        if not s.get("error") and 0 < s["utf8_flag_set_count"] < s["entry_count"]
    ]
    A("9. **The producer's own readme reclassified a whole subtree, and it was right.**")
    A("   `Well_technical_data/EDT_EDM_read_me.txt` (Statoil, 2018-04-11) states that")
    A("   `CasingSeat, CasingWear, Compass, EDM.XML, Site, Site_TemplateSlot,")
    A("   StressCheck, Wellcat, WellPlan, WellWellbore` are one **EDT/EDM export from")
    A("   Landmark software** — which is the brief's own definition of `TRAJ`")
    A("   (EDT/EDM/Compass). An early pass had coded `WellWellbore/` as `DOC`, because")
    A("   39% of its files are PDF and the DOC rule outscored the survey rule.")
    A("   Checking the content against the readme showed 159 of its 180 files are")
    A("   Compass wellpath exports: 49 `Standard Survey Report_*`, plus 110 named with")
    A("   the Compass status suffixes `_PLAN`, `_PROTOTYPE` and `_ACTUAL`. The PDFs are")
    A("   the *rendering* of the surveys, not unrelated documents. That suffix")
    A("   convention is now an explicit rule and `WellWellbore/` is coded `TRAJ`.")
    A("   `StressCheck/` and `Wellcat/` remain unclassified on purpose: they are")
    A("   casing-stress and tubing-design files from the same export, and no source")
    A("   code in the brief covers well engineering design.")
    A("")

    good = [s for s in manifest["archives"] if not s.get("error")]
    all_set = [s for s in good if s["utf8_flag_all_set"]]
    none_set = [s for s in good if s["utf8_flag_set_count"] == 0]
    ambiguous = [
        n for s in good for n in s["encoding_notes"]
        if not n["utf8_flag"] and n["differs"]
    ]
    A("10. **Encoding: the mangling the brief warned about does not occur, but the")
    A(f"   flag is inconsistent.** {len(all_set)} archives set the UTF-8 flag on every")
    A(f"   entry; {len(none_set)} set it on none; {len(utf8_archives)} set it on some")
    A("   entries only.")
    for s in good:
        if 0 < s["utf8_flag_set_count"] < s["entry_count"]:
            A(f"   `{s['name']}` sets it on {s['utf8_flag_set_count']} of")
            A(f"   {s['entry_count']:,} entries — the ones whose names carry `æ ø å`.")
    A(f"   Across all {len(good)} archives, {len(ambiguous)} entry names are genuinely")
    A("   ambiguous (unflagged *and* non-ASCII). Every unflagged name in this dataset")
    A("   is pure ASCII, so the cp437 fallback decodes them identically to UTF-8 and")
    A("   latin-1. Where a name does carry non-ASCII, every reading is still recorded")
    A("   per entry in `name-mapping.csv` rather than one being chosen silently.")
    A("")

    A("11. **`$47$` is a live encoding in entry names, not only in archive names.**")
    A("    It appears inside WITSML entry paths too, e.g.")
    A("    `15_$47$_9-F-9 A - Main Wellbore (B-986464)(NULL).xml`. It encodes a forward")
    A("    slash from the source system. Slugs restore it as a hyphen for directory")
    A("    names; entry paths keep it verbatim, because `$` is legal on Windows and the")
    A("    string is data.")
    A("")

    A("12. **Layout deviation, deliberate.** The brief shows a `<slug>` level only under")
    A("    `witsml/` and `log/`. That level is applied under every code directory here.")
    A("    Several archives contribute to `doc/`, `geom/` and `traj/`, and without a")
    A("    per-source level their entry paths collide — `license.txt` alone arrives from")
    A("    five archives. The slug is derived from the archive's own root folder name,")
    A("    so it preserves the source-given name rather than inventing one.")
    A("")

    rejected = extraction.get("rejected_entries", [])
    A(f"13. **Path safety:** {len(rejected)} entries were rejected as unsafe")
    A("    (traversal or absolute paths).")
    if rejected:
        for r in rejected[:10]:
            A(f"    - `{r['archive']}` → `{r['entry']}` ({r['reason']})")
    A("")

    renamed = [r for r in rows if r["rename_reason"]]
    A(f"14. **Renames:** {len(renamed)} of {len(rows)} extracted files needed a name change.")
    if renamed:
        reasons = collections.Counter(
            part.split(":")[0] for r in renamed for part in r["rename_reason"].split(";") if part
        )
        for reason, n in reasons.most_common():
            A(f"    - `{reason}`: {n}")
        A("    Every one is reversible from `name-mapping.csv`.")
    A("")

    pct = [r for r in rows if re.search(r"%[0-9A-Fa-f]{2}", r["entry_path_original"])]
    if pct:
        A(f"15. **{len(pct)} entry names are percent-encoded** and were left that way.")
        A("    For example `F-13_AB%20DG2_Target%20btw%20F12_F14%20Rev2%2C3%20141210-Final"
          "%2C%20v1.sck`,")
        A("    where `%20` is a space and `%2C` a comma. Sibling files in the same folder")
        A("    use literal spaces, so the encoding is inconsistent within one directory —")
        A("    two different export paths fed the same folder. The names are stored")
        A("    verbatim: decoding them here would be a transformation, and this session")
        A("    writes none. Identity resolution will have to normalise them, and should")
        A("    treat `%20` and a literal space as the same character when it does.")
        A("")

    lnk = [r for r in rows if r["entry_path_original"].lower().endswith(".lnk")]
    if lnk:
        A(f"16. **{len(lnk)} Windows shortcut (`.lnk`) file(s) shipped inside the data**, e.g.")
        A(f"    `{lnk[0]['entry_path_original']}`. A shortcut points at a path on the")
        A("    machine that produced the archive; it carries no data of its own and its")
        A("    target almost certainly does not exist here.")
        A("")

    cross = duplicates.get("cross_archive_files", {})
    conflicts = cross.get("conflicts", [])
    if cross:
        A("17. **Same file, same size, different bytes — in "
          f"{cross['same_name_same_size_different_crc']} cases.**")
        A(f"    {cross['files_in_more_than_one_archive']:,} files appear in more than one")
        A(f"    archive under the same name and size. {cross['identical_everywhere']:,} of")
        A("    them are byte-identical everywhere, which is reassuring and expected for")
        A("    partially overlapping deliveries. A further")
        A(f"    {cross['coincidental_name_collisions']:,} are coincidence rather than")
        A("    overlap — sequence-numbered WITSML exports and fixed export-manifest names")
        A(f"    ({', '.join('`' + n + '`' for n in cross['coincidental_examples'][:5])})")
        A("    that describe *different* wellbores and merely happen to match in length;")
        A("    those are excluded by the corroboration rule in the method note. These are")
        A("    the real conflicts:")
        A("")
        for c in conflicts[:12]:
            A(f"    - `{c['basename']}` ({c['size_bytes']:,} bytes)")
            for cp in c["copies"]:
                A(f"      - CRC32 `{cp['crc32']}` — `{cp['archive']}` → `{cp['entry']}`")
        A("")
        A("    Identical name, identical byte length, different CRC32. That cannot be a")
        A("    truncated download: a partial copy would be shorter. It is either a")
        A("    re-processed version that kept the original length, or one copy is")
        A("    corrupt. Nothing here can tell which, because deciding would mean reading")
        A("    the trace data, and this session parses nothing. Both copies were")
        A("    extracted and neither was preferred. **Resolve this before either copy is")
        A("    used**, and note that a pipeline picking files by name alone would silently")
        A("    choose one at random.")
        A("")

    A("18. **One file appeared inside the read-only archive folder during this session,")
    A("    and it was not put there by this pipeline.** The interactive tool session")
    A("    ran with the archive folder as its working directory and wrote")
    A("    `.claude/settings.local.json` there. Nothing in `inventory.py` opens that")
    A("    folder for writing. It was left in place rather than deleted, because")
    A("    deleting inside the archive folder would itself break the read-only rule.")
    A("    It is noted here so the folder's contents are not mistaken for source data.")
    A("")

    return F


def write_dictionary_doc(manifest: dict, rows: list[dict]) -> None:
    """Format facts only — what the files actually contain, not what we plan."""
    out: list[str] = []
    A = out.append
    A("# Volve data dictionary — observed format facts")
    A("")
    A("Draft. Every statement below was measured from an extracted file, not assumed.")
    A("This document records **format** only: encoding, delimiters, headers, date")
    A("shapes, sentinel values, non-ASCII characters and units as literally written")
    A("in the files. It contains no transformation logic, no domain model and no plan.")
    A("")
    A("Where a code has several file formats, one representative of each was profiled.")
    A("A blank field means the probe found no instance, not that none exists.")
    A("")

    by_code: dict[str, list[dict]] = collections.defaultdict(list)
    for r in rows:
        by_code[r["source_code"]].append(r)

    for code in sorted(by_code):
        members = by_code[code]
        A(f"## {code}")
        A("")
        label = SOURCE_CODES.get(code, "not classified")
        A(f"_{label}_ — {len(members)} extracted files.")
        A("")
        exts = collections.Counter(
            posixpath.splitext(r["entry_path_extracted"])[1].lower() or "<noext>"
            for r in members
        )
        A("Formats present: " + ", ".join(f"`{e}` x{n}" for e, n in exts.most_common(10)) + ".")
        A("")

        # Profile one text-ish representative per extension, up to three.
        profiled = 0
        for ext, _n in exts.most_common():
            if profiled >= 3 or ext not in TEXT_EXTS:
                continue
            candidate = next(
                (r for r in members
                 if posixpath.splitext(r["entry_path_extracted"])[1].lower() == ext),
                None,
            )
            if candidate is None:
                continue
            path = REPO_ROOT / candidate["entry_path_extracted"]
            if not path.exists():
                continue
            try:
                prof = profile_text(path)
            except OSError:
                continue
            profiled += 1
            A(f"### `{ext}` — probed on `{candidate['entry_path_extracted']}`")
            A("")
            A("| Property | Observed |")
            A("|---|---|")
            A(f"| Encoding | {prof['encoding']} |")
            A(f"| Line endings | {prof['line_ending']} |")
            A(f"| Delimiter | {prof['delimiter']} |")
            A(f"| First non-empty line | `{prof['first_non_empty_line'][:160]}` |")
            A(f"| Header row present | {'yes — see line above' if prof['first_non_empty_line'] else 'not detected'} |")
            A(f"| Date formats seen | {', '.join(prof['date_formats']) or 'none found in sample'} |")
            A(f"| Sentinel values seen | {', '.join('`' + s + '`' for s in prof['sentinels']) or 'none found in sample'} |")
            nonascii = ", ".join(f"`{c}` (U+{ord(c):04X})" for c in prof["non_ascii_chars"])
            A(f"| Non-ASCII characters | {nonascii or 'none in sample'} |")
            A(f"| Units written in file | {', '.join('`' + u + '`' for u in prof['units_declared']) or 'none declared in sample'} |")
            A("")

        binary_exts = [e for e, _ in exts.most_common() if e not in TEXT_EXTS]
        if binary_exts:
            A("Binary or opaque formats under this code, not text-profiled: "
              + ", ".join(f"`{e}`" for e in binary_exts) + ".")
            A("")

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "data-dictionary.md").write_text("\n".join(out) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m hugin.ingestion.inventory",
        description="Inventory, duplicate detection and targeted extraction of the Volve archives.",
    )
    parser.add_argument(
        "--archive-dir", default=str(DEFAULT_ARCHIVE_DIR),
        help="read-only folder holding the .zip archives",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="Phases A-C: inventory, duplicates, classification (no extraction)")
    p_scan.add_argument(
        "--quarantine-duplicates", action="store_true",
        help="also write data/_inventory/duplicate-list.txt. Deletes nothing.",
    )
    p_scan.set_defaults(func=cmd_scan)

    p_extract = sub.add_parser("extract", help="Phase D: targeted, idempotent extraction")
    p_extract.add_argument(
        "--no-crc", action="store_true",
        help="skip CRC verification of already-present files (size check only)",
    )
    p_extract.add_argument(
        "--keep-orphans", action="store_true",
        help=(
            "keep files left in data/landing/ by an earlier run that the current "
            "mapping no longer produces (they are reported either way). Never "
            "affects the archive folder."
        ),
    )
    p_extract.set_defaults(func=cmd_extract)

    p_report = sub.add_parser("report", help="Phase E: write docs/data-inventory.md and docs/data-dictionary.md")
    p_report.set_defaults(func=cmd_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
