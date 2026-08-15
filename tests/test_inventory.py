"""Tests for the Volve archive inventory and extraction.

Two layers:

* Synthetic tests build small zips in a temp dir and exercise the extractor's
  guarantees directly. They run anywhere, with no dataset present.
* Dataset tests assert over the real artefacts in data/_inventory/. They skip
  when those artefacts have not been produced yet.

Nothing here writes to the archive folder.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import zipfile
from pathlib import Path

import pytest

from hugin.ingestion import inventory as inv

REPO_ROOT = Path(__file__).resolve().parents[1]

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def make_zip(path: Path, entries: dict[str, bytes], dirs: tuple[str, ...] = ()) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for d in dirs:
            zf.writestr(zipfile.ZipInfo(d if d.endswith("/") else d + "/"), b"")
        for name, data in entries.items():
            zf.writestr(name, data)
    return path


def tree_fingerprint(root: Path) -> list[tuple[str, int, str]]:
    """(relative path, size, sha256) for every file and dir under root."""
    out: list[tuple[str, int, str]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        rel_dir = Path(dirpath).relative_to(root).as_posix()
        if rel_dir != ".":
            out.append((rel_dir + "/", -1, "<dir>"))
        for fn in sorted(filenames):
            p = Path(dirpath) / fn
            rel = p.relative_to(root).as_posix()
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            out.append((rel, p.stat().st_size, digest))
    return sorted(out)


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """Point every module-level output path at a temp directory."""
    data = tmp_path / "data"
    docs = tmp_path / "docs"
    monkeypatch.setattr(inv, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(inv, "DATA_DIR", data)
    monkeypatch.setattr(inv, "INVENTORY_DIR", data / "_inventory")
    monkeypatch.setattr(inv, "LANDING_DIR", data / "landing")
    monkeypatch.setattr(inv, "DOCS_DIR", docs)
    monkeypatch.setattr(inv, "SOURCE_README_DIR", docs / "source-readme")
    monkeypatch.setattr(inv, "NAME_MAPPING_PATH", data / "_inventory" / "name-mapping.csv")
    (data / "_inventory").mkdir(parents=True)
    return tmp_path


def scan_dir(archive_dir: Path) -> tuple[dict, dict]:
    scans = []
    for p in sorted(archive_dir.glob("*.zip")):
        s = inv.scan_archive(p)
        rec = vars(s)
        rec["classification"] = inv.classify_archive(p, s.root_prefix)
        scans.append(rec)
    manifest = {"archives": scans, "archive_count": len(scans)}
    return manifest, inv.group_duplicates(scans)


# --------------------------------------------------------------------------
# Requirement 1: extraction is idempotent
# --------------------------------------------------------------------------

def test_extraction_is_idempotent(sandbox, tmp_path, capsys):
    archives = tmp_path / "archives"
    archives.mkdir()
    make_zip(
        archives / "well_a.zip",
        {
            "well_a/01.MUD_LOG/MUD_LOG_1.LAS": b"~VERSION\nVERS. 2.0\n",
            "well_a/02.LWD_EWL/WL_RAW_GR_1.ASC": b"DEPTH GR\n100.0 45.2\n",
            "well_a/empty.LAS": b"",
        },
        dirs=("well_a/emptydir",),
    )
    manifest, dups = scan_dir(archives)

    inv.extract_archives(archives, manifest, dups)
    first = tree_fingerprint(sandbox / "data" / "landing")
    first_csv = (sandbox / "data" / "_inventory" / "name-mapping.csv").read_text(encoding="utf-8")

    inv.extract_archives(archives, manifest, dups)
    second = tree_fingerprint(sandbox / "data" / "landing")
    second_csv = (sandbox / "data" / "_inventory" / "name-mapping.csv").read_text(encoding="utf-8")

    assert first == second, "second extraction produced a different file tree"
    assert first_csv == second_csv, "name-mapping.csv is not stable across runs"

    # The second run must recognise the files as already correct, not rewrite them.
    out = capsys.readouterr().out
    assert "files_skipped_already_correct" in out


def test_second_run_rewrites_a_corrupted_file(sandbox, tmp_path):
    archives = tmp_path / "archives"
    archives.mkdir()
    make_zip(archives / "well_a.zip", {"well_a/01.MUD_LOG/A.LAS": b"~VERSION\ncorrect\n"})
    manifest, dups = scan_dir(archives)
    inv.extract_archives(archives, manifest, dups)

    target = next((sandbox / "data" / "landing").rglob("A.LAS"))
    target.write_bytes(b"~VERSION\nCORRUPT!\n")  # same length, different CRC

    inv.extract_archives(archives, manifest, dups)
    assert target.read_bytes() == b"~VERSION\ncorrect\n", "CRC mismatch was not repaired"


def test_stale_files_from_an_earlier_run_are_pruned(sandbox, tmp_path):
    """A reclassification must not leave the old destination behind."""
    archives = tmp_path / "archives"
    archives.mkdir()
    make_zip(archives / "well_a.zip", {"well_a/01.MUD_LOG/A.LAS": b"~V\n"})
    manifest, dups = scan_dir(archives)
    inv.extract_archives(archives, manifest, dups)

    stale = sandbox / "data" / "landing" / "log" / "well_a" / "stale_from_before.LAS"
    stale.write_bytes(b"left over\n")

    result = inv.extract_archives(archives, manifest, dups)
    assert not stale.exists(), "a stale file survived re-extraction"
    assert any("stale_from_before" in o for o in result["orphans"])


def test_orphans_can_be_kept_and_are_still_reported(sandbox, tmp_path):
    archives = tmp_path / "archives"
    archives.mkdir()
    make_zip(archives / "well_a.zip", {"well_a/01.MUD_LOG/A.LAS": b"~V\n"})
    manifest, dups = scan_dir(archives)
    inv.extract_archives(archives, manifest, dups)

    stale = sandbox / "data" / "landing" / "log" / "well_a" / "keepme.LAS"
    stale.write_bytes(b"left over\n")

    result = inv.extract_archives(archives, manifest, dups, prune_orphans=False)
    assert stale.exists()
    assert result["orphans_pruned"] == []
    assert any("keepme" in o for o in result["orphans"])


def test_pruning_never_reaches_outside_the_landing_tree(sandbox, tmp_path):
    archives = tmp_path / "archives"
    archives.mkdir()
    make_zip(archives / "well_a.zip", {"well_a/01.MUD_LOG/A.LAS": b"~V\n"})
    manifest, dups = scan_dir(archives)

    bystander = sandbox / "data" / "_inventory" / "do_not_touch.json"
    bystander.write_text("{}", encoding="utf-8")
    docs_file = sandbox / "docs" / "source-readme"
    docs_file.mkdir(parents=True, exist_ok=True)
    (docs_file / "keep.txt").write_text("keep", encoding="utf-8")

    inv.extract_archives(archives, manifest, dups)
    assert bystander.exists()
    assert (docs_file / "keep.txt").exists()


def test_empty_dirs_and_zero_byte_files_are_created(sandbox, tmp_path):
    archives = tmp_path / "archives"
    archives.mkdir()
    make_zip(
        archives / "well_a.zip",
        {"well_a/01.MUD_LOG/A.LAS": b"", "well_a/01.MUD_LOG/B.LAS": b"x"},
        dirs=("well_a/emptydir",),
    )
    manifest, dups = scan_dir(archives)
    inv.extract_archives(archives, manifest, dups)

    landing = sandbox / "data" / "landing"
    assert any(p.name == "emptydir" and p.is_dir() for p in landing.rglob("*"))
    zero = next(landing.rglob("A.LAS"))
    assert zero.is_file() and zero.stat().st_size == 0


# --------------------------------------------------------------------------
# Requirement 2: every archive is classified or recorded as unclassified
# --------------------------------------------------------------------------

def test_every_archive_gets_a_verdict_with_evidence(sandbox, tmp_path):
    archives = tmp_path / "archives"
    archives.mkdir()
    make_zip(archives / "logs.zip", {"logs/04.COMPOSITE/WLC_A.LAS": b"~V\n"})
    make_zip(archives / "mystery.zip", {"mystery/a.qqq": b"\x00\x01", "mystery/b.zzz": b"\x02"})
    manifest, _ = scan_dir(archives)

    for s in manifest["archives"]:
        cls = s["classification"]
        assert cls["archive_code"] in inv.SOURCE_CODES or cls["archive_code"] == inv.UNCLASSIFIED
        assert cls["archive_evidence"], f"{s['name']} has a verdict but no evidence"

    codes = {s["name"]: s["classification"]["archive_code"] for s in manifest["archives"]}
    assert codes["logs.zip"] == "LOG"
    assert codes["mystery.zip"] == inv.UNCLASSIFIED


def test_unclassified_entries_land_in_their_own_tree(sandbox, tmp_path):
    archives = tmp_path / "archives"
    archives.mkdir()
    make_zip(archives / "mystery.zip", {"mystery/sub/a.qqq": b"\x00"})
    manifest, dups = scan_dir(archives)
    inv.extract_archives(archives, manifest, dups)

    landing = sandbox / "data" / "landing"
    assert (landing / "_unclassified").is_dir()
    assert list((landing / "_unclassified").rglob("a.qqq"))


# --------------------------------------------------------------------------
# Requirement 3: name-mapping.csv has one row per extracted file
# --------------------------------------------------------------------------

def test_mapping_has_exactly_one_row_per_extracted_file(sandbox, tmp_path):
    archives = tmp_path / "archives"
    archives.mkdir()
    make_zip(
        archives / "well_a.zip",
        {
            "well_a/01.MUD_LOG/A.LAS": b"~V\n",
            "well_a/01.MUD_LOG/B.ASC": b"x\n",
            "well_a/14.DIV.REPORTS/r.pdf": b"%PDF-1.4\n",
        },
        dirs=("well_a/emptydir",),
    )
    make_zip(archives / "wits.zip", {"wits/1/trajectory/1.xml": b"<t/>"})
    manifest, dups = scan_dir(archives)
    inv.extract_archives(archives, manifest, dups)

    with open(sandbox / "data" / "_inventory" / "name-mapping.csv", newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert set(rows[0]) == {
        "archive", "entry_path_original", "entry_path_extracted",
        "source_code", "rename_reason", "encoding_note",
    }

    extracted = [
        p for p in (sandbox / "data" / "landing").rglob("*") if p.is_file()
    ]
    assert len(rows) == len(extracted), (
        f"{len(rows)} mapping rows for {len(extracted)} extracted files"
    )

    on_disk = {p.relative_to(sandbox).as_posix() for p in extracted}
    in_csv = {r["entry_path_extracted"] for r in rows}
    assert in_csv == on_disk

    # The original name must never be lost.
    for r in rows:
        assert r["entry_path_original"]
        assert r["source_code"]


def test_original_name_is_recoverable_after_sanitisation(sandbox, tmp_path):
    archives = tmp_path / "archives"
    archives.mkdir()
    # Colon is legal in a zip entry, illegal in a Windows filename.
    make_zip(archives / "well_a.zip", {"well_a/01.MUD_LOG/a:b?c.LAS": b"~V\n"})
    manifest, dups = scan_dir(archives)
    inv.extract_archives(archives, manifest, dups)

    with open(sandbox / "data" / "_inventory" / "name-mapping.csv", newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    row = rows[0]
    assert row["entry_path_original"].endswith("a:b?c.LAS")
    assert row["entry_path_extracted"].endswith("a_b_c.LAS")
    assert "invalid_windows_char" in row["rename_reason"]


# --------------------------------------------------------------------------
# Requirement 4: sanitisation is injective
# --------------------------------------------------------------------------

def test_case_only_differences_get_distinct_destinations(sandbox, tmp_path):
    archives = tmp_path / "archives"
    archives.mkdir()
    make_zip(
        archives / "well_a.zip",
        {
            "well_a/01.MUD_LOG/Report.LAS": b"upper\n",
            "well_a/01.MUD_LOG/report.LAS": b"lower\n",
            "well_a/01.MUD_LOG/REPORT.LAS": b"shout\n",
        },
    )
    manifest, dups = scan_dir(archives)
    inv.extract_archives(archives, manifest, dups)

    with open(sandbox / "data" / "_inventory" / "name-mapping.csv", newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    dests = [r["entry_path_extracted"] for r in rows]
    assert len(dests) == 3
    assert len({d.lower() for d in dests}) == 3, "case-only variants collided"
    assert sum(1 for r in rows if "case_insensitive_collision" in r["rename_reason"]) == 2

    # All three payloads survived independently.
    payloads = {
        (sandbox / d).read_bytes()
        for d in dests
    }
    assert payloads == {b"upper\n", b"lower\n", b"shout\n"}


def test_distinct_originals_never_share_a_destination(sandbox, tmp_path):
    """The injectivity property, on names engineered to collide."""
    archives = tmp_path / "archives"
    archives.mkdir()
    make_zip(
        archives / "well_a.zip",
        {
            "well_a/01.MUD_LOG/a:b.LAS": b"1\n",   # -> a_b.LAS
            "well_a/01.MUD_LOG/a*b.LAS": b"2\n",   # -> a_b.LAS
            "well_a/01.MUD_LOG/a?b.LAS": b"3\n",   # -> a_b.LAS
            "well_a/01.MUD_LOG/a_b.LAS": b"4\n",   # -> a_b.LAS, unchanged
            'well_a/01.MUD_LOG/a"b.LAS': b"5\n",   # -> a_b.LAS
        },
    )
    manifest, dups = scan_dir(archives)
    inv.extract_archives(archives, manifest, dups)

    with open(sandbox / "data" / "_inventory" / "name-mapping.csv", newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    originals = {r["entry_path_original"] for r in rows}
    dests = [r["entry_path_extracted"] for r in rows]
    assert len(originals) == 5
    assert len({d.lower() for d in dests}) == 5, "sanitisation is not injective"

    payloads = {(sandbox / d).read_bytes() for d in dests}
    assert payloads == {b"1\n", b"2\n", b"3\n", b"4\n", b"5\n"}


def test_registry_is_injective_on_a_generated_name_set():
    """Property check on the registry itself, independent of any filesystem."""
    registry = inv.DestinationRegistry()
    raw_names = [
        f"root/{a}{b}c.txt"
        for a in ("x", "X", "x:", "x*", 'x"', "x?", "x<", "x>", "x|")
        for b in ("", "1", "A", "a")
    ]
    seen: set[str] = set()
    for name in raw_names:
        safe, _reasons, ok = inv.sanitize_relative_path(name)
        assert ok
        unique, _reason = registry.claim(safe)
        assert unique.lower() not in seen, f"{name} collided onto {unique}"
        seen.add(unique.lower())
    assert len(seen) == len(raw_names)


# --------------------------------------------------------------------------
# Path safety and slug rules
# --------------------------------------------------------------------------

@pytest.mark.parametrize("evil", [
    "../escape.txt",
    "a/../../escape.txt",
    "/absolute.txt",
    "C:/windows/system32/evil.txt",
    "a/b/../../../out.txt",
])
def test_traversal_and_absolute_paths_are_rejected(evil):
    _safe, reasons, ok = inv.sanitize_relative_path(evil)
    assert not ok, f"{evil} was not rejected"
    assert reasons


def test_traversal_entry_is_rejected_not_written(sandbox, tmp_path):
    archives = tmp_path / "archives"
    archives.mkdir()
    zpath = archives / "evil.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("evil/01.MUD_LOG/ok.LAS", b"~V\n")
        zf.writestr("evil/../../../pwned.LAS", b"pwned\n")
    manifest, dups = scan_dir(archives)
    result = inv.extract_archives(archives, manifest, dups)

    assert result["stats"].get("entries_rejected", 0) >= 1
    assert not (tmp_path.parent / "pwned.LAS").exists()
    assert not list(tmp_path.rglob("pwned.LAS"))


def test_inner_traversal_that_stays_inside_is_allowed():
    safe, _reasons, ok = inv.sanitize_relative_path("a/b/../c.txt")
    assert not ok  # we reject any '..', rather than resolving it


@pytest.mark.parametrize("source,expected", [
    ("Norway-StatoilHydro-15_$47$_9-F-15B", "Norway-StatoilHydro-15-9-F-15B"),
    ("Norway-NA-15_$47$_9-F-9 A", "Norway-NA-15-9-F-9_A"),
    ("15_9-F-15 B", "15_9-F-15_B"),
    ("Well_technical_data", "Well_technical_data"),
])
def test_slug_rules(source, expected):
    assert inv.make_slug(source) == expected


def test_slug_never_introduces_a_path_separator():
    assert "/" not in inv.make_slug("Norway-NA-15_$47$_9-F-9 A")
    assert "\\" not in inv.make_slug("Norway-NA-15_$47$_9-F-9 A")


def test_reserved_device_names_are_suffixed():
    safe, reasons, ok = inv.sanitize_relative_path("a/CON.txt")
    assert ok and safe == "a/CON.txt_"
    assert any("reserved_device_name" in r for r in reasons)


# --------------------------------------------------------------------------
# Duplicate detection
# --------------------------------------------------------------------------

def test_duplicates_are_detected_by_content_not_by_name(tmp_path):
    archives = tmp_path / "archives"
    archives.mkdir()
    payload = {"a.txt": b"same\n", "sub/b.txt": b"content\n"}
    make_zip(archives / "short.zip", {f"RootOne/{k}": v for k, v in payload.items()})
    make_zip(archives / "a_much_longer_name (1).zip", {f"RootTwo/{k}": v for k, v in payload.items()})
    make_zip(archives / "different.zip", {"RootThree/a.txt": b"other\n"})

    _manifest, dups = scan_dir(archives)

    assert dups["group_count"] == 1
    group = dups["groups"][0]
    assert group["canonical"] == "short.zip"
    assert group["duplicates"] == ["a_much_longer_name (1).zip"]
    assert "different.zip" not in dups["duplicate_archives"]


def test_duplicate_archives_are_skipped_but_never_deleted(sandbox, tmp_path):
    archives = tmp_path / "archives"
    archives.mkdir()
    payload = {"01.MUD_LOG/A.LAS": b"~V\n"}
    make_zip(archives / "short.zip", {f"RootOne/{k}": v for k, v in payload.items()})
    dup = make_zip(archives / "longer_name.zip", {f"RootTwo/{k}": v for k, v in payload.items()})

    manifest, dups = scan_dir(archives)
    result = inv.extract_archives(archives, manifest, dups)

    assert result["stats"]["archives_skipped_duplicate"] == 1
    assert dup.exists(), "a duplicate archive was deleted"

    with open(sandbox / "data" / "_inventory" / "name-mapping.csv", newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert {r["archive"] for r in rows} == {"short.zip"}


def _cross(archives: Path) -> dict:
    scans = []
    for p in sorted(archives.glob("*.zip")):
        s = inv.scan_archive(p)
        scans.append(vars(s))
    return inv.cross_archive_files(scans, {p.name: p for p in archives.glob("*.zip")})


def test_cross_archive_reports_a_real_byte_conflict(tmp_path):
    """Archives that clearly share a delivery but disagree on one file."""
    archives = tmp_path / "archives"
    archives.mkdir()
    shared = {f"A/data/f{i}.segy": bytes([i]) * 100 for i in range(6)}
    other = dict(shared)
    # Same name, same length, different bytes.
    other["A/data/f3.segy"] = b"\xff" * 100
    make_zip(archives / "per_well.zip", {k.replace("A/", "PerWell/"): v for k, v in shared.items()})
    make_zip(archives / "seismic.zip", {k.replace("A/", "Seismic/deep/"): v for k, v in other.items()})

    result = _cross(archives)
    assert result["same_name_same_size_different_crc"] == 1
    conflict = result["conflicts"][0]
    assert conflict["basename"] == "f3.segy"
    assert conflict["size_bytes"] == 100
    assert len({c["crc32"] for c in conflict["copies"]}) == 2
    assert result["identical_everywhere"] == 5


def test_cross_archive_ignores_coincidental_name_collisions(tmp_path):
    """Different wells' WITSML exports share 1.xml but share nothing else."""
    archives = tmp_path / "archives"
    archives.mkdir()
    make_zip(archives / "well_f12.zip", {
        "F12/1/message/1.xml": b"<m>twelve</m>",
        "F12/1/message/2.xml": b"<m>twelve-two</m>",
        "F12/MetaFileInfo.txt": b"twelve!",
    })
    make_zip(archives / "well_f14.zip", {
        "F14/1/message/1.xml": b"<m>fourteen</m>",   # same name+size, other bytes
        "F14/1/message/2.xml": b"<m>fourteen-2</m>",
        "F14/MetaFileInfo.txt": b"f14teen",
    })

    result = _cross(archives)
    # Nothing is shared byte-for-byte, so no clash is corroborated.
    assert result["same_name_same_size_different_crc"] == 0
    assert result["coincidental_name_collisions"] >= 1


