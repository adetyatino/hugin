"""Stream telemetry into Redpanda, Avro-encoded against a registered schema.

    python -m hugin.streaming.producer --speed 100 --source data/fixtures

``--speed`` is a multiple of real time: 1 replays at the rate the samples were
logged, 100 replays a hundred times faster. It is a pacing control, not a batch
size, so the shape of the load matches a rig's rather than a bulk copy's.

**What it reads.** The parsed WITSML on disk. The real delivery contains no log
curves — ``mnemonicList`` appears in zero of its 10,773 files — so against real
data this producer finds nothing and says so. The load fixture
(``--scale load``) generates that format precisely so there is something to
stream, and every row it produces is fixture data.

**Streaming, not loading.** Files are parsed with ``iterparse`` and yielded
sample by sample. A 200,000-sample document is never held in memory, because the
point of the exercise is throughput under a bounded footprint.

Messages that fail the contract go to the dead-letter topic and the run
continues. A producer that stopped on a bad record would make one malformed
sample an outage.
"""

from __future__ import annotations

import argparse
import io
import json
import struct
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from hugin.streaming.schema import (
    DLQ_SCHEMA,
    DLQ_TOPIC,
    TELEMETRY_SCHEMA,
    TELEMETRY_TOPIC,
    SchemaViolation,
    schema_json,
    validate_record,
)

__all__ = ["ProducerStats", "SchemaRegistry", "iter_telemetry", "run"]

#: Confluent wire format: a magic byte, then the four-byte schema id, then the
#: Avro body. Redpanda's registry speaks the same protocol, so a consumer using
#: any Confluent-compatible deserialiser reads these messages unmodified.
MAGIC_BYTE = 0


@dataclass
class ProducerStats:
    sent: int = 0
    rejected: int = 0
    files: int = 0
    started_at: float = field(default_factory=time.perf_counter)

    @property
    def elapsed_s(self) -> float:
        return max(time.perf_counter() - self.started_at, 1e-9)

    @property
    def rows_per_second(self) -> float:
        return self.sent / self.elapsed_s


class SchemaRegistry:
    """Register a schema and get its id, over the registry's REST API.

    Uses httpx, which is already a declared dependency. The registry is part of
    Redpanda rather than a separate service, so there is nothing extra to run.
    """

    def __init__(self, base_url: str = "http://localhost:8081", timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def register(self, subject: str, schema: dict) -> int:
        import httpx

        payload = {"schema": schema_json(schema), "schemaType": "AVRO"}
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/subjects/{subject}/versions",
                json=payload,
                headers={"Content-Type": "application/vnd.schemaregistry.v1+json"},
            )
            response.raise_for_status()
            return int(response.json()["id"])


def encode_avro(schema: dict, record: dict, schema_id: int) -> bytes:
    """Avro-encode one record in the Confluent wire format.

    ``fastavro`` is not a declared dependency and adding one needs an ADR
    (CLAUDE.md), so the encoder here handles exactly the subset this schema
    uses: records of string, long, double, and unions of null with those. That
    is enough for the contract and small enough to read.
    """
    buffer = io.BytesIO()
    buffer.write(struct.pack(">bI", MAGIC_BYTE, schema_id))
    for field_schema in schema["fields"]:
        _write_field(buffer, field_schema["type"], record.get(field_schema["name"]))
    return buffer.getvalue()


def _write_long(buffer: io.BytesIO, value: int) -> None:
    """Avro zigzag varint."""
    encoded = (value << 1) ^ (value >> 63)
    while True:
        chunk = encoded & 0x7F
        encoded >>= 7
        if encoded:
            buffer.write(bytes([chunk | 0x80]))
        else:
            buffer.write(bytes([chunk]))
            break


def _write_field(buffer: io.BytesIO, field_type, value) -> None:
    if isinstance(field_type, list):  # union, always ["null", X] here
        if value is None:
            _write_long(buffer, field_type.index("null"))
            return
        non_null = next(i for i, t in enumerate(field_type) if t != "null")
        _write_long(buffer, non_null)
        _write_field(buffer, field_type[non_null], value)
        return

    if isinstance(field_type, dict):
        field_type = field_type["type"]

    if field_type == "string":
        raw = str(value).encode("utf-8")
        _write_long(buffer, len(raw))
        buffer.write(raw)
    elif field_type == "long":
        _write_long(buffer, int(value))
    elif field_type == "double":
        buffer.write(struct.pack("<d", float(value)))
    else:  # pragma: no cover - the schema uses nothing else
        raise TypeError(f"unsupported avro type {field_type!r}")


