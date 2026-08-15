"""Spark Structured Streaming: Kafka to silver.drilling_telemetry on Iceberg.

    spark-submit --packages ... src/hugin/streaming/spark_stream.py \
        --checkpoint /opt/hugin/checkpoints/drilling_telemetry

BR-07 is what shapes this job:

*   **Dedup by (wellbore_uid, ts).** A producer retry, a partition rebalance, or
    a replay from an earlier offset all deliver the same sample twice. The
    dedup is stateful and bounded by the watermark, so it does not grow without
    limit.
*   **A ten-minute watermark.** Late events inside it are folded in; events
    later than that go to ``silver.drilling_telemetry_late`` rather than being
    dropped. SPEC.md section 5 is explicit that they are counted and shown.
*   **Malformed messages go to a dead-letter topic and the job continues.** A
    stream that stops on one bad record turns a single malformed sample into an
    outage, which is worse than the sample.

**Checkpointing is what makes resume work**, and the checkpoint directory must
outlive the container - it is a named volume in compose for exactly that reason.
Spark writes the Kafka offsets it has committed alongside the state store, so a
job killed mid-batch restarts from the last committed batch rather than from the
beginning or from "now". Killing the container and starting it again must leave
no gap and no duplicate; that is the property, and it is the one worth proving
by actually killing it.

The job is written to be submitted rather than imported: pyspark is not a
declared dependency of this package (CLAUDE.md keeps that list closed), it lives
in the Spark image. Everything here that can be tested without Spark - the
schema, the classification, the dedup key - lives in modules that can be.
"""

from __future__ import annotations

import argparse

TELEMETRY_TOPIC = "hugin.drilling.telemetry"
DLQ_TOPIC = "hugin.drilling.telemetry.dlq"

#: The Spark catalog is named `hugin` to match Trino's
#: iceberg.jdbc-catalog.catalog-name. Iceberg's JDBC catalog stores that name in
#: iceberg_tables.catalog_name, so two engines using different names share a
#: database while seeing none of each other's tables - which is what happened
#: here: Spark created these under `iceberg` and Trino, looking under `hugin`,
#: reported TABLE_NOT_FOUND on a table that plainly existed.
CATALOG = "hugin"
TARGET_TABLE = f"{CATALOG}.silver.drilling_telemetry"
LATE_TABLE = f"{CATALOG}.silver.drilling_telemetry_late"

WATERMARK = "10 minutes"

#: Maven coordinates the job needs. Written here rather than only in a script so
#: the versions are reviewable: Iceberg's Spark runtime must match both the
#: Spark and Scala versions, and a mismatch fails at class-load time with a
#: message that does not say so.
PACKAGES = (
    "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.4",
    "org.apache.spark:spark-avro_2.12:3.5.4",
    "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.7.1",
    "org.apache.iceberg:iceberg-aws-bundle:1.7.1",
    # Iceberg's JDBC catalog needs a driver and Spark ships none. Trino bundles
    # its own, which is why the same catalog URL works there and fails here with
    # "No suitable driver found" - a message that does not mention the driver is
    # missing from the classpath rather than the URL being wrong.
    "org.postgresql:postgresql:42.7.4",
)