def test_near_duplicates_are_not_grouped(tmp_path):
    archives = tmp_path / "archives"
    archives.mkdir()
    make_zip(archives / "one.zip", {"R/a.txt": b"same\n"})
    make_zip(archives / "two.zip", {"R/a.txt": b"same!\n"})  # different CRC and size
    _manifest, dups = scan_dir(archives)
    assert dups["group_count"] == 0


# --------------------------------------------------------------------------
# Phase A details
# --------------------------------------------------------------------------

def test_sample_entries_are_spread_not_the_first_twenty(tmp_path):
    archives = tmp_path / "archives"
    archives.mkdir()
    entries = {f"R/{i:04d}.txt": b"x" for i in range(500)}
    scan = inv.scan_archive(make_zip(archives / "many.zip", entries))

    assert len(scan.sample_entries) == inv.SAMPLE_ENTRY_COUNT
    first_twenty = [f"R/{i:04d}.txt" for i in range(20)]
    assert scan.sample_entries != first_twenty
    # A spread sample must reach the tail of the archive.
    assert any(e >= "R/0400.txt" for e in scan.sample_entries)


def test_scan_records_depth_sizes_and_longest_path(tmp_path):
    archives = tmp_path / "archives"
    archives.mkdir()
    long_name = "R/a/b/c/" + ("d" * 120) + ".txt"
    scan = inv.scan_archive(make_zip(archives / "deep.zip", {long_name: b"hello", "R/x.txt": b"hi"}))

    assert scan.file_count == 2
    assert scan.max_depth == 5
    assert scan.longest_path == long_name
    assert scan.longest_path_length == len(long_name)
    assert scan.uncompressed_bytes == 7