def iter_telemetry(root: Path) -> Iterator[dict]:
    """Yield samples from parsed WITSML log documents, one at a time.

    Uses the same mnemonicList/logData handling as
    :mod:`hugin.ingestion.witsml`: the column names come from the header rather
    than from position, because a fixed order would mislabel every curve the day
    a producer reorders them.
    """
    from lxml import etree

    def local(tag: object) -> str:
        return str(tag).rsplit("}", 1)[-1]

    for path in sorted(root.rglob("*.xml")):
        if not path.is_file():
            continue
        try:
            context = etree.iterparse(str(path), events=("end",))
        except (etree.XMLSyntaxError, OSError):
            continue

        wellbore = None
        mnemonics: list[str] = []
        for _event, element in context:
            tag = local(element.tag)
            if tag == "nameWellbore" and element.text:
                wellbore = element.text.strip()
            elif tag == "nameWell" and element.text and wellbore is None:
                wellbore = element.text.strip()
            elif tag == "mnemonicList" and element.text:
                mnemonics = [m.strip() for m in element.text.split(",")]
            elif tag == "data" and element.text and mnemonics:
                values = [v.strip() for v in element.text.split(",")]
                record: dict = {"source_identifier": wellbore, "wellbore_uid": wellbore}
                for name, value in zip(mnemonics, values, strict=False):
                    if name.upper() == "TIME":
                        record["ts"] = _epoch_millis(value)
                    else:
                        record[name] = _maybe_float(value)
                yield record
                element.clear()


def _epoch_millis(text: str) -> int | None:
    try:
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return int(stamp.timestamp() * 1000)


def _maybe_float(text: str) -> float | None:
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def resolve_identity(record: dict) -> dict:
    """Attach the BR-12 wellbore_uid, keeping what the source wrote.

    The stream carries both: ``source_identifier`` is evidence, ``wellbore_uid``
    is the key everything downstream joins on. A message whose identity cannot
    be resolved keeps a NULL uid and is rejected by the contract rather than
    guessed at — the same rule the batch path follows.
    """
    from hugin.identity.resolver import get_resolver

    written = record.get("source_identifier")
    resolved = get_resolver().resolve("WITSML", written) if written else None
    record["wellbore_uid"] = resolved
    return record


def run(
    source: Path,
    speed: float,
    bootstrap: str,
    registry_url: str,
    limit: int | None = None,
    dry_run: bool = False,
) -> ProducerStats:
    """Stream the telemetry, pacing at ``speed`` times real time."""
    stats = ProducerStats()

    producer = None
    schema_id = 1
    if not dry_run:
        from kafka import KafkaProducer  # type: ignore[import-not-found]

        schema_id = SchemaRegistry(registry_url).register(
            f"{TELEMETRY_TOPIC}-value", TELEMETRY_SCHEMA
        )
        SchemaRegistry(registry_url).register(f"{DLQ_TOPIC}-value", DLQ_SCHEMA)
        producer = KafkaProducer(
            bootstrap_servers=bootstrap,
            linger_ms=20,
            batch_size=1 << 18,
            compression_type="lz4",
            acks=1,
        )

    previous_ts: int | None = None
    for record in iter_telemetry(source):
        if limit is not None and stats.sent + stats.rejected >= limit:
            break

        record = resolve_identity(record)
        try:
            valid = validate_record(record)
        except SchemaViolation as violation:
            stats.rejected += 1
            if producer is not None:
                dead = {
                    "rejected_at": int(time.time() * 1000),
                    "reason": violation.reason,
                    "field": violation.field,
                    "raw_value": None if violation.raw_value is None else str(violation.raw_value),
                    "payload": json.dumps(record, default=str),
                }
                producer.send(DLQ_TOPIC, encode_avro(DLQ_SCHEMA, dead, schema_id))
            continue

        # Pace against the sample's own timestamps, so --speed means what it
        # says regardless of how fast the file parses.
        if speed > 0 and previous_ts is not None:
            gap_s = (valid["ts"] - previous_ts) / 1000.0 / speed
            if gap_s > 0:
                time.sleep(min(gap_s, 1.0))
        previous_ts = valid["ts"]

        if producer is not None:
            producer.send(
                TELEMETRY_TOPIC,
                key=valid["wellbore_uid"].encode("utf-8"),
                value=encode_avro(TELEMETRY_SCHEMA, valid, schema_id),
            )
        stats.sent += 1

    if producer is not None:
        producer.flush()
        producer.close()
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hugin.streaming.producer")
    parser.add_argument("--source", type=Path, default=Path("data/fixtures/witsml"))
    parser.add_argument("--speed", type=float, default=1.0,
                        help="multiple of real time; 100 replays 100x faster")
    parser.add_argument("--bootstrap", default="localhost:19092")
    parser.add_argument("--registry", default="http://localhost:18081")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true",
                        help="parse and validate without producing, for measuring the reader")
    args = parser.parse_args(argv)

    if not args.source.exists():
        raise SystemExit(
            f"{args.source} does not exist. The real delivery contains no WITSML "
            f"log curves, so the load fixture is the only source of telemetry:\n"
            f"  python -m hugin.synthetic generate --scale load --out ./data/fixtures"
        )

    stats = run(args.source, args.speed, args.bootstrap, args.registry,
                limit=args.limit, dry_run=args.dry_run)
    print(f"sent      : {stats.sent:,}")
    print(f"rejected  : {stats.rejected:,} (to {DLQ_TOPIC})")
    print(f"elapsed   : {stats.elapsed_s:.1f}s")
    print(f"throughput: {stats.rows_per_second:,.0f} rows/s")
    print("\nFIXTURE DATA - not Volve measurements.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
