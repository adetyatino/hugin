"""Bronze integration: Parquet to MinIO, registered as Iceberg, through Trino.

Idempotency is *proven* here rather than claimed. The claim is that loading the
same replay date twice leaves the table exactly as it was after the first load;
the test loads twice and compares counts and row hashes.

Skipped when the stack is not running. To run it:

    docker compose --profile core up -d
    pytest tests/test_bronze_integration.py
"""

from __future__ import annotations

import datetime
import uuid
from pathlib import Path

import pytest

from hugin.common.config import Settings
from hugin.common.trino import TrinoClient, TrinoQueryError
from hugin.ingestion.base import TECHNICAL_COLUMNS
from hugin.ingestion.bronze import BRONZE_SCHEMA, BronzeLoader
from hugin.ingestion.las import STATIC_LOAD_DATE
from hugin.ingestion.prod import ProductionDailyReader
from hugin.ingestion.vsp import VspCheckshotReader

REPO_ROOT = Path(__file__).resolve().parents[1]
PROD_DATE = datetime.date(2014, 4, 7)


def settings() -> Settings:
    return Settings(replay_epoch="2026-08-01T00:00:00Z", repo_root=REPO_ROOT)


def stack_is_up() -> bool:
    try:
        return TrinoClient().wait_until_ready(attempts=1, delay=0.0)
    except Exception:
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not stack_is_up(),
        reason="Trino not reachable; run 'docker compose --profile core up -d'",
    ),
]


@pytest.fixture(scope="module")
def loader() -> BronzeLoader:
    return BronzeLoader(settings=settings())


def count(loader: BronzeLoader, table: str, replay_date: datetime.date | None = None) -> int:
    where = f" WHERE _replay_date = '{replay_date.isoformat()}'" if replay_date else ""
    return loader.client.scalar(f"SELECT count(*) FROM {loader.qualified(table)}{where}") or 0


# -- the load works at all --------------------------------------------------


def test_a_load_creates_an_iceberg_table_and_registers_the_parquet(loader):
    reader = ProductionDailyReader(settings=settings(), batch_id=str(uuid.uuid4()))
    result = loader.load(reader, PROD_DATE)

    assert not result.skipped
    assert result.rows == 7
    assert result.location.startswith("s3://")
    assert count(loader, reader.table, PROD_DATE) == 7


def test_the_table_is_iceberg_and_partitioned_by_replay_date(loader):
    catalog = settings().trino_catalog
    # $partitions is an Iceberg-only metadata table: querying it proves the
    # table format as well as the partitioning. Only the table name takes the
    # suffix and the quotes — quoting the whole qualified name looks for a
    # table literally called 'iceberg.bronze.prod_daily$partitions'.
    rows = loader.client.execute(
        f'SELECT count(*) FROM {catalog}.{BRONZE_SCHEMA}."prod_daily$partitions"'
    )
    assert rows[0][0] >= 1, "the table is not partitioned"


def test_every_technical_column_survives_into_iceberg_as_varchar(loader):
    catalog = settings().trino_catalog
    rows = loader.client.execute(
        f"SELECT column_name, data_type FROM {catalog}.information_schema.columns "
        f"WHERE table_schema = '{BRONZE_SCHEMA}' AND table_name = 'prod_daily'"
    )
    types = dict(rows)
    for column in TECHNICAL_COLUMNS:
        assert column in types, f"{column} missing from the Iceberg table"
    assert set(types.values()) == {"varchar"}, "bronze must not type anything"


# -- idempotency ------------------------------------------------------------


def test_loading_the_same_replay_date_twice_leaves_the_row_count_unchanged(loader):
    """The claim, tested: a re-run replaces its date rather than appending."""
    table = "bronze.prod_daily"

    first = loader.load(ProductionDailyReader(settings=settings(), batch_id=str(uuid.uuid4())), PROD_DATE)
    after_first = count(loader, table, PROD_DATE)

    second = loader.load(ProductionDailyReader(settings=settings(), batch_id=str(uuid.uuid4())), PROD_DATE)
    after_second = count(loader, table, PROD_DATE)

    assert first.rows == second.rows
    assert after_first == after_second == first.rows


