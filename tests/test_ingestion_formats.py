"""Trajectory, VSP, WITSML, SEG-Y, Eclipse and GEOM readers.

Each test names a format fact that was measured in the delivery. Where the
delivery contradicts SPEC.md, the test asserts the delivery.
"""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from hugin.common.config import Settings
from hugin.ingestion.eclipse import _column_spans, iter_balance_pages
from hugin.ingestion.geom import FaultRecordReader, FixedWidthSpec, parse_fixed_width
from hugin.ingestion.las import STATIC_LOAD_DATE
from hugin.ingestion.segy import (
    HEADER_BYTES,
    SegyHeaderReader,
    parse_binary_header,
    parse_textual_header,
    read_header_bytes,
)
from hugin.ingestion.trajectory import TrajectoryStationReader
from hugin.ingestion.vsp import VspCheckshotReader, identity_from_name
from hugin.ingestion.witsml import (
    WitsmlLogDataReader,
    WitsmlLogHeaderReader,
    WitsmlMessageReader,
    document_namespace,
    survey_document_types,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
LANDING = REPO_ROOT / "data" / "landing"
pytestmark = pytest.mark.skipif(
    not LANDING.exists(), reason="landing tree not extracted; run 'make extract'"
)


def settings() -> Settings:
    return Settings(replay_epoch="2026-08-01T00:00:00Z", repo_root=REPO_ROOT)


# -- TRAJ -------------------------------------------------------------------

TRAJ_DAY = datetime.date(2009, 5, 29)


def test_trajectory_emits_one_row_per_station_on_its_own_date():
    batches = list(TrajectoryStationReader(settings=settings()).read(TRAJ_DAY))
    assert sum(b.num_rows for b in batches) == 469


def test_trajectory_keeps_the_unit_of_every_quantity_it_carries():
    """A dogleg in dega/m and one in dega/30m differ by a factor of thirty."""
    batch = next(iter(TrajectoryStationReader(settings=settings()).read(TRAJ_DAY)))
    assert batch.column("md_uom")[0].as_py() == "m"
    assert batch.column("dls_uom")[0].as_py() == "dega/m"


def test_br10_source_crs_is_null_because_the_source_declares_none():
    """The trajectories declare an azimuth reference, not a CRS.

    aziRef 'grid north', magDeclUsed and gridCorUsed say azimuths are grid
    referenced; none of them says which grid. CLAUDE.md forbids assuming one,
    so the column stays NULL and BR-10 has to get a real answer elsewhere.
    """
    batch = next(iter(TrajectoryStationReader(settings=settings()).read(TRAJ_DAY)))
    assert batch.column("source_crs")[0].as_py() is None
    assert batch.column("azi_ref")[0].as_py() == "grid north"
    assert batch.column("mag_decl_used")[0].as_py() is not None


def test_trajectory_links_stations_through_the_main_wellbore_descriptor():
    batch = next(iter(TrajectoryStationReader(settings=settings()).read(TRAJ_DAY)))
    assert batch.column("name_wellbore")[0].as_py() == "15/9-F-10 - Main Wellbore"
    assert batch.column("_wellbore_uid")[0].as_py() == "15/9-F-10"


# -- VSP --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("stem", "expected"),
    [("checkshot_15_9_19A", "15_9_19A"), ("checkshot_15_9_F_15A", "15_9_F_15A"), ("other", None)],
)
def test_vsp_identity_comes_from_the_file_name_unnormalised(stem, expected):
    """Returned verbatim; BR-12 stage c is what turns it into 15/9-19 A."""
    assert identity_from_name(Path(f"{stem}.txt")) == expected


def test_vsp_reads_both_checkshot_layouts():
    """Four files, two layouts, 676 rows.

    Three files lead with a column header and five whitespace fields; the
    fourth leads with a metadata block and carries Measured Depth, Vertical
    Depth and Two-way Time. An earlier reader required five fields and dropped
    every row of the second layout silently - and that file is the only one
    with measured depth, which is what BR-09's validation needs.
    """
    batches = list(VspCheckshotReader(settings=settings()).read(STATIC_LOAD_DATE))
    total = sum(b.num_rows for b in batches)
    assert total == 676, "both layouts must be read"

    layouts, with_md, uids = set(), 0, set()
    for batch in batches:
        for index in range(batch.num_rows):
            layouts.add(batch.column("layout")[index].as_py())
            if batch.column("md_m")[index].as_py():
                with_md += 1
            uids.add(batch.column("_wellbore_uid")[index].as_py())

    assert layouts == {"columns", "header_block"}
    assert with_md == 191, "the MD-bearing layout must survive"
    assert uids <= {"15/9-19 SR", "15/9-19 A", "15/9-19 BT2", "15/9-F-15 A"}


