"""PROD reader, against the format facts in docs/data-dictionary.md.

Every assertion here is about something measured in the delivery, not something
SPEC.md predicted. Where the two differ the data wins, and the test says so.
"""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from hugin.common.config import Settings
from hugin.ingestion.prod import (
    ProductionDailyReader,
    ProductionMonthlyReader,
    excel_serial_to_date,
    out_of_replay_window,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = REPO_ROOT / "data" / "landing" / "prod" / "Production_data" / "Volve production data.xlsx"
pytestmark = pytest.mark.skipif(
    not WORKBOOK.exists(), reason="production workbook not extracted; run 'make extract'"
)


def settings() -> Settings:
    return Settings(replay_epoch="2026-08-01T00:00:00Z", repo_root=REPO_ROOT)


# -- the dual date encoding -------------------------------------------------


@pytest.mark.parametrize(
    ("serial", "expected"),
    [
        ("39326", datetime.date(2007, 9, 1)),   # first row in the sheet
        ("41736", datetime.date(2014, 4, 7)),
        ("42705", datetime.date(2016, 12, 1)),  # last row in the sheet
    ],
)
def test_excel_serials_decode_to_the_dates_the_sheet_means(serial, expected):
    assert excel_serial_to_date(serial) == expected


def test_the_1900_leap_year_bug_is_reproduced_not_corrected():
    """Excel counts a 29 Feb 1900 that never existed. Reading from 1899-12-30
    reproduces it, which is what makes serial 39326 land on 2007-09-01."""
    assert excel_serial_to_date("1") == datetime.date(1899, 12, 31)
    assert excel_serial_to_date("60") == datetime.date(1900, 2, 28)


@pytest.mark.parametrize("value", ["", "   ", "not a date", "0", "-5"])
def test_a_cell_that_is_not_a_serial_yields_no_date(value):
    assert excel_serial_to_date(value) is None


# -- daily ------------------------------------------------------------------


def test_daily_reads_only_the_requested_replay_date():
    batches = list(ProductionDailyReader(settings=settings()).read(datetime.date(2014, 4, 7)))
    assert batches, "2014-04-07 has production rows"
    for batch in batches:
        for index in range(batch.num_rows):
            assert excel_serial_to_date(batch.column("dateprd")[index].as_py()) == datetime.date(2014, 4, 7)
            assert batch.column("_replay_date")[index].as_py() == "2014-04-07"


def test_daily_stores_the_serial_as_written_rather_than_a_converted_date():
    """Bronze keeps what the file holds. The conversion is silver's job."""
    batch = next(iter(ProductionDailyReader(settings=settings()).read(datetime.date(2014, 4, 7))))
    assert batch.column("dateprd")[0].as_py() == "41736"


def test_daily_carries_all_twenty_four_source_columns():
    batch = next(iter(ProductionDailyReader(settings=settings()).read(datetime.date(2014, 4, 7))))
    assert len(ProductionDailyReader.business_columns) == 24
    for name in ("well_bore_code", "bore_oil_vol", "bore_wi_vol", "flow_kind", "well_type"):
        assert name in batch.schema.names


def test_daily_links_every_row_to_a_wellbore():
    """All seven producing wellbores carry an NPD code, so all seven resolve."""
    batch = next(iter(ProductionDailyReader(settings=settings()).read(datetime.date(2014, 4, 7))))
    uids = [batch.column("_wellbore_uid")[i].as_py() for i in range(batch.num_rows)]
    assert all(uids), f"unresolved production identity: {uids}"


def test_daily_preserves_the_scandinavian_facility_name():
    """MÆRSK INSPIRER. Read as UTF-8; a cp1252 read would corrupt it."""
    batch = next(iter(ProductionDailyReader(settings=settings()).read(datetime.date(2014, 4, 7))))
    assert batch.column("npd_facility_name")[0].as_py() == "MÆRSK INSPIRER"


def test_daily_yields_nothing_for_a_date_with_no_production():
    assert list(ProductionDailyReader(settings=settings()).read(datetime.date(1999, 1, 1))) == []


# -- monthly ----------------------------------------------------------------


def test_monthly_is_emitted_once_per_month_on_the_first():
    reader = ProductionMonthlyReader(settings=settings())
    first = list(reader.read(datetime.date(2014, 4, 1)))
    assert sum(b.num_rows for b in first) == 7
    for day in (2, 7, 30):
        assert list(reader.read(datetime.date(2014, 4, day))) == [], (
            "a monthly row emitted on more than one day would double-count"
        )


def test_monthly_skips_the_units_row_that_sits_under_the_header():
    """Row 2 holds 'hrs' and 'Sm3'. Those are units, not a record."""
    batch = next(iter(ProductionMonthlyReader(settings=settings()).read(datetime.date(2014, 4, 1))))
    years = {batch.column("year")[i].as_py() for i in range(batch.num_rows)}
    assert years == {"2014"}
    assert "hrs" not in {batch.column("on_stream")[i].as_py() for i in range(batch.num_rows)}


def test_monthly_column_named_with_a_space_is_reachable():
    """The sheet writes 'Wellbore name'; the daily sheet writes WELL_BORE_CODE."""
    batch = next(iter(ProductionMonthlyReader(settings=settings()).read(datetime.date(2014, 4, 1))))
    names = [batch.column("wellbore_name")[i].as_py() for i in range(batch.num_rows)]
    assert all(names), "the wellbore column must not be empty"
    assert "15/9-F-1 C" in names


def test_monthly_links_every_row_to_a_wellbore():
    batch = next(iter(ProductionMonthlyReader(settings=settings()).read(datetime.date(2014, 4, 1))))
    uids = [batch.column("_wellbore_uid")[i].as_py() for i in range(batch.num_rows)]
    assert all(uids), f"unresolved monthly identity: {uids}"


# -- what the source does that SPEC did not predict -------------------------


def test_production_extends_beyond_the_replay_window():
    """Measured, and reported rather than resolved.

    SPEC.md section 2 puts field life at 2008-06 .. 2016-09. Production data
    runs 2007-09 .. 2016-12, so some rows can never be selected by a
    replay-driven run. Which of the two is wrong is a decision, not a parse.
    """
    counts = out_of_replay_window(
        settings().landing_dir, datetime.date(2008, 6, 1), datetime.date(2016, 9, 30)
    )
    assert counts["before"] == 766
    assert counts["after"] == 9
    assert counts["inside"] == 14859
    assert counts["unparseable"] == 0