def test_directories_implied_by_file_paths_are_counted(tmp_path):
    """An archive with no directory entries still has directories.

    Most archives in this dataset carry none, so counting only entries flagged
    as directories reports "0 directories" for a tree several levels deep.
    """
    archives = tmp_path / "archives"
    archives.mkdir()
    scan = inv.scan_archive(make_zip(archives / "flat.zip", {
        "R/a/b/one.txt": b"1",
        "R/a/c/two.txt": b"2",
        "R/three.txt": b"3",
    }))

    assert scan.dir_count == 0, "this archive has no explicit directory entries"
    # R, R/a, R/a/b, R/a/c
    assert scan.implied_dir_count == 4


def test_explicit_directory_entries_are_counted_once(tmp_path):
    archives = tmp_path / "archives"
    archives.mkdir()
    path = archives / "explicit.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("R/", b"")
        zf.writestr("R/sub/", b"")
        zf.writestr("R/sub/file.txt", b"x")
    scan = inv.scan_archive(path)

    assert scan.dir_count == 2
    assert scan.implied_dir_count == 2, "an entry counted twice would give 3 or 4"


def test_non_utf8_flagged_scandinavian_name_is_reported_both_ways():
    """A cp437-decoded name that is really UTF-8 must be reported, not resolved.

    This exercises the probe directly rather than through a written zip, because
    ``zipfile`` sets the UTF-8 flag itself whenever a name is not ASCII-encodable.
    An unflagged non-ASCII entry therefore cannot be produced with the public
    write API at all — it only arrives from other tools, which is exactly the
    case the probe exists for.
    """
    info = zipfile.ZipInfo()
    # What zipfile hands us for raw UTF-8 bytes when the flag is clear.
    info.filename = "Sør".encode().decode("cp437") + ".txt"
    info.flag_bits = 0

    note = inv._encoding_probe(info)
    assert note is not None, "a mangled Scandinavian name was not detected"
    assert note.utf8_flag is False
    assert note.differs is True
    assert note.as_utf8 == "Sør.txt"
    assert note.as_latin1 != note.as_utf8
    # Every reading is kept; none replaces the other.
    assert note.entry_as_read != note.as_utf8
    assert note.entry_as_read == "S├╕r.txt"