def test_vsp_header_block_layout_keeps_its_datum():
    """The header names the depth datum, and comparing a checkshot to a survey
    on a different datum is the mistake this data makes available."""
    batches = list(VspCheckshotReader(settings=settings()).read(STATIC_LOAD_DATE))
    datums = {
        batch.column("depth_datum")[i].as_py()
        for batch in batches
        for i in range(batch.num_rows)
        if batch.column("layout")[i].as_py() == "header_block"
    }
    assert datums == {"MSL"}


# -- WITSML -----------------------------------------------------------------


def test_witsml_namespace_and_version_are_read_from_the_document():
    reader = WitsmlMessageReader(settings=settings())
    namespace, version = document_namespace(reader.source_files()[0])
    assert namespace == "http://www.witsml.org/schemas/1series"
    assert version == "1.4.1.1"


def test_witsml_delivery_contains_no_log_documents_at_all():
    """The brief asks for log/mnemonicList. This delivery has neither.

    The log/ directories hold only MetaFileInfo.txt files listing the *names*
    of logs the export never wrote out. Layer 2's throughput demonstration has
    no real curve data behind it, and that is a fact about the dataset rather
    than a gap in this reader.
    """
    types = survey_document_types(settings().landing_dir / "witsml")
    assert types.get("logs", 0) == 0
    assert types["messages"] == 3944


def test_witsml_log_readers_yield_nothing_and_do_not_fail():
    for reader_class in (WitsmlLogHeaderReader, WitsmlLogDataReader):
        reader = reader_class(settings=settings())
        assert list(reader.read(datetime.date(2016, 8, 26))) == []


def test_witsml_messages_are_read_as_the_time_indexed_data_that_does_exist():
    batches = list(WitsmlMessageReader(settings=settings()).read(datetime.date(2016, 8, 26)))
    assert sum(b.num_rows for b in batches) == 60
    batch = batches[0]
    assert batch.column("dtim")[0].as_py().startswith("2016-08-26")
    assert batch.column("_wellbore_uid")[0].as_py() == "15/9-F-12"


def test_witsml_log_data_parser_uses_mnemoniclist_to_name_columns(tmp_path):
    """Exercised on a synthetic document, since the delivery has none.

    Each <data> row is comma-separated and aligned to mnemonicList. Splitting
    without the list, or assuming a column order, mislabels every curve.
    """
    path = tmp_path / "log.xml"
    path.write_text(
        '<?xml version="1.0"?>'
        '<logs xmlns="http://www.witsml.org/schemas/1series" version="1.4.1.1">'
        '<log uidWell="W-1" uidWellbore="B-1" uid="L-1">'
        "<nameWell>15/9-F-12</nameWell><nameWellbore>15/9-F-12</nameWellbore>"
        "<name>Time Log</name><indexType>date time</indexType>"
        "<logData>"
        "<mnemonicList>TIME,ROP,WOB</mnemonicList>"
        "<unitList>s,m/h,klbf</unitList>"
        "<data>2013-12-01T00:00:00Z,12.5,3.2</data>"
        "</logData></log></logs>",
        encoding="utf-8",
    )

    class _Reader(WitsmlLogDataReader):
        def source_files(self):
            return [path]

    batches = list(_Reader(settings=settings()).read(datetime.date(2013, 12, 1)))
    rows = [
        {name: batch.column(name)[i].as_py() for name in ("mnemonic", "unit", "value")}
        for batch in batches
        for i in range(batch.num_rows)
    ]
    assert rows == [
        {"mnemonic": "ROP", "unit": "m/h", "value": "12.5"},
        {"mnemonic": "WOB", "unit": "klbf", "value": "3.2"},
    ]


def test_witsml_log_parser_handles_a_1_3_namespace_without_a_version_test(tmp_path):
    path = tmp_path / "log13.xml"
    path.write_text(
        '<?xml version="1.0"?>'
        '<logs xmlns="http://www.witsml.org/schemas/131" version="1.3.1.1">'
        '<log uidWell="W-1" uidWellbore="B-1" uid="L-1">'
        "<nameWell>15/9-F-12</nameWell><nameWellbore>15/9-F-12</nameWellbore>"
        "<logCurveInfo><mnemonic>ROP</mnemonic><unit>m/h</unit></logCurveInfo>"
        "</log></logs>",
        encoding="utf-8",
    )

    class _Reader(WitsmlLogHeaderReader):
        def source_files(self):
            return [path]

    batch = next(iter(_Reader(settings=settings()).read(datetime.date(2013, 12, 1))))
    assert batch.column("namespace")[0].as_py() == "http://www.witsml.org/schemas/131"
    assert batch.column("mnemonic")[0].as_py() == "ROP"


# -- SEG-Y ------------------------------------------------------------------


