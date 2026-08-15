# Measured performance

Every number here was produced by `scripts/benchmark.py` against the running
compose stack, on the machine described below. Targets come from `SPEC.md`
section 13. Where a target was missed, or met for a reason that will not hold,
the analysis says so — SPEC.md section 13 asks for that explicitly, and an
honest miss is worth more in an interview than a polished number.

**Measured**: 2026-08-13.
**Machine**: Windows 11, Docker Desktop, single-node compose stack (MinIO,
PostgreSQL, Trino 476, Metabase). Trino has one worker, which is the
coordinator.

## Against SPEC.md section 13

| Metric | Target | Measured | Met |
|---|---|---|:--:|
| Ingest bronze, one replay day | < 60 s | **53.3 s** | yes |
| `dbt build` full, Trino | < 8 min | **67.4 s** | yes |
| `dbt build`, DuckDB | < 90 s | **60.2 s** | yes |
| Backfill 24 replay months | < 25 min | **26.2 s** | yes |
| Depth-range query on `fct_log_sample` | < 3 s | **0.145 s** | yes |
| — with partition pruning active | pruning active | **not partitioned; whole table scanned** | **no** |
| Streaming throughput, producer path | > 20,000 rows/s | **15,712 rows/s** | **no** |
| Iceberg file size after compaction | 128–512 MB | **6.9 KB** on the worst table | **no** |
| File count after compaction | down > 70% | **0.1%** overall | **no** |

Every row in SPEC.md section 13 is now measured. Four targets are met outright,
one is met on latency and missed on the mechanism it was meant to demonstrate,
and three miss. The analysis for each is below. Two of the three misses share a
cause, and it is the same cause as the half-miss — the partitioning decision in
SPEC.md section 4.1, which is now the single most consequential open item in
this repository.

## Ingest, one replay day — 53.3 s against a 60 s target

Met, but the margin is not where it looks. The breakdown for 2014-04-07, which
loaded **38 rows**:

| Reader | Rows | Seconds |
|---|---:|---:|
| `bronze.prod_daily` | 7 | 9.2 |
| `bronze.ddr_activity` | 31 | 6.4 |
| `bronze.witsml_message` | 0 | 7.7 |
| `bronze.sim_summary` | 0 | 5.4 |
| `bronze.trajectory_station` | 0 | 5.1 |
| `bronze.witsml_log_header` | 0 | 3.4 |
| `bronze.witsml_log_data` | 0 | 3.3 |
| the remaining six | 0 | 1.9–2.3 each |

**Almost none of that is data.** Thirty-eight rows do not take 53 seconds to
write. The cost is two fixed charges per reader:

1. **A Trino round trip whether or not there is anything to load.** Every reader
   issues `DELETE FROM ... WHERE _replay_date = ...` before it registers
   anything, including when it produced no rows — deliberately, so that
   re-running a date after the source shrank cannot leave stale rows behind. On
   an empty day that delete is the entire cost, about 2 seconds, thirteen times
   over.
2. **Scanning the source to discover there is nothing there.** `witsml_message`
   spends 7.7 seconds opening 4,094 XML files to find no message dated
   2014-04-07. `sim_summary` spends 5.4 seconds streaming a 238 MB print file
   for the same answer. Neither reader has an index; each is a full scan per
   replay date.

So the number scales the wrong way. It is nearly flat in data volume — a day
with 100× the rows would still be about 50 seconds — and linear in *number of
sources* and *size of source files*. Adding four more readers would breach the
target while adding no data at all.

**What would fix it**, in the order worth doing:

- **Index the date-bearing sources once.** The Eclipse print file has 3,000
  balance pages with known dates; the WITSML messages have a date per document.
  Building a date → file offset index at extraction time turns a 7.7-second
  scan into a lookup. This is the big one, and it is the same fix for both.
- **Skip the delete when the reader has nothing and the partition is empty.** A
  cheap `count(*)` for the partition costs less than a delete, and the delete
  is only needed if something is there.
- **Let readers declare which dates they can produce.** Ten of the thirteen
  readers are static-load or date-scoped and could answer "not this date"
  without opening a file.

## `dbt build` — 67.4 s on Trino, 60.2 s on DuckDB

Both inside target, and the DuckDB figure matters most: it is what CI runs, and
SPEC.md section 13 sets 90 seconds for it precisely so CI does not need a
lakehouse.

**Both numbers went up since the first measurement**, and the reason is worth
recording rather than quietly overwriting. The earlier figures were 47.7 s and
35.4 s over **23 models**; the project now builds **25 models and 107 tests**,
and the two new models are `fct_drilling_state` — which reads
`silver.drilling_telemetry`, a table Spark owns — and `mart_drilling_efficiency`
on top of it. The DuckDB target grew more in relative terms (+70%) because it
reads that table's Parquet across the MinIO S3 API rather than through Trino's
already-warm Iceberg metadata.

The DuckDB headroom is now 30 seconds rather than 55. That is still comfortable,
but it is worth saying plainly that the CI target is the one that will be
breached first, and that it will be breached by adding models rather than by
adding data.

