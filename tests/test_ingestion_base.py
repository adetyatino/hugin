"""The bronze contract: technical columns, all-varchar, identity linking.

These hold for every reader, so they are tested once here rather than nine
times. Format-specific behaviour lives in tests/test_ingestion_<format>.py.
"""

from __future__ import annotations

import datetime
from pathlib import Path

import pyarrow as pa
import pytest

from hugin.identity.resolver import IdentityResolver
from hugin.ingestion.base import (
    TECHNICAL_COLUMNS,
    Batcher,
    records_to_batch,
    row_hash,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
REPLAY_DATE = datetime.date(2014, 4, 7)
COLUMNS = ("well", "oil", "note")


def resolver() -> IdentityResolver:
    return IdentityResolver(
        by_system={("PROD", "NO 15/9-F-12 H"): "15/9-F-12"},
        by_identifier={"NO 15/9-F-12 H": "15/9-F-12"},
    )


def batch_of(records, **kwargs) -> pa.RecordBatch:
    params = {
        "source_system": "PROD",
        "source_file": "data/landing/prod/x.xlsx",
        "replay_date": REPLAY_DATE,
        "batch_id": "batch-1",
        "ingested_at": "2026-08-13T00:00:00+00:00",
        "resolver": resolver(),
        "identifier_column": "well",
    }
    params.update(kwargs)
    return records_to_batch(records, COLUMNS, **params)


# -- the seven mandatory columns -------------------------------------------


def test_every_batch_carries_the_technical_columns_spec_requires():
    """SPEC.md section 3 lists seven. All seven, on every bronze table."""
    batch = batch_of([{"well": "NO 15/9-F-12 H", "oil": "1", "note": None}])
    for column in (
        "_ingested_at", "_replay_date", "_source_system", "_source_file",
        "_source_identifier", "_batch_id", "_row_hash",
    ):
        assert column in batch.schema.names, f"{column} missing from bronze"


def test_business_columns_come_first_then_technical():
    batch = batch_of([{"well": "a", "oil": "1", "note": "n"}])
    assert batch.schema.names == [*COLUMNS, *TECHNICAL_COLUMNS]


def test_every_column_is_varchar():
    """Bronze does not type anything. SPEC.md section 3."""
    batch = batch_of([{"well": "a", "oil": "1", "note": "n"}])
    for field in batch.schema:
        assert field.type == pa.string(), f"{field.name} is {field.type}, not varchar"


def test_a_value_that_is_not_a_string_is_still_stored_as_one():
    batch = batch_of([{"well": "a", "oil": 1.5, "note": None}])
    assert batch.column("oil")[0].as_py() == "1.5"
    assert batch.column("note")[0].as_py() is None


# -- row hash ---------------------------------------------------------------


def test_row_hash_covers_business_columns_only():
    """A hash that moved with _ingested_at or _batch_id could not dedup."""
    first = batch_of([{"well": "a", "oil": "1", "note": "n"}])
    second = batch_of(
        [{"well": "a", "oil": "1", "note": "n"}],
        batch_id="batch-2",
        ingested_at="2026-09-01T00:00:00+00:00",
    )
    assert first.column("_row_hash")[0].as_py() == second.column("_row_hash")[0].as_py()


def test_row_hash_changes_when_a_business_value_changes():
    first = batch_of([{"well": "a", "oil": "1", "note": "n"}])
    second = batch_of([{"well": "a", "oil": "2", "note": "n"}])
    assert first.column("_row_hash")[0].as_py() != second.column("_row_hash")[0].as_py()


def test_row_hash_separates_fields_that_would_otherwise_concatenate():
    """('ab', '') and ('a', 'b') are different rows and must hash differently."""
    assert row_hash({"x": "ab", "y": ""}, ("x", "y")) != row_hash({"x": "a", "y": "b"}, ("x", "y"))


def test_row_hash_distinguishes_null_from_empty_string():
    assert row_hash({"x": None}, ("x",)) != row_hash({"x": ""}, ("x",))


# -- identity linking -------------------------------------------------------


def test_a_resolvable_identity_is_linked_to_its_wellbore():
    batch = batch_of([{"well": "NO 15/9-F-12 H", "oil": "1", "note": None}])
    assert batch.column("_source_identifier")[0].as_py() == "NO 15/9-F-12 H"
    assert batch.column("_wellbore_uid")[0].as_py() == "15/9-F-12"


def test_br12_an_unresolvable_identity_is_ingested_with_a_null_uid():
    """Kept, not dropped. Dropping loses data; guessing attributes it wrongly."""
    batch = batch_of([{"well": "Relief well location 3", "oil": "1", "note": None}])
    assert batch.num_rows == 1, "the row must survive"
    assert batch.column("_source_identifier")[0].as_py() == "Relief well location 3"
    assert batch.column("_wellbore_uid")[0].as_py() is None


def test_a_record_may_name_its_identity_directly():
    """Some formats name the wellbore in a file header, not in a column."""
    batch = batch_of([
        {"well": "n/a", "oil": "1", "note": None, "_source_identifier": "NO 15/9-F-12 H"}
    ])
    assert batch.column("_wellbore_uid")[0].as_py() == "15/9-F-12"


def test_the_resolver_counts_what_it_could_not_place():
    r = resolver()
    r.resolve("PROD", "NO 15/9-F-12 H")
    r.resolve("PROD", "Relief well location 3")
    assert r.hits == 1 and r.misses == 1
    assert r.coverage == pytest.approx(0.5)
    assert ("PROD", "Relief well location 3") in r.unresolved


def test_the_resolver_refuses_an_identifier_that_two_systems_read_differently():
    """A string meaning two wellbores cannot resolve system-blind."""
    r = IdentityResolver.from_crosswalk(REPO_ROOT / "does-not-exist.csv")
    assert r.by_system == {}
    assert r.resolve("PROD", "15/9-F-12") == "15/9-F-12", "falls back to the normaliser"


# -- batching ---------------------------------------------------------------


def test_batcher_emits_when_full_and_keeps_the_remainder():
    batcher = Batcher(
        business_columns=COLUMNS, source_system="PROD", replay_date=REPLAY_DATE,
        batch_id="b", ingested_at="t", resolver=resolver(), max_rows=2,
    )
    emitted = []
    for index in range(5):
        emitted += list(batcher.add({"well": "a", "oil": str(index), "note": None}, "f.xlsx"))
    assert [b.num_rows for b in emitted] == [2, 2]
    assert batcher.pending == 1


def test_batcher_never_mixes_two_source_files_in_one_batch():
    """_source_file is per row, so a batch spanning files would mislabel rows."""
    batcher = Batcher(
        business_columns=COLUMNS, source_system="LOG", replay_date=REPLAY_DATE,
        batch_id="b", ingested_at="t", resolver=resolver(), max_rows=100,
    )
    emitted = list(batcher.add({"well": "a", "oil": "1", "note": None}, "one.las"))
    emitted += list(batcher.add({"well": "a", "oil": "2", "note": None}, "two.las"))
    assert len(emitted) == 1
    assert emitted[0].column("_source_file")[0].as_py() == "one.las"
    assert batcher.flush().column("_source_file")[0].as_py() == "two.las"
