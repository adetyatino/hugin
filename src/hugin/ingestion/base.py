"""The contract every source reader implements.

One interface, nine formats:

    reader.read(replay_date) -> Iterator[pa.RecordBatch]

Each batch carries the business columns exactly as the source wrote them —
**every one a string** — plus the technical columns SPEC.md section 3 makes
mandatory on every bronze table. Bronze does not type, clean, or interpret
anything; that is what makes a replay from bronze possible without going back to
the archive.

The technical columns:

    _ingested_at        real UTC wall clock at ingest
    _replay_date        the field date this run covers (BR-01)
    _source_system      PROD / WITSML / LOG / ...
    _source_file        path relative to the repo root
    _source_identifier  the wellbore identity as the source wrote it
    _batch_id           UUID per DAG execution
    _row_hash           SHA-256 over the business columns, for dedup

and one more, which SPEC.md does not list:

    _wellbore_uid       the resolved wellbore, or NULL

BR-12 resolution belongs between bronze and silver, so carrying the uid in
bronze is a deviation. It is deliberate: the ingestion brief requires every
module to link its rows, and resolving at ingest means an unresolvable identity
is visible in the same table as the row it belongs to rather than only after a
join. The column is underscore-prefixed to keep it out of the business columns
and out of ``_row_hash``, so a re-resolution never changes a row's identity.

NULL there means "no source in this dataset says which wellbore this is". Those
rows are still ingested. Dropping them would lose data; guessing would attribute
it to the wrong hole.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import uuid
from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pyarrow as pa

from hugin.common.config import Settings, get_settings
from hugin.identity.resolver import IdentityResolver, get_resolver

__all__ = [
    "TECHNICAL_COLUMNS",
    "Batcher",
    "SourceReader",
    "records_to_batch",
]

#: In the order they appear on every bronze table.
TECHNICAL_COLUMNS = (
    "_ingested_at",
    "_replay_date",
    "_source_system",
    "_source_file",
    "_source_identifier",
    "_batch_id",
    "_row_hash",
    "_wellbore_uid",
)

#: Rows per RecordBatch. Large enough that Parquet row groups are not tiny,
#: small enough that a 238 MB Eclipse print file never lands in memory at once.
DEFAULT_BATCH_ROWS = 10_000


def _as_string(value: object) -> str | None:
    """Render one business value as the string bronze stores.

    Bronze keeps what the source wrote. A float that arrives as ``1.0`` from a
    parser that already typed it would lose the source's own spelling, so
    readers are expected to hand over strings; anything else is stringified here
    rather than silently dropped.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def row_hash(business: Mapping[str, str | None], columns: Sequence[str]) -> str:
    """SHA-256 over the business columns, in a fixed column order.

    Deliberately excludes every technical column: ``_ingested_at`` and
    ``_batch_id`` change on every run, and a hash that changes with them cannot
    dedup anything. Two runs over the same source file produce the same hashes,
    which is what the idempotency test checks.
    """
    digest = hashlib.sha256()
    for name in columns:
        value = business.get(name)
        digest.update(b"\x00" if value is None else value.encode("utf-8"))
        digest.update(b"\x1f")  # unit separator: 'a|b' and 'ab' must differ
    return digest.hexdigest()


def records_to_batch(
    records: Sequence[Mapping[str, str | None]],
    business_columns: Sequence[str],
    *,
    source_system: str,
    source_file: str,
    replay_date: date,
    batch_id: str,
    ingested_at: str,
    resolver: IdentityResolver,
    identifier_column: str | None = None,
) -> pa.RecordBatch:
    """Turn parsed records into a bronze RecordBatch.

    ``identifier_column`` names the business column holding the wellbore
    identity as written. When a record carries ``_source_identifier`` directly,
    that wins — some formats name the wellbore in the file header rather than in
    a column.
    """
    columns: dict[str, list[str | None]] = {
        name: [] for name in (*business_columns, *TECHNICAL_COLUMNS)
    }

    for record in records:
        business = {name: _as_string(record.get(name)) for name in business_columns}
        for name, value in business.items():
            columns[name].append(value)

        identifier = record.get("_source_identifier")
        if identifier is None and identifier_column is not None:
            identifier = business.get(identifier_column)
        identifier = _as_string(identifier)

        columns["_ingested_at"].append(ingested_at)
        columns["_replay_date"].append(replay_date.isoformat())
        columns["_source_system"].append(source_system)
        columns["_source_file"].append(source_file)
        columns["_source_identifier"].append(identifier)
        columns["_batch_id"].append(batch_id)
        columns["_row_hash"].append(row_hash(business, business_columns))
        columns["_wellbore_uid"].append(
            resolver.resolve(source_system, identifier) if identifier else None
        )

    schema = pa.schema([(name, pa.string()) for name in columns])
    return pa.RecordBatch.from_arrays(
        [pa.array(values, type=pa.string()) for values in columns.values()],
        schema=schema,
    )