The Trino build spends most of its time on
`silver_production_daily` (14,859 rows through a window function for the
`_row_hash` dedup) and `mart_well_performance` (the same rows again with a
per-wellbore first-oil join). Neither is close to a limit.

The DuckDB build being *faster* than Trino on the same models is not a surprise
and is worth understanding: DuckDB reads the Parquet files directly in-process,
while Trino pays coordinator planning, worker scheduling and Iceberg metadata
resolution per statement. At this data size that fixed cost dominates. The
ordering would reverse well before the data got large.

## Backfill, 24 replay months — 26.2 s against a 25 minute target

Met by a factor of fifty-seven, and the reason is a design decision rather than
speed: `BronzeLoader.load_range` makes **one pass** over the source and **one**
registration for the whole range, where a naive backfill would run the daily
path 730 times.

The comparison is worth stating plainly. The daily path costs ~9 seconds per
date for production alone; 730 dates would be about 110 minutes, missing the
target by four times. The same rows loaded as a range take 26 seconds.

Second pass, immediately after: **23.9 s**, and the table state was identical —
same row counts, same distinct `_row_hash` counts, same checksum over the
hashes. That is the idempotency claim in SPEC.md section 6, measured rather than
asserted.

| Pass | Seconds | `prod_daily` | `prod_monthly` |
|---|---:|---:|---:|
| 1 | 26.2 | 14,859 rows | 497 rows |
| 2 | 23.9 | 14,859 rows | 497 rows |

**A caveat on what was backfilled.** The 24 months cover 2008-06-01 to
2010-05-31, and the readers exercised are the two production readers — the only
sources with data spread across every month of the range. DDR, trajectory and
WITSML have their own arrival patterns and are loaded by
`hugin_wellbore_static`. A backfill covering all thirteen readers over 24 months
would be dominated by the per-date scans described above, and would not meet the
25-minute target until those are indexed. That is the same finding as the
ingest-day analysis, and it is the one thing on this page that would fail under
a larger load.

## Depth-range query — 0.145 s against 3 s, and no pruning at all

**Half met, and the interesting half is the one that failed.**

The query, run five times, median reported:

```sql
select count(*) as samples, avg(value) as mean_value
from gold.fct_log_sample
where depth_m between 3000 and 3200
```

| | |
|---|---|
| Rows returned | 2,033 of 30,421 |
| Times (s) | 0.145, 0.151, 0.135, 0.145, 0.131 → **median 0.145 s** |
| Target | < 3 s |

Comfortably inside target. And the `EXPLAIN ANALYZE` says why that number means
almost nothing:

```
└─ ScanFilterProject[table = iceberg:gold.fct_log_sample$data,
                     filterPredicate = (depth_m BETWEEN 3000.0 AND 3200.0)]
       Input: 30421 rows (474.37kB), Filtered: 93.32%,
       Physical input: 1.23MB, Splits: 1
```

**Every row was read and 93.32% were thrown away after reading.** There is no
pruning, because there is nothing to prune: `SHOW CREATE TABLE` confirms
`fct_log_sample` has no `partitioning` property at all, and
`fct_log_sample$files` reports the entire table as **one 1.29 MB file, one
split**. The 0.145 seconds is the time to read 1.29 MB and filter it in memory.

So the target as SPEC.md section 13 writes it — *"< 3 s, partition pruning
active"* — is met on the first clause and failed on the second, and the second
is the one that was worth measuring. A latency number produced by scanning
everything says how small the table is, not how well it is laid out.

**Two things would have to change**, and they are separable:

1. **Partition the table.** `fct_log_sample`'s grain is
   wellbore x source_file x curve x depth, and the natural partition is
   `source_file` (one logging run) or a depth bucket. Neither is set. Iceberg
   would then skip files by manifest statistics before opening any of them —
   which is what "pruning active" means and what the `EXPLAIN ANALYZE` would
   have to show as a reduced `Physical input` rather than a high `Filtered`.
2. **Load enough data for it to matter.** 30,421 rows come from a deliberately
   bounded LAS load (`--max-las-files 8`); the full delivery is on the order of
   ten million rows. At 1.29 MB in a single file, a perfectly partitioned table
   and an unpartitioned one would both answer in well under a second, and the
   measurement still would not distinguish them.

Both are needed. Doing (1) without (2) produces a partitioned table whose
partitions are a few hundred kilobytes each — the same mistake the compaction
section below documents, arrived at from the other direction.

Sorting is worth noting as the cheaper alternative. Iceberg keeps per-column
min/max in the manifest, and the partition statistics above already show
`depth_m: (min: 2480.0051, max: 4089.0)` for the single file. Writing the table
sorted by `depth_m` would let file-level statistics skip files for a depth
range with no partitioning at all — the same benefit, at the cost of a sort on
write rather than a partition spec that has to be right in advance.


## Streaming throughput — 15,712 rows/s against a 20,000 target

**Missed, by 21%, and the measured figure is the optimistic one.**