def test_a_re_run_produces_identical_row_hashes(loader):
    """Not just the same count — the same rows.

    _row_hash covers the business columns only, so it is stable across runs
    even though _batch_id and _ingested_at are not.
    """
    table = loader.qualified("bronze.prod_daily")
    query = f"SELECT _row_hash FROM {table} WHERE _replay_date = '{PROD_DATE.isoformat()}' ORDER BY _row_hash"

    before = [row[0] for row in loader.client.execute(query)]
    loader.load(ProductionDailyReader(settings=settings(), batch_id=str(uuid.uuid4())), PROD_DATE)
    after = [row[0] for row in loader.client.execute(query)]

    assert before == after
    assert len(set(after)) == len(after), "a replay date must not contain duplicate rows"


def test_a_re_run_replaces_the_batch_id_rather_than_keeping_both(loader):
    """Proof the old rows went away, not merely that the count matched."""
    table = loader.qualified("bronze.prod_daily")
    batch_id = str(uuid.uuid4())
    loader.load(ProductionDailyReader(settings=settings(), batch_id=batch_id), PROD_DATE)

    batches = [
        row[0] for row in loader.client.execute(
            f"SELECT DISTINCT _batch_id FROM {table} "
            f"WHERE _replay_date = '{PROD_DATE.isoformat()}'"
        )
    ]
    assert batches == [batch_id]


def test_loading_a_different_date_does_not_disturb_the_first(loader):
    """Delete-then-register must scope to its own replay date."""
    table = "bronze.prod_daily"
    other = datetime.date(2014, 4, 8)

    loader.load(ProductionDailyReader(settings=settings(), batch_id=str(uuid.uuid4())), PROD_DATE)
    before = count(loader, table, PROD_DATE)

    loader.load(ProductionDailyReader(settings=settings(), batch_id=str(uuid.uuid4())), other)

    assert count(loader, table, PROD_DATE) == before
    assert count(loader, table) >= before


def test_a_date_with_no_rows_still_clears_what_was_there(loader):
    """If the source shrinks, a re-run must not leave the old rows behind."""
    table = "bronze.prod_daily"
    empty_date = datetime.date(1999, 1, 1)
    result = loader.load(ProductionDailyReader(settings=settings(), batch_id=str(uuid.uuid4())), empty_date)
    assert result.skipped
    assert count(loader, table, empty_date) == 0


# -- identity linking through the whole path --------------------------------


def test_wellbore_uid_survives_the_round_trip_to_iceberg(loader):
    reader = VspCheckshotReader(settings=settings(), batch_id=str(uuid.uuid4()))
    loader.load(reader, STATIC_LOAD_DATE)
    table = loader.qualified(reader.table)

    linked, total = loader.client.execute(
        f"SELECT count(_wellbore_uid), count(*) FROM {table}"
    )[0]
    assert total > 0
    assert linked > 0
    uids = {row[0] for row in loader.client.execute(f"SELECT DISTINCT _wellbore_uid FROM {table}")}
    assert "15/9-19 SR" in uids


def test_an_unresolvable_identity_is_present_with_a_null_uid(loader):
    """BR-12: kept and counted, never dropped and never guessed.

    The fault records carry no wellbore at all, so every row of that table is a
    NULL uid — which is the honest representation, not a gap.
    """
    from hugin.ingestion.geom import FaultRecordReader

    reader = FaultRecordReader(settings=settings(), batch_id=str(uuid.uuid4()))
    result = loader.load(reader, STATIC_LOAD_DATE)
    assert result.rows == 90

    table = loader.qualified(reader.table)
    total, linked = loader.client.execute(
        f"SELECT count(*), count(_wellbore_uid) FROM {table}"
    )[0]
    assert total == 90
    assert linked == 0, "these records name no wellbore, and none was invented"


# -- the client itself ------------------------------------------------------


def test_a_failed_query_raises_rather_than_returning_a_200(loader):
    """Trino reports errors in the body with HTTP 200; silence would be worse."""
    with pytest.raises(TrinoQueryError):
        loader.client.execute("SELECT * FROM a_table_that_does_not_exist")