def test_utf8_flagged_name_is_not_second_guessed():
    info = zipfile.ZipInfo()
    info.filename = "Sør.txt"
    info.flag_bits = 0x800
    note = inv._encoding_probe(info)
    assert note is not None
    assert note.utf8_flag is True
    assert note.differs is False
    assert note.as_utf8 == "Sør.txt"


def test_pure_ascii_names_produce_no_encoding_note(tmp_path):
    archives = tmp_path / "archives"
    archives.mkdir()
    scan = inv.scan_archive(make_zip(archives / "plain.zip", {"R/plain.txt": b"x"}))
    assert scan.encoding_notes == []


def test_bad_zip_is_recorded_not_raised(tmp_path):
    archives = tmp_path / "archives"
    archives.mkdir()
    (archives / "broken.zip").write_bytes(b"this is not a zip file at all")
    scan = inv.scan_archive(archives / "broken.zip")
    assert scan.error and "BadZipFile" in scan.error


# --------------------------------------------------------------------------
# Dataset-level assertions (skipped when artefacts are absent)
# --------------------------------------------------------------------------

MANIFEST = REPO_ROOT / "data" / "_inventory" / "archive-manifest.json"
MAPPING = REPO_ROOT / "data" / "_inventory" / "name-mapping.csv"

needs_scan = pytest.mark.skipif(not MANIFEST.exists(), reason="run 'make inventory' first")
needs_extract = pytest.mark.skipif(not MAPPING.exists(), reason="run 'make extract' first")


