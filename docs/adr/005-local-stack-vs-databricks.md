# ADR 005 — Build the stack locally, even though Volve is already on Databricks

Status: accepted
Date: 2026-08-12
Scope: the whole platform; the compose stack; what Databricks is still used for

## Context

The Volve dataset is published as a Databricks share. Anyone could attach a
cluster, point dbt at it, and have a warehouse over this data in an afternoon.
Instead this project runs MinIO, PostgreSQL, Trino, Airflow, Spark, Redpanda,
and Metabase on a laptop under Docker Compose.

That difference needs a stated reason, because it is a reviewer's obvious
question and — asked in an interview — a question about judgement, not tooling.

## Decision

Build the platform on the local open-source stack. Keep Databricks for the two
jobs it is genuinely better at, and use it for those only.

**Why local:**

- **It demonstrates the components, not the console.** Running an Iceberg
  catalog, wiring a query engine to object storage, and scheduling
  orchestration exercises the parts a managed platform hides. The distinction
  a hiring manager is testing for is between someone who understands catalogs,
  table formats, and orchestration, and someone who can configure a service
  that has already made those decisions. Building it is the only way to show
  the former.
- **A reviewer can run all of it.** `docker compose --profile core up` needs no
  cloud account, no credit card, and no approval. A portfolio that cannot be
  run is read; one that can be run is evaluated.
- **The combination is portable.** Iceberg on S3-compatible storage with Trino
  and Airflow moves to AWS, GCP, Azure, or another vendor with configuration
  changes rather than a rewrite. Building on a managed platform's proprietary
  surface first would make the portability claim in SPEC.md section 12
  unfalsifiable.
- **The costs land where they teach.** Small-file accumulation, compaction,
  partition pruning, and container memory limits are all visible on a laptop
  and all hidden behind a managed autoscaler. `docs/performance.md` exists
  because these costs are visible.

**What Databricks is still used for**, because it is the better tool there:

- **SEG-Y headers.** The seismic volume is 1.17 TB. Reading the first 3,600
  bytes of a file where it already sits — 3,200 bytes of EBCDIC text header,
  400 bytes of binary header, then 240 bytes per trace header — yields the
  survey metadata for a few kilobytes of transfer. Downloading a terabyte to
  read its header would be the wrong answer to a real question, and moving the
  computation to the data is the point of the exercise.
- **The third dbt target.** The data is already there, so
  `dbt build --target databricks` costs nothing to run and produces the
  strongest single claim in the project: the same models, unchanged, build on
  Trino, DuckDB, and Databricks SQL.

## Alternatives considered

**Databricks only.** Fastest to a working warehouse and closest to what many
teams actually operate. Rejected for what it would leave undemonstrated:
catalog and table-format mechanics, orchestration wiring, and the storage-layout
questions that make up SPEC.md section 13. It also puts the project behind a
signup wall for anyone reviewing it, and would have made Delta the natural table
format, inverting ADR 001.

**Local plus a deployed cloud copy on AWS.** Rejected on cost, not merit. A
running EMR or MWAA environment bills continuously for a portfolio nobody is
querying. SPEC.md section 7 replaces this with a documented mapping from each
local component to its AWS equivalent — which conveys the same understanding for
zero dollars per month.

**Local only, no Databricks at all.** Rejected because it would mean either
downloading a terabyte of SEG-Y to read headers, or dropping the seismic source
entirely, and because the third dbt target — free, since the data is already
hosted — is the cheapest strong claim available.

## Consequences

- The stack has a hardware floor: about 6 GB of RAM for the core profile, about
  12 GB with Spark and Redpanda. Compose profiles keep the two separable so a
  machine with 8 GB can still run layer 1.
- Component versions and their compatibility are now this project's problem, in
  particular the Iceberg library versions across Trino and Spark.
- Two environments must be kept working. The dbt project is the shared surface,
  so the no-vendor-functions rule in CLAUDE.md is not a style preference — it is
  what keeps the Databricks target running at all.
- The answer to "why not just use Databricks?" is now a paragraph with reasons
  rather than a shrug. That is the actual deliverable of this ADR.

## When this should be revisited

If this became a production platform with an operations budget rather than a
portfolio, most of the above inverts: a managed catalog and managed compute are
usually the right call when someone is paid to keep them up, and the local stack
would be kept only for CI.