def test_segy_reads_exactly_the_header_and_nothing_more():
    """3200 EBCDIC + 400 binary + 240 trace = 3,840 bytes, of a 4 MB file."""
    reader = SegyHeaderReader(settings=settings())
    path = reader.source_files()[0]
    assert HEADER_BYTES == 3840
    assert len(read_header_bytes(path)) == HEADER_BYTES
    assert path.stat().st_size > HEADER_BYTES * 100


def test_segy_textual_header_is_decoded_from_ebcdic():
    """cp037, not ASCII. Decoding as ASCII yields plausible-looking rubbish."""
    reader = SegyHeaderReader(settings=settings())
    raw = read_header_bytes(reader.source_files()[0])
    header = parse_textual_header(raw)
    assert header.splitlines()[0].startswith("C01")
    assert "VSP ACQUISITION PARAMETERS" in header
    assert raw[:80].decode("ascii", errors="replace") != header[:80]


def test_segy_binary_header_fields_are_big_endian_at_standard_offsets():
    reader = SegyHeaderReader(settings=settings())
    fields = parse_binary_header(read_header_bytes(reader.source_files()[0]))
    assert fields["sample_interval_us"] == "1000"
    assert fields["samples_per_trace"] == "5000"
    assert fields["data_sample_format_code"] == "1"  # 4-byte IBM float


def test_segy_identity_survives_a_card_holding_two_labelled_fields():
    """'CLIENT SURVEY : ... WELL : 15/9-F-15A' — splitting on the first colon
    returns the whole card."""
    batch = next(iter(SegyHeaderReader(settings=settings()).read(STATIC_LOAD_DATE)))
    assert batch.column("_source_identifier")[0].as_py() == "15/9-F-15A"
    assert batch.column("_wellbore_uid")[0].as_py() == "15/9-F-15 A"


def test_segy_remote_mode_refuses_a_server_that_ignores_the_range_header():
    import httpx

    reader = SegyHeaderReader(settings=settings(), remote_urls=["http://example.invalid/x.segy"])
    with pytest.raises((RuntimeError, httpx.HTTPError, OSError)):
        list(reader.read(STATIC_LOAD_DATE))


# -- Eclipse ----------------------------------------------------------------


def test_eclipse_columns_come_from_the_header_not_from_whitespace():
    """Oil VAPOUR is blank on every page. A whitespace split files the oil
    total under vapour and shifts every gas column left."""
    subheader = (
        "                           :     LIQUID         VAPOUR         TOTAL   "
        ":       TOTAL    :       FREE      DISSOLVED         TOTAL   :"
    )
    spans = _column_spans(subheader)
    assert spans is not None and len(spans) == 7
    row = (
        " :CURRENTLY IN PLACE       :     21967455.                    21967455."
        ":      81270001. :            0.   3036404371.    3036404371.:"
    )
    values = [row[start:end].strip().strip(":").strip() for start, end in spans]
    assert values[0] == "21967455."
    assert values[1] == "", "vapour is genuinely blank and must stay blank"
    assert values[2] == "21967455."
    assert values[3] == "81270001."
    assert values[6] == "3036404371."


def test_eclipse_pages_carry_report_number_date_and_field_totals():
    reader = FaultOrEclipse = None  # noqa: F841 - keep the import list honest
    from hugin.ingestion.eclipse import EclipseBalanceReader

    path = EclipseBalanceReader(settings=settings()).source_files()[0]
    pages = []
    for page in iter_balance_pages(path):
        pages.append(page)
        if len(pages) == 2:
            break
    assert pages[0]["report_date"] == "2008-01-11"
    assert pages[0]["model_name"] == "2010a Volve simulation model"
    assert pages[0]["pav_bara"] == "329.6"
    assert any(label == "CURRENTLY IN PLACE" for label, _ in pages[0]["rows"])


# -- GEOM -------------------------------------------------------------------


def test_geom_fixed_width_parser_requires_a_declared_spec(tmp_path):
    """The parser the brief asks for, driven by declared positions.

    It has no built-in Volve layout because no readme documents one, and
    guessed positions produce plausible values in the wrong columns.
    """
    path = tmp_path / "fixed.dat"
    path.write_text("-- comment\nABCDEF1234567890\n", encoding="utf-8")
    spec = FixedWidthSpec(fields=(("name", 0, 6), ("value", 6, 16)), source="test")
    assert list(parse_fixed_width(path, spec)) == [{"name": "ABCDEF", "value": "1234567890"}]


def test_geom_reads_the_fault_records_the_delivery_actually_holds():
    """ADDZCORN grid-corner operations, not polygon geometry: no coordinates."""
    batches = list(FaultRecordReader(settings=settings()).read(STATIC_LOAD_DATE))
    assert sum(b.num_rows for b in batches) == 90
    batch = batches[0]
    assert batch.column("keyword")[0].as_py() == "ADDZCORN"
    assert batch.column("z_shift")[0].as_py() == "10.0"
    assert batch.column("index_values")[0].as_py() == "0 62 46 0 1 63 0 62 46 0"