@needs_scan
def test_dataset_every_archive_has_a_verdict():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["archives"], "manifest is empty"
    for s in manifest["archives"]:
        if s.get("error"):
            continue
        cls = s["classification"]
        code = cls["archive_code"]
        assert code in inv.SOURCE_CODES or code == inv.UNCLASSIFIED
        assert cls["archive_evidence"], f"{s['name']}: verdict without evidence"
        for key, sub in cls["per_subdir"].items():
            assert sub["evidence"], f"{s['name']}/{key}: verdict without evidence"


@needs_scan
@needs_extract
def test_dataset_mapping_covers_every_extracted_file():
    with open(MAPPING, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    landing = REPO_ROOT / "data" / "landing"
    if not landing.exists():
        pytest.skip("landing tree absent")

    on_disk = {
        p.relative_to(REPO_ROOT).as_posix()
        for p in landing.rglob("*") if p.is_file()
    }
    in_csv = {r["entry_path_extracted"] for r in rows}

    # Files another program holds open (an open Excel workbook drops a ~$ lock
    # file beside itself) cannot be pruned; the extractor reports them.
    report = REPO_ROOT / "data" / "_inventory" / "extraction-report.json"
    locked = set()
    if report.exists():
        locked = {
            o["path"] for o in json.loads(report.read_text(encoding="utf-8")).get(
                "orphans_unprunable", []
            )
        }

    assert not (in_csv - on_disk), f"{len(in_csv - on_disk)} mapping rows have no file"
    unexplained = on_disk - in_csv - locked
    assert not unexplained, (
        f"{len(unexplained)} files on disk have no mapping row, "
        f"e.g. {sorted(unexplained)[:3]}"
    )


@needs_extract
def test_dataset_mapping_destinations_are_unique():
    with open(MAPPING, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    dests = [r["entry_path_extracted"].lower() for r in rows]
    assert len(set(dests)) == len(dests), "two entries share a destination path"

    originals = [(r["archive"], r["entry_path_original"]) for r in rows]
    assert len(set(originals)) == len(originals), "an entry was mapped twice"