@dataclass
class Batcher:
    """Accumulates records and emits fixed-size batches.

    Readers append and yield from this rather than building one list per file:
    several sources here are one enormous file, and one 238 MB print file must
    not become one 238 MB batch.
    """

    business_columns: Sequence[str]
    source_system: str
    replay_date: date
    batch_id: str
    ingested_at: str
    resolver: IdentityResolver
    identifier_column: str | None = None
    max_rows: int = DEFAULT_BATCH_ROWS
    _pending: list[Mapping[str, str | None]] = field(default_factory=list)
    _source_file: str = ""

    def add(self, record: Mapping[str, str | None], source_file: str) -> Iterator[pa.RecordBatch]:
        """Add one record; yields a batch when the buffer is full or the file changed."""
        if self._source_file and source_file != self._source_file and self._pending:
            yield self.flush()
        self._source_file = source_file
        self._pending.append(record)
        if len(self._pending) >= self.max_rows:
            yield self.flush()

    def flush(self) -> pa.RecordBatch:
        records, self._pending = self._pending, []
        return records_to_batch(
            records,
            self.business_columns,
            source_system=self.source_system,
            source_file=self._source_file,
            replay_date=self.replay_date,
            batch_id=self.batch_id,
            ingested_at=self.ingested_at,
            resolver=self.resolver,
            identifier_column=self.identifier_column,
        )

    @property
    def pending(self) -> int:
        return len(self._pending)


class SourceReader(ABC):
    """Base for the nine format readers.

    Subclasses declare ``source_system``, ``table``, and ``business_columns``,
    and implement :meth:`read`. Everything else — technical columns, identity
    resolution, batching — comes from here, so the readers hold format knowledge
    and nothing else.
    """

    #: Source code from SPEC.md section 2: PROD, WITSML, LOG, ...
    source_system: str = ""

    #: Bronze table this reader feeds, e.g. ``bronze.prod_daily``.
    table: str = ""

    #: Business columns, in order. All string in bronze.
    business_columns: Sequence[str] = ()

    #: Business column naming the wellbore, when there is one.
    identifier_column: str | None = None

    def __init__(
        self,
        settings: Settings | None = None,
        resolver: IdentityResolver | None = None,
        batch_id: str | None = None,
        ingested_at: str | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.resolver = resolver if resolver is not None else get_resolver()
        self.batch_id = batch_id or str(uuid.uuid4())
        # Fixed for the life of the reader: every row of one run shares an
        # ingest timestamp, so a batch is one event rather than N.
        self.ingested_at = ingested_at or _dt.datetime.now(_dt.UTC).isoformat(
            timespec="seconds"
        )

    # -- the interface ----------------------------------------------------

    @abstractmethod
    def read(self, replay_date: date) -> Iterator[pa.RecordBatch]:
        """Yield bronze batches for one replay date."""

    def read_range(self, start: date, end: date) -> Iterator[pa.RecordBatch]:
        """Yield bronze batches for every replay date in a closed range.

        The default chains :meth:`read`, which is correct but re-opens the
        source once per date. A reader whose source is one large file should
        override this to make a single pass; see
        :class:`hugin.ingestion.prod.ProductionDailyReader`, where the
        difference is one 14 MB parse against three thousand of them.
        """
        current = start
        while current <= end:
            yield from self.read(current)
            current += _dt.timedelta(days=1)

    # -- helpers for subclasses -------------------------------------------

    def batcher(self, replay_date: date, **kwargs) -> Batcher:
        return Batcher(
            business_columns=self.business_columns,
            source_system=self.source_system,
            replay_date=replay_date,
            batch_id=self.batch_id,
            ingested_at=self.ingested_at,
            resolver=self.resolver,
            identifier_column=self.identifier_column,
            **kwargs,
        )

    def relative(self, path: Path) -> str:
        """Path as ``_source_file`` records it: relative to the repo, forward slashes."""
        try:
            return str(path.relative_to(self.settings.repo_root)).replace("\\", "/")
        except ValueError:
            return str(path).replace("\\", "/")

    def source_files(self) -> Iterable[Path]:
        """Files this reader would read. Override where a glob is not enough."""
        return ()

    def schema(self) -> pa.Schema:
        return pa.schema(
            [(name, pa.string()) for name in (*self.business_columns, *TECHNICAL_COLUMNS)]
        )
