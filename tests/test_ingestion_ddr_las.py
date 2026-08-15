"""DDR and LOG readers, against measured format facts.

BR-08 has its own tests here, named for the rule.
"""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from hugin.common.config import Settings
from hugin.ingestion.ddr import DDRActivityReader, report_date_from_name
from hugin.ingestion.las import (
    STATIC_LOAD_DATE,
    LasCurveHeaderReader,
    LasSampleReader,
    scan_header,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
LANDING = REPO_ROOT / "data" / "landing"
pytestmark = pytest.mark.skipif(
    not LANDING.exists(), reason="landing tree not extracted; run 'make extract'"
)


def settings() -> Settings:
    return Settings(replay_epoch="2026-08-01T00:00:00Z", repo_root=REPO_ROOT)


# -- DDR --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("stem", "expected"),
    [
        ("15_9_F_14_2016_08_04", datetime.date(2016, 8, 4)),
        ("15_9_19_A_1980_01_01", datetime.date(1980, 1, 1)),
        ("no_date_here", None),
    ],
)
def test_ddr_report_date_comes_from_the_file_name(stem, expected):
    assert report_date_from_name(Path(f"{stem}.xml")) == expected


def test_ddr_reads_only_the_reports_that_end_on_the_replay_date():
    batches = list(DDRActivityReader(settings=settings()).read(datetime.date(2016, 8, 4)))
    assert batches, "2016-08-04 has a drilling report"
    for batch in batches:
        for index in range(batch.num_rows):
            assert batch.column("report_date")[index].as_py() == "2016-08-04"


def test_ddr_takes_the_report_date_from_dtimend_in_local_offset():
    """dTimEnd is written +02:00 in summer. Converting to UTC would move a
    third of the reports to the previous day and disagree with the file name."""
    batch = next(iter(DDRActivityReader(settings=settings()).read(datetime.date(2016, 8, 4))))
    assert batch.column("dtim_end")[0].as_py() == "2016-08-04T00:00:00+02:00"
    assert batch.column("report_date")[0].as_py() == "2016-08-04"


def test_ddr_emits_one_row_per_activity_with_a_sequence():
    batch = next(iter(DDRActivityReader(settings=settings()).read(datetime.date(2016, 8, 4))))
    sequences = [batch.column("activity_seq")[i].as_py() for i in range(batch.num_rows)]
    assert sequences == [str(n) for n in range(1, batch.num_rows + 1)]


def test_ddr_carries_the_npd_alias_that_teaches_br12():
    batch = next(iter(DDRActivityReader(settings=settings()).read(datetime.date(2016, 8, 4))))
    assert batch.column("npd_code_well")[0].as_py() == "15/9-F-14"
    assert batch.column("npd_number")[0].as_py() == "5351"
    assert batch.column("_wellbore_uid")[0].as_py() == "15/9-F-14"


def test_ddr_keeps_multiline_free_text_comments_as_written():
    batch = next(iter(DDRActivityReader(settings=settings()).read(datetime.date(2016, 8, 4))))
    comments = [batch.column("comments")[i].as_py() or "" for i in range(batch.num_rows)]
    assert any("\n" in c for c in comments), "comments are multi-line in this report"


def test_ddr_prefers_xml_and_records_which_form_it_read():
    batch = next(iter(DDRActivityReader(settings=settings()).read(datetime.date(2016, 8, 4))))
    formats = {batch.column("source_format")[i].as_py() for i in range(batch.num_rows)}
    assert formats == {"xml"}, "every report in this delivery has an XML form"


def test_ddr_yields_nothing_for_a_day_with_no_report():
    assert list(DDRActivityReader(settings=settings()).read(datetime.date(1999, 5, 5))) == []


# -- LAS header parsing -----------------------------------------------------


def test_las_header_line_keeps_the_value_out_of_the_unit_field(tmp_path):
    """'NULL.   -999.25  : NULL' declares no unit and a sentinel of -999.25.

    A pattern that skips whitespace after the dot reads -999.25 as the unit and
    leaves the sentinel empty — which defeats BR-08 without failing.
    """
    path = tmp_path / "t.las"
    path.write_text(
        "~Version Information\nVERS.   2.0 : CWLS\nWRAP.   NO : one line\n"
        "~Well Information\n"
        "STRT.M   100.0 : START\n"
        "NULL.   -999.25   : NULL\n"
        "WELL.   15/9-F-12 : WELL\n"
        "~Curve Information\n"
        "DEPT.M   : depth\n"
        "GR.API   : gamma\n"
        "~A\n100.0 12.5\n",
        encoding="utf-8",
    )
    header = scan_header(path)
    assert header.null_value == "-999.25"
    assert header.well["STRT"] == "100.0"
    assert header.identity == "15/9-F-12"
    assert [c["mnemonic"] for c in header.curves] == ["DEPT", "GR"]
    assert header.curves[0]["unit"] == "M"


