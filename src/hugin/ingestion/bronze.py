"""Bronze load: Parquet to MinIO, then registered as Iceberg through Trino.

Two steps, deliberately not one:

1.  The reader's RecordBatches are written as Parquet objects into MinIO under
    ``bronze/<table>/replay_date=<date>/run=<batch_id>/``.
2.  Trino registers those objects into an Iceberg table with
    ``ALTER TABLE ... EXECUTE add_files``. The bytes are not rewritten and do
    not pass through the engine.

Inserting through the engine instead would work and would be slower for no
gain; registering is what makes "write the file, then catalogue it" a real
pattern rather than a description of one.

**Idempotency** is the property this module exists to guarantee, and it is
proven by tests/test_bronze_integration.py rather than asserted here. The
mechanism is delete-then-register, per replay date:

    DELETE FROM <table> WHERE _replay_date = <date>
    ALTER TABLE <table> EXECUTE add_files(location => <this run's prefix>)

Each run writes to a prefix keyed by its own batch id, so re-running a date
never rewrites objects an earlier run's snapshot still references — Iceberg
would then point at files that no longer exist. The old rows are deleted
logically and their files age out through snapshot expiry, which is the
maintenance ADR 001 already committed to scheduling.

Every column is ``varchar``, including the technical ones. SPEC.md section 3:
bronze does not type anything.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import date

import pyarrow as pa
import pyarrow.parquet as pq
from pyarrow import fs as pafs

from hugin.common.config import Settings, get_settings
from hugin.common.trino import TrinoClient
from hugin.ingestion.base import SourceReader

__all__ = ["BronzeLoader", "LoadResult"]

BRONZE_SCHEMA = "bronze"


@dataclass
class LoadResult:
    table: str
    replay_date: date
    rows: int
    files: int
    batch_id: str
    location: str
    skipped: bool = False
    note: str = ""

    def __str__(self) -> str:
        if self.skipped:
            return f"{self.table:28} {self.replay_date}  no rows"
        return (
            f"{self.table:28} {self.replay_date}  {self.rows:>9,} rows  "
            f"{self.files} file(s)"
        )


@dataclass
class BronzeLoader:
    """Writes a reader's output to MinIO and registers it in Iceberg."""

    settings: Settings = field(default_factory=get_settings)
    client: TrinoClient | None = None
    #: Rows per Parquet file. Small files are the thing compaction exists to
    #: fix; this keeps a single day's load from producing hundreds of them.
    rows_per_file: int = 250_000

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = TrinoClient(
                host=self.settings.trino_host,
                port=self.settings.trino_port,
                user=self.settings.trino_user,
                catalog=self.settings.trino_catalog,
                schema=BRONZE_SCHEMA,
            )

    # -- object storage ----------------------------------------------------

    def filesystem(self) -> pafs.S3FileSystem:
        endpoint = self.settings.minio_endpoint
        return pafs.S3FileSystem(
            access_key=self.settings.minio_root_user,
            secret_key=self.settings.minio_root_password.get_secret_value(),
            endpoint_override=endpoint.replace("http://", "").replace("https://", ""),
            scheme="http" if endpoint.startswith("http://") else "https",
            # MinIO has no per-bucket DNS, so addressing must be path style.
            force_virtual_addressing=False,
        )

    def prefix_for(self, table: str, replay_date: date, batch_id: str) -> str:
        name = table.split(".")[-1]
        return (
            f"{self.settings.minio_bucket}/bronze/{name}/"
            f"replay_date={replay_date.isoformat()}/run={batch_id}"
        )

    # -- Iceberg -----------------------------------------------------------

    def ensure_schema(self) -> None:
        self.client.execute(
            f"CREATE SCHEMA IF NOT EXISTS {self.settings.trino_catalog}.{BRONZE_SCHEMA}"
        )

    def ensure_table(self, table: str, schema: pa.Schema) -> None:
        """Create the Iceberg table if it does not exist. All columns varchar.

        Partitioned by ``_replay_date`` for the daily sources, which is what
        makes the delete-then-register cycle touch one day's files rather than
        rewriting the table.
        """
        name = table.split(".")[-1]
        columns = ",\n  ".join(f'"{field.name}" varchar' for field in schema)
        self.client.execute(
            f"CREATE TABLE IF NOT EXISTS {self.settings.trino_catalog}.{BRONZE_SCHEMA}.{name} (\n"
            f"  {columns}\n"
            f") WITH (format = 'PARQUET', partitioning = ARRAY['_replay_date'])"
        )

    def qualified(self, table: str) -> str:
        return f"{self.settings.trino_catalog}.{BRONZE_SCHEMA}.{table.split('.')[-1]}"

    # -- the load ----------------------------------------------------------

    def load(self, reader: SourceReader, replay_date: date) -> LoadResult:
        """Write one reader's rows for one replay date, and register them."""
        filesystem = self.filesystem()
        prefix = self.prefix_for(reader.table, replay_date, reader.batch_id)
        schema = reader.schema()

        rows = 0
        files = 0
        writer: pq.ParquetWriter | None = None
        try:
            for batch in reader.read(replay_date):
                if batch.num_rows == 0:
                    continue
                if writer is None or rows // self.rows_per_file != (rows - batch.num_rows) // self.rows_per_file:
                    if writer is not None:
                        writer.close()
                        writer = None
                if writer is None:
                    files += 1
                    path = f"{prefix}/part-{files:05d}.parquet"
                    writer = pq.ParquetWriter(
                        path, schema, filesystem=filesystem, compression="zstd"
                    )
                writer.write_batch(batch.cast(schema) if batch.schema != schema else batch)
                rows += batch.num_rows
        finally:
            if writer is not None:
                writer.close()

        self.ensure_schema()
        self.ensure_table(reader.table, schema)
        qualified = self.qualified(reader.table)

        # Delete first, always — including when this run produced no rows, so
        # that re-running a date after the source shrank leaves nothing behind.
        self.client.execute(
            f"DELETE FROM {qualified} WHERE _replay_date = '{replay_date.isoformat()}'"
        )

        if rows == 0:
            return LoadResult(
                table=reader.table, replay_date=replay_date, rows=0, files=0,
                batch_id=reader.batch_id, location=f"s3://{prefix}", skipped=True,
                note="reader produced no rows for this replay date",
            )

        self._register(qualified, prefix, reader, schema)
        return LoadResult(
            table=reader.table, replay_date=replay_date, rows=rows, files=files,
            batch_id=reader.batch_id, location=f"s3://{prefix}",
        )

    def _register(
        self, qualified: str, prefix: str, reader: SourceReader, schema: pa.Schema
    ) -> None:
        """Register the run's Parquet into the partitioned table, via a stage.

        ``add_files`` is how Parquet already in object storage becomes an
        Iceberg table without the bytes passing through the engine — but Trino
        refuses it on a partitioned table:

            INVALID_PROCEDURE_ARGUMENT: The procedure does not support
            partitioned tables

        and SPEC.md section 4.1 requires bronze to be partitioned by
        ``_replay_date``. So the registration happens in two hops: the objects
        are registered into an unpartitioned stage table, which costs nothing
        and rewrites nothing, and the engine then writes them into the
        partitioned table with one columnar INSERT ... SELECT.

        One engine-side rewrite per load, rather than one insert per row.

        Dropping the stage deletes the objects it registered: after add_files
        the table owns them, and Iceberg purges data files on DROP. So the
        staged Parquet is not a durable copy - the Iceberg table is. Anything
        reading these rows outside Trino (the DuckDB dbt target, for one)
        must read the table's own data files under warehouse/, not this
        staging prefix.
        """
        stage = f"{qualified}__stage_{reader.batch_id.replace('-', '')[:12]}"
        columns = ",\n  ".join(f'"{field.name}" varchar' for field in schema)
        # Clear any stage a killed run left behind. The drop below is in a
        # finally block, but a process killed outright never reaches it, and one
        # such orphan was found in the warehouse holding a full copy of its
        # run's rows - visible in every information_schema listing and swept up
        # by the compaction script as if it were a real table.
        self._drop_orphan_stages(qualified)
        self.client.execute(f"DROP TABLE IF EXISTS {stage}")
        self.client.execute(
            f"CREATE TABLE {stage} (\n  {columns}\n) WITH (format = 'PARQUET')"
        )
        try:
            self.client.execute(
                f"ALTER TABLE {stage} EXECUTE add_files("
                f"location => 's3://{prefix}', format => 'PARQUET')"
            )
            # ORDER BY the partition column, or a backfill fails with
            # ICEBERG_TOO_MANY_OPEN_PARTITIONS: the writer keeps one file open
            # per partition it is currently writing, and a range load touches
            # one partition per day. Sorted input means one open writer at a
            # time instead of three thousand.
            self.client.execute(
                f"INSERT INTO {qualified} SELECT * FROM {stage} ORDER BY _replay_date"
            )
        finally:
            self.client.execute(f"DROP TABLE IF EXISTS {stage}")

    def _drop_orphan_stages(self, qualified: str) -> list[str]:
        """Remove stage tables an earlier run failed to clean up."""
        catalog, schema, table = qualified.split(".")
        pattern = f"{table}__stage_%"
        orphans = [
            row[0] for row in self.client.execute(
                f"SELECT table_name FROM {catalog}.information_schema.tables "
                f"WHERE table_schema = '{schema}' AND table_name LIKE '{pattern}'"
            )
        ]
        for name in orphans:
            self.client.execute(f'DROP TABLE IF EXISTS {catalog}.{schema}."{name}"')
        return orphans

    def load_range(self, reader: SourceReader, start: date, end: date) -> LoadResult:
        """Load a whole date range in one pass, for backfill.

        Same guarantees as :meth:`load`, scoped to the range instead of a day:
        the delete covers ``[start, end]`` and the register happens once. Rows
        keep their own ``_replay_date``, so a range load and a sequence of daily
        loads produce the same table — which is what makes a backfill and a
        replay interchangeable rather than two code paths that agree by
        accident.
        """
        filesystem = self.filesystem()
        prefix = self.prefix_for(reader.table, start, reader.batch_id) + f"__to_{end.isoformat()}"
        schema = reader.schema()

        rows = 0
        files = 0
        writer: pq.ParquetWriter | None = None
        try:
            for batch in reader.read_range(start, end):
                if batch.num_rows == 0:
                    continue
                if writer is None:
                    files += 1
                    writer = pq.ParquetWriter(
                        f"{prefix}/part-{files:05d}.parquet", schema,
                        filesystem=filesystem, compression="zstd",
                    )
                writer.write_batch(batch.cast(schema) if batch.schema != schema else batch)
                rows += batch.num_rows
        finally:
            if writer is not None:
                writer.close()

        self.ensure_schema()
        self.ensure_table(reader.table, schema)
        qualified = self.qualified(reader.table)
        self.client.execute(
            f"DELETE FROM {qualified} WHERE _replay_date >= '{start.isoformat()}' "
            f"AND _replay_date <= '{end.isoformat()}'"
        )
        if rows == 0:
            return LoadResult(
                table=reader.table, replay_date=start, rows=0, files=0,
                batch_id=reader.batch_id, location=f"s3://{prefix}", skipped=True,
                note=f"no rows between {start} and {end}",
            )
        self._register(qualified, prefix, reader, schema)
        return LoadResult(
            table=reader.table, replay_date=start, rows=rows, files=files,
            batch_id=reader.batch_id, location=f"s3://{prefix}",
            note=f"range {start} .. {end}",
        )

    def load_all(
        self, readers: Iterable[SourceReader], replay_dates: Iterable[date]
    ) -> Iterator[LoadResult]:
        dates = list(replay_dates)
        for reader in readers:
            for replay_date in dates:
                yield self.load(reader, replay_date)

    # -- reporting ---------------------------------------------------------

    def table_counts(self) -> list[tuple[str, int, int, float]]:
        """(table, rows, rows with a wellbore_uid, percent) for every bronze table."""
        catalog = self.settings.trino_catalog
        tables = [
            row[0] for row in self.client.execute(
                f"SELECT table_name FROM {catalog}.information_schema.tables "
                f"WHERE table_schema = '{BRONZE_SCHEMA}' ORDER BY table_name"
            )
        ]
        out: list[tuple[str, int, int, float]] = []
        for table in tables:
            total, linked = self.client.execute(
                f"SELECT count(*), count(_wellbore_uid) FROM {catalog}.{BRONZE_SCHEMA}.{table}"
            )[0]
            percent = (linked / total * 100) if total else 0.0
            out.append((table, total, linked, percent))
        return out