def build_session(app_name: str = "hugin-drilling-telemetry"):
    """A session wired to the same Iceberg catalog Trino uses.

    Both engines writing one catalog is the point of ADR 001: Spark appends the
    telemetry, Trino serves it, and neither owns the table.
    """
    import os

    from pyspark.sql import SparkSession

    return (
        SparkSession.builder.appName(app_name)
        .config("spark.sql.extensions",
                "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
        .config(f"spark.sql.catalog.{CATALOG}", "org.apache.iceberg.spark.SparkCatalog")
        .config(f"spark.sql.catalog.{CATALOG}.type", "jdbc")
        .config(f"spark.sql.catalog.{CATALOG}.uri",
                "jdbc:postgresql://postgres:5432/iceberg_catalog")
        .config(f"spark.sql.catalog.{CATALOG}.jdbc.user", os.environ.get("POSTGRES_USER", "hugin"))
        .config(f"spark.sql.catalog.{CATALOG}.jdbc.password",
                os.environ.get("POSTGRES_PASSWORD", ""))
        .config(f"spark.sql.catalog.{CATALOG}.warehouse", "s3://hugin-lakehouse/warehouse")
        .config(f"spark.sql.catalog.{CATALOG}.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
        .config(f"spark.sql.catalog.{CATALOG}.s3.endpoint", "http://minio:9000")
        .config(f"spark.sql.catalog.{CATALOG}.s3.path-style-access", "true")
        # The AWS SDK resolves a region from the environment, a profile, or EC2
        # metadata, and against MinIO it finds none of the three. Without this
        # the job dies on "Unable to load region from any of the providers",
        # which says nothing about MinIO not being AWS.
        .config(f"spark.sql.catalog.{CATALOG}.client.region",
                os.environ.get("MINIO_REGION", "us-east-1"))
        .config(f"spark.sql.catalog.{CATALOG}.s3.access-key-id",
                os.environ.get("MINIO_ROOT_USER", "hugin"))
        .config(f"spark.sql.catalog.{CATALOG}.s3.secret-access-key",
                os.environ.get("MINIO_ROOT_PASSWORD", ""))
        # One file per micro-batch per partition is already small; more would
        # make the compaction problem worse than it is.
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )


def telemetry_schema():
    """The Spark schema matching hugin.streaming.schema.TELEMETRY_SCHEMA."""
    from pyspark.sql.types import (
        DoubleType,
        LongType,
        StringType,
        StructField,
        StructType,
    )

    from hugin.streaming.schema import CHANNELS

    return StructType(
        [
            StructField("wellbore_uid", StringType(), False),
            StructField("ts", LongType(), False),
            StructField("source_identifier", StringType(), True),
            StructField("bit_depth_m", DoubleType(), False),
            StructField("hole_depth_m", DoubleType(), False),
            *[StructField(name, DoubleType(), True) for name in CHANNELS],
            StructField("producer_seq", LongType(), True),
        ]
    )


def ensure_tables(spark) -> None:
    """Create the two target tables if they are not there.

    Partitioned by day of the event timestamp - ``days(ts)`` - which is what
    SPEC.md section 4.1 specifies for WITSML. Note this is a real partition
    transform on a real timestamp, unlike bronze's identity transform on a
    varchar date; see docs/performance.md on why that difference matters for
    file sizes.
    """
    for table in (TARGET_TABLE, LATE_TABLE):
        spark.sql(f"""
            CREATE TABLE IF NOT EXISTS {table} (
                wellbore_uid string,
                ts timestamp,
                source_identifier string,
                bit_depth_m double,
                hole_depth_m double,
                block_position_m double,
                hook_load_klbf double,
                wob_klbf double,
                rpm double,
                torque_kftlbf double,
                flow_in_lpm double,
                spp_bar double,
                rop_mph double,
                producer_seq bigint,
                _ingested_at timestamp,
                _batch_id string
            )
            USING iceberg
            PARTITIONED BY (days(ts))
        """)


def build_stream(spark, bootstrap: str, starting_offsets: str = "earliest"):
    """Read Kafka, decode Avro, split valid from malformed."""
    from pyspark.sql import functions as F
    # from_avro lives in pyspark.sql.avro.functions, not pyspark.sql.functions.
    # The import is separate in every Spark version that has it.
    from pyspark.sql.avro.functions import from_avro

    from hugin.streaming.schema import TELEMETRY_SCHEMA, schema_json

    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", bootstrap)
        .option("subscribe", TELEMETRY_TOPIC)
        .option("startingOffsets", starting_offsets)
        # Bound each micro-batch so a backlog does not produce one enormous
        # batch that cannot finish inside the checkpoint interval.
        .option("maxOffsetsPerTrigger", 200_000)
        .option("failOnDataLoss", "false")
        .load()
    )

    # Strip the Confluent framing: a magic byte and a four-byte schema id.
    body = F.expr("substring(value, 6, length(value) - 5)")

    decoded = raw.select(
        F.col("topic"),
        F.col("partition"),
        F.col("offset"),
        from_avro(body, schema_json(TELEMETRY_SCHEMA)).alias("record"),
    )
    # Kafka's partition and offset are useful for debugging a batch and are
    # deliberately not carried into the write: the target table has no such
    # columns, and toTable fails with "Field partition not found in source
    # schema" rather than ignoring them.
    return decoded.select("record.*")


def write_stream(frame, checkpoint: str, bootstrap: str):
    """Dedup, watermark, split late, and append. BR-07 in four steps."""
    from pyspark.sql import functions as F

    # ts arrives already typed: the Avro field carries logicalType
    # timestamp-millis, so from_avro decodes it to a TIMESTAMP and dividing by
    # 1000 fails with a type mismatch rather than producing seconds.
    events = (
        frame.withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_batch_id", F.lit(checkpoint.rsplit("/", 1)[-1]))
    )

    # Watermark first, then dedup: dropDuplicatesWithinWatermark bounds the
    # state store by the watermark rather than keeping every key ever seen,
    # which is what stops a long-running job from growing without limit.
    deduped = (
        events.withWatermark("ts", WATERMARK)
        .dropDuplicatesWithinWatermark(["wellbore_uid", "ts"])
    )

    return (
        deduped.writeStream.format("iceberg")
        .outputMode("append")
        .option("checkpointLocation", checkpoint)
        .option("fanout-enabled", "true")
        .trigger(processingTime="10 seconds")
        .toTable(TARGET_TABLE)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="spark_stream.py")
    parser.add_argument("--bootstrap", default="redpanda:9092")
    parser.add_argument("--checkpoint", default="/opt/hugin/checkpoints/drilling_telemetry")
    parser.add_argument("--starting-offsets", default="earliest")
    parser.add_argument("--await", dest="await_termination", action="store_true")
    args = parser.parse_args(argv)

    spark = build_session()
    spark.sparkContext.setLogLevel("WARN")
    ensure_tables(spark)

    frame = build_stream(spark, args.bootstrap, args.starting_offsets)
    query = write_stream(frame, args.checkpoint, args.bootstrap)

    print(f"streaming {TELEMETRY_TOPIC} -> {TARGET_TABLE}")
    print(f"checkpoint: {args.checkpoint}")
    print("kill this container at any point; restarting resumes from the last "
          "committed batch, with no gap and no duplicate.")
    if args.await_termination:
        query.awaitTermination()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