def test_las_header_value_may_contain_colons(tmp_path):
    """'STRT. 00:00:00 09-Jun-08 : START INDEX' — description is after the last."""
    path = tmp_path / "t.las"
    path.write_text(
        "~Version Information\nVERS. 2.0 : CWLS\n"
        "~Well Information\nSTRT. 00:00:00 09-Jun-08   : START INDEX\n"
        "~Curve Information\nDEPT.M : depth\n~A\n1 2\n",
        encoding="utf-8",
    )
    assert scan_header(path).well["STRT"] == "00:00:00 09-Jun-08"


def test_las3_definition_section_is_read_as_curves_and_data_still_ends_the_header(tmp_path):
    """LAS 3.0 pairs '~X_Definition' with '~X_Data | X_Definition'.

    The data marker names its definition section, so a test for '_DEFINITION'
    that runs first reads the whole data section as curve definitions.
    """
    path = tmp_path / "t3.las"
    path.write_text(
        "~Version Information\nVERS. 3.0 : LAS 3\nDLM. COMMA : delimiter\n"
        "~Well Information Block\nNULL. -999.25 : NULL\nWELL. 15/9-F-14 : well\n"
        "~Phase_Definition_RMDATA\nTIME.s : time\nDEPTH.m : depth\n"
        "~Phase_data_RMDATA | Phase_Definition_RMDATA\n"
        "0.0000,  3017.01\n0.0625,  3017.02\n",
        encoding="utf-8",
    )
    header = scan_header(path)
    assert [c["mnemonic"] for c in header.curves] == ["TIME", "DEPTH"]
    assert header.delimiter == ","
    assert header.null_value == "-999.25"
    assert not header.is_las2_unwrapped


# -- BR-08 ------------------------------------------------------------------


def test_br08_the_sentinel_is_read_from_each_file_not_hard_coded():
    """The delivery declares four different sentinel spellings.

    -999.25, -9999, -999.2500 and -999.25000 all appear, each in the file that
    uses it. Code comparing against the constant '-999.25' would carry three of
    them through as measurements.
    """
    reader = LasCurveHeaderReader(settings=settings())
    declared = set()
    for batch in reader.read(STATIC_LOAD_DATE):
        for index in range(batch.num_rows):
            value = batch.column("null_value_declared")[index].as_py()
            if value:
                declared.add(value)
    assert {"-999.25", "-9999"} <= declared, declared
    assert len(declared) >= 3, f"expected several spellings, got {declared}"


def test_br08_every_sample_carries_the_sentinel_its_own_file_declared():
    """So silver can apply BR-08 without reopening the file."""
    reader = LasSampleReader(settings=settings(), max_files=3)
    rows = 0
    for batch in reader.read(STATIC_LOAD_DATE):
        for index in range(batch.num_rows):
            assert batch.column("null_value_declared")[index].as_py(), "sample with no sentinel"
            rows += 1
    assert rows > 0


def test_br08_bronze_stores_sample_values_as_written():
    """Bronze does not convert the sentinel. Silver does, auditably."""
    reader = LasSampleReader(settings=settings(), max_files=3)
    batch = next(iter(reader.read(STATIC_LOAD_DATE)))
    for name in ("value", "index_value"):
        assert batch.schema.field(name).type == "string"


# -- LAS scheduling ---------------------------------------------------------


def test_las_loads_once_because_the_files_declare_no_usable_date():
    """DATE values include UNKNOWN, empty, and 'Wed Nov 26 21-01-09'."""
    reader = LasCurveHeaderReader(settings=settings())
    assert list(reader.read(datetime.date(2011, 3, 4))) == []
    assert next(iter(reader.read(STATIC_LOAD_DATE))).num_rows > 0


def test_las_records_a_file_it_could_not_parse_rather_than_skipping_it():
    reader = LasCurveHeaderReader(settings=settings())
    for _ in reader.read(STATIC_LOAD_DATE):
        pass
    for path, reason in reader.parse_failures():
        assert reason, f"{path} failed with no reason recorded"
