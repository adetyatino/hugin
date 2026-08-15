# ADR 001 — Apache Iceberg as the table format, over Delta Lake and Hudi

Status: accepted
Date: 2026-08-12
Scope: every table in bronze, silver, gold, and mart

## Context

The lakehouse stores tables as files in object storage (MinIO), so a table
format has to supply what a filesystem does not: atomic commits, schema
evolution, snapshot isolation, and enough metadata to prune files at query time.
The three candidates are Iceberg, Delta Lake, and Hudi.

Two constraints of this project decide it, and neither is about raw performance.

**More than one engine must write, not just read.** SPEC.md section 12 commits
the dbt project to building on Trino, DuckDB, and Databricks SQL without model
changes, and section 1 puts Spark Structured Streaming on the same tables that
Trino serves. That is at least two writers and three readers against one set of
tables.

**Partitioning will be wrong at first.** `fct_log_sample` and the WITSML
telemetry are the two large tables, and the right partition layout for them
depends on measurements that have not been taken yet (SPEC.md section 13). A
format that requires rewriting a table to change its partitioning turns a
benchmark result into a migration.

## Decision

Apache Iceberg, with a JDBC catalog on the PostgreSQL instance that already
exists for Airflow's metadata. Trino is the primary writer and server; Spark
writes telemetry; DuckDB and Databricks SQL read the same tables.

Two Iceberg features are load-bearing here rather than incidental:

- **Hidden partitioning.** The partition transform (`days(ts)`,
  `wellbore_code`) is table metadata, not a physical column a query has to
  mention. Query predicates stay in business terms and still prune.
- **Partition evolution.** The layout can change without rewriting history;
  old data keeps its old layout and both are readable. This is what makes it
  safe to partition `fct_log_sample` one way, benchmark it, and change it.

## Alternatives considered

**Delta Lake.** Mature, with the best-in-class implementation on the one
platform this project deliberately does not centre itself on. Outside
Databricks, multi-engine *write* support is the weak spot: Trino's Delta
connector is real but has trailed the Iceberg connector on DML and maintenance
operations, and the story degrades further when Spark and Trino write the same
table. Delta also lacks an equivalent to hidden partitioning — partition columns
are physical, and changing the partitioning of a large table means rewriting it.
The determining factor is that choosing Delta would make Databricks the natural
home of the platform, which inverts the argument in ADR 005.

**Apache Hudi.** The strongest of the three at streaming upserts and incremental
pulls, which maps well onto the WITSML telemetry. It loses on everything else
here: copy-on-write versus merge-on-read, compaction scheduling, and timeline
services are decisions and daemons that have to be understood and operated
before the first row lands, and the query-engine support outside Spark is the
thinnest of the three. For a platform where exactly one table has a streaming
upsert pattern, that is a large fixed cost for a narrow benefit.

**Plain Parquet plus a Hive metastore.** Rejected earlier for the obvious
reason: no atomic commits, so a failed or re-run task leaves a partially written
partition that queries can already see. Idempotent DAG re-runs (SPEC.md section
6) are not achievable without snapshot isolation.

## Consequences

- The catalog is a component to run and back up. The JDBC catalog on the
  existing PostgreSQL keeps this to a schema rather than a new service — the
  reason it was chosen over Hive Metastore or a REST catalog.
- Iceberg's snapshot model accumulates metadata and small files. Snapshot
  expiry and compaction must be scheduled, not left to chance; SPEC.md section
  13 already sets targets for post-compaction file size and count, and the
  before/after numbers are recorded in `docs/performance.md`.
- Every engine in the stack needs a compatible Iceberg library version. That
  version matrix is now a real constraint on upgrades, particularly for Spark.
- The claim "the same dbt models build on three engines" is only credible
  because the format is engine-agnostic. This ADR is what makes that claim
  cheap rather than heroic.

## When this should be revisited

If the platform ever consolidates onto Databricks as its only compute, the
multi-engine argument disappears and Delta's tighter integration there would
win. Also if a table develops a genuine streaming-upsert-heavy workload where
Hudi's merge-on-read profile measurably beats Iceberg's — that is a benchmark
question, and it belongs in `docs/performance.md`, not in an opinion.