Measured with `scale=load` (800,000 samples across four wellbores, 81 MB of
WITSML XML) through `producer.py --speed 0 --dry-run`: parse, resolve identity,
validate against the Avro contract, encode. 50.9 s, zero rejected.

`--dry-run` excludes the Kafka produce, so the real end-to-end number is lower.
It was measured this way deliberately — separating the reader from the broker
says *where* the time goes, and it goes to the reader.

**Where it goes.** The producer does four things per sample and only one of them
is cheap:

1. `lxml.iterparse` over a 20 MB document, yielding one `<data>` element at a
   time. Streaming rather than loading, which is the right shape, but the XML
   is ~100 bytes of tags per 60 bytes of payload.
2. A comma split of the data line against `mnemonicList`.
3. Identity resolution per sample, through a dictionary lookup that is fast but
   happens 800,000 times.
4. Avro encoding, hand-written, one field at a time in Python.

**What would fix it**, in order:

- **Encode in batches, not per record.** The Avro encoder writes field by field
  through Python function calls. Encoding a block of records into one buffer,
  or handing the loop to a compiled encoder, is the single largest win — and
  `fastavro` exists precisely for this. It is not a declared dependency and
  adding it needs an ADR, which is the right process for a decision that trades
  a dependency for a 20% target.
- **Resolve identity once per document, not per sample.** Every sample in a
  WITSML log has the same wellbore. The lookup is hoisted out trivially.
- **Parallelise across files.** Four documents, four cores. The producer is
  single-threaded and the work is embarrassingly parallel; this alone would
  clear the target on this hardware, though it would be measuring the machine
  rather than the code path.

The honest summary is that the target is reachable and the current
implementation does not reach it.

## Compaction — 0.1% fewer files, and the cause is a design decision

**Missed, badly, and this is the most interesting number on the page.**

`scripts/compact.py --all` ran `ALTER TABLE ... EXECUTE optimize` over 28
tables. Overall: **4,136 files → 4,131**, a 0.1% reduction against a target of
70%. Average file size on the worst table: **6.9 KB** against a target of
128–512 MB.

| Table | Rows | Files before → after | Avg size | Reduction |
|---|---:|---|---:|---:|
| `bronze.prod_daily` | 14,859 | 3,044 → 3,044 | 6.9 KB | 0.0% |
| `bronze.ddr_activity` | 15,854 | 957 → 957 | 9 KB | 0.0% |
| `bronze.prod_monthly` | 497 | 100 → 100 | 4 KB | 0.0% |
| `silver.silver_production_quarantine` | 48 | 3 → 1 | 4.7 KB | 66.7% |
| `silver.silver_simulation_result` | 183 | 3 → 1 | 5.4 KB | 66.7% |

The three tables that compacted are the three that had more than one file in a
single partition. The three that did not have **exactly one file per
partition**, and `optimize` rewrites files *within* a partition — it cannot
merge across partition boundaries, because that is what a partition is.

**The cause is a collision between two parts of SPEC.md.**

- Section 3 requires every bronze column to be `varchar`, including
  `_replay_date`. Bronze does not type anything, and that is what makes replay
  from bronze possible without re-ingesting.
- Section 4.1 requires bronze to be partitioned by `_replay_date`.

A partition transform on a `varchar` can only be identity. So the field's 3,044
days become 3,044 partitions holding a median of seven rows each, and no amount
of compaction will merge them. The table is not badly compacted; it is
correctly compacted and badly partitioned.

**What would fix it.** Partition evolution — which is precisely the Iceberg
capability ADR 001 chose the format for, and which has not been used yet:

1. Add a typed `_replay_month` (or a real `date` column) and evolve the
   partition spec to `month(...)`. Existing data keeps its old layout, new data
   lands in monthly partitions, and both remain readable. 3,044 partitions
   become 100.
2. Then compaction has something to do: a month of production is ~210 rows,
   still small, but a month of telemetry at 5-second sampling is ~500,000.
3. The daily partition is the right grain for the *delete* in the idempotent
   load, so the two are in tension and the resolution is a partition spec that
   is coarser than the delete predicate — Iceberg supports that, and it is the
   next piece of work here.

Nothing was tuned to make the number look better, and the number is bad. It is
also the clearest evidence in this repository that the partitioning decision
deserves the revisit ADR 001 anticipated.

## Streaming: dedup and resume, proven

Not a performance target, but measured the same way, on the running stack.

**Dedup (BR-07).** 500 distinct samples produced, then the same 500 produced 20
more times — 10,500 messages on the topic, of which 10,000 are duplicates.
`silver.drilling_telemetry` held **500 rows and 500 distinct
(wellbore_uid, ts)** afterwards. Duplicates added nothing.

**Resume.** The Spark container was killed outright with `docker kill` while
the stream was running, 3,000 further samples were produced while it was down,
and the job was resubmitted against the same checkpoint. Afterwards: **3,000
rows, 3,000 distinct keys, 0 duplicates introduced**. No rows were lost and none
were double-counted — the checkpoint held the committed Kafka offsets across a
process that never got to shut down.
