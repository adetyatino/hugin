# HUGIN — a full-field data platform for the Volve field, North Sea

> One field, every data type — a data platform that unifies daily production,
> WITSML drilling telemetry, well logs, well trajectories, geophysical
> interpretation, and reservoir simulation output from one real North Sea field
> into a single dimensional model with full identity resolution and lineage.

Named after the Hugin Formation, the Jurassic sandstone Volve produced from.

## 2. Status

![ci](https://github.com/USER/hugin/actions/workflows/ci.yml/badge.svg)
![python](https://img.shields.io/badge/python-3.12-blue)
![licence](https://img.shields.io/badge/data-Equinor%20Volve%20terms-lightgrey)

> The CI badge resolves once this repository has a GitHub remote; the workflow
> in `.github/workflows/ci.yml` runs ruff, pytest and a DuckDB `dbt build` on
> every push. Replace `USER` with the account when the remote is added.

**Built and running:** archive inventory and extraction, BR-12 identity
resolution, thirteen format readers, a bronze lakehouse on Iceberg, a dbt
project building **25 models and 107 tests green on two engines**, a Kafka and
Spark streaming path with dedup and checkpoint resume both proven by
measurement, BR-09 minimum curvature validated to millimetres, an OSDU mapping
with a JSON Schema validator, and service level objectives enforced by an
Airflow task.
**Running in Airflow:** all three DAGs parse in the scheduler with no import
errors, and `hugin_daily.resolve_replay_date` has been executed against a
real interval — 2026-08-04 resolved to replay date 2008-09-01, which is three
field months after the epoch for three real days, exactly as BR-01 specifies. No
full DAG run has been executed end to end.
**Not built:** BR-10 (no source in this delivery declares a CRS), BR-13, the
third dbt target's execution (no Databricks workspace — ADR 007), and the
Metabase dashboard. Section 10 says exactly where the edges are, and
[`docs/slo.md`](docs/slo.md) lists three objectives the pipeline does not
currently meet, each with a diagnosis.

## 3. Architecture

```
volve/ (24 read-only zip archives)
   |
   |  make inventory / make extract        src/hugin/ingestion/inventory.py
   v
data/landing/<source_code>/               10,773 files, names preserved
   |
   |  thirteen format readers              src/hugin/ingestion/{prod,ddr,las,...}.py
   |  identity resolved at ingest          src/hugin/identity/
   v
bronze (Iceberg on MinIO, all varchar)    13 tables, 7 technical columns each
   |                                       ^
   |  dbt: type, dedup, clean              |  Redpanda -> Spark Structured
   v  transform/models/silver/             |  Streaming, watermark + dedup
silver ---> gold (Kimball, SCD2) ---> mart |  src/hugin/streaming/
   |                                       +-- silver.drilling_telemetry
   +-- Trino (primary, executed)
   +-- DuckDB (CI, no containers, executed)
   +-- Databricks SQL (dispatched and audited, not executed — ADR 007)
   |
   +-- OSDU well-known schemas             src/hugin/osdu/  -> 28 records, 0 violations
   +-- SLOs enforced in Airflow            src/hugin/slo.py -> hugin_daily.slo_check
```

A rendered diagram belongs in `docs/img/`; the text version is authoritative
until then, and it is the same shape as `SPEC.md` section 3.

## 4. What this project proves

Each item names the file or table that does it, because a claim that cannot be
checked is not a claim.

- **An archive with no arrival pattern can still exercise orchestration.**
  `src/hugin/common/replay.py` maps Airflow's `data_interval` onto the field's
  2008–2016 life as a pure function — exact rationals, no wall clock, no
  clamping at either end. 26 tests named `test_br01_*`, and
  `orchestration/dags/hugin_daily.py` takes its date from it rather than
  `datetime.now()`.
- **Identity resolution that shows its work and refuses to guess.**
  `src/hugin/identity/normalize.py` implements BR-12 as five separately testable
  stages, and `crosswalk.py` resolves 337 of 379 identity strings to 37
  wellbores. `docs/identity-report.md` lists all 42 unresolved with a category
  and a reason. The decisive case: production writes `NO 15/9-F-4 AH`, whose
  name parses to a sidetrack no register knows, and the NPD code in the same row
  says the wellbore is `15/9-F-4` — the identifier wins, and the disagreement is
  recorded.
- **A NULL sentinel read from the data, not from a constant.** The delivery
  declares four spellings — `-999.25`, `-9999`, `-999.2500`, `-999.25000` —
  each in the file that uses it. `src/hugin/ingestion/las.py` reads it per file;
  `transform/models/silver/silver_log_sample.sql` compares each reading against
  its own file's value; `assert_br08_*.sql` proves none survived.
- **Idempotency proven, not claimed.** `tests/test_bronze_integration.py` loads
  a replay date twice against the running stack and asserts the same row count,
  the same `_row_hash` set, and only the newest `_batch_id` present. The
  24-month backfill was run twice: 26.2 s then 23.9 s, identical table state.
- **The same dbt models on two engines, unchanged — and a third whose dialect
  is audited.** `dbt build` returns `PASS=132 ERROR=0` on both Trino (67.4 s)
  and DuckDB (60.2 s), 25 models and 107 tests. Every dialect difference lives
  in `transform/macros/dialect.sql` behind `adapter.dispatch`, never as a
  branch inside a model. Auditing the models against Databricks SQL found
  **six** constructs Trino and DuckDB happen to agree on and Spark does not,
  four of them sitting inline in models — including `date_diff('second', …)`,
  whose obvious Databricks port returns whole *days* and would have sent every
  BR-06 rig state to `STATIC` without raising anything.
  `scripts/dialect_check.py` renders each macro out of `dialect.sql` and
  compares its answer across DuckDB and Spark 3.5 under ANSI mode: **15 of 15
  agree**. [`docs/portability-report.md`](docs/portability-report.md) is
  explicit that the Databricks build itself has *not* been executed and why.
- **SCD2 that tracks something real.** `transform/models/gold/dim_wellbore.sql`
  gives `15/9-F-5` nine versions as it was converted between producer and water
  injector, with the dates it happened on, and carries the `Statoil` /
  `StatoilHydro` label variation across wellbores.
- **A reconciliation that finds real disagreement.**
  `mart_allocation_reconciliation` compares 497 wellbore-months: 493 agree
  exactly, 4 breach the ±2% tolerance, worst at −20.5%. Neither figure is
  corrected — BR-02 says the difference is the information — and a test fails if
  the model ever finds nothing.
- **Reading a terabyte's metadata without moving it.**
  `src/hugin/ingestion/segy.py` reads 3,840 bytes per SEG-Y file — 3,200 EBCDIC,
  400 binary, 240 trace header — and refuses any HTTP response that is not `206
  Partial Content`, because a server ignoring `Range` would turn the fallback
  into a 1.17 TB download.

### Layer 2 — streaming and drilling

- **A streaming job that survives being killed, measured rather than asserted.**
  `src/hugin/streaming/spark_stream.py` writes Kafka to Iceberg with a
  watermark, `dropDuplicatesWithinWatermark` and a checkpoint. Dedup: 500
  distinct samples produced 21 times — 10,500 messages, 10,000 of them
  duplicates — left **500 rows and 500 distinct `(wellbore_uid, ts)`**. Resume:
  the container was killed with `docker kill` mid-stream, 3,000 further samples
  were produced while it was down, and the job resubmitted against the same
  checkpoint ended with **3,000 rows, 3,000 distinct keys, 0 duplicates**. No
  rows lost, none double-counted, across a process that never got to shut down.
- **A rig-state classifier, and a validation that refuses to invent a number.**
  `src/hugin/streaming/rig_state.py` implements BR-06's ordered rule with
  SPEC.md's thresholds, unmodified, in one dictionary.
  [`docs/rig-state-validation.md`](docs/rig-state-validation.md) reports that the
  agreement rate against `silver.ddr_activity` **cannot be computed** on this
  delivery — `mnemonicList` appears in zero of 10,773 extracted files, so the
  only telemetry available is fixture data for wellbores that do not exist — and
  says exactly what would make it computable. Forcing an overlap would have
  produced a fabricated agreement rate between synthetic telemetry and real
  drilling reports.

### Layer 3 — geoscience, portability, and operations

- **Minimum curvature validated to millimetres, then contradicted by an
  independent measurement.** `src/hugin/geo/minimum_curvature.py` recomputes TVD
  from raw angles and lands within **3 mm** of the surveying contractor's own
  numbers on a 469-station survey — three orders of magnitude inside SPEC.md's
  0.1% threshold. Against the VSP checkshot, the only independent depth
  measurement in the delivery, it does **not** agree: mean **+32.45 m** over 142
  comparable points, with a structure — a few metres to 2400 m, then divergence
  to +82 m. [`docs/trajectory-validation.md`](docs/trajectory-validation.md)
  reports both, and treats the disagreement as a finding rather than as a
  tuning opportunity. The validation also caught the delivery declaring four
  surveys in **radians**: `0.371` reads plausibly as degrees and is 21.3°, which
  puts computed TVD 188 m out.
- **A gold schema mapped to OSDU, and validated by something we did not write.**
  `src/hugin/osdu/mapping.py` maps `dim_wellbore`, `fct_log_sample` and
  `fct_trajectory` to three OSDU well-known kinds; two of the three change grain,
  because OSDU's work-product-components describe a logging run and a survey
  rather than a reading and a station. **28 records, 0 schema violations**
  against the reduced 1.0.0 schemas. The half worth reading is
  [`docs/osdu-mapping.md`](docs/osdu-mapping.md)'s two tables of what does *not*
  map: eight gold columns with no OSDU home, and nine OSDU properties nothing
  here can honestly fill.
- **Service level objectives that fail a DAG.** [`docs/slo.md`](docs/slo.md)
  defines 16 objectives across freshness, completeness and BR-12 coverage — each
  with the SQL that measures it and a sentence on what breaks when it is
  breached — and `hugin_daily.slo_check` runs the same `evaluate()` after
  `dbt_test`. Current state: **13 met, 3 known breaches, 0 blocking**. Two of the
  three found a real defect the dbt tests could not see: `bronze.las_curve_header`
  is empty, so `dim_curve` has 0 rows and every `curve_key` in `fct_log_sample`
  is NULL, on a table whose `not_null` tests all pass.
- **Performance measured against every SPEC §13 target, including the misses.**
  Four met, three missed, one met on latency and failed on the mechanism.
  [`docs/performance.md`](docs/performance.md) carries the `EXPLAIN ANALYZE`
  showing `Filtered: 93.32%, Splits: 1` on a table with no partitioning, and
  [ADR 009](docs/adr/009-partition-evolution.md) explains why bronze has 3,044
  partitions of seven rows and gold has one partition of everything — the same
  decision, wrong in two directions.

## 5. Data provenance

Every figure this repository produces is traceable to one of two origins, and
they are never mixed silently. This is a licence condition, not a preference:
the Volve terms forbid presenting the data in a misleading or distorted way, so
labelling fixture-derived numbers as such is part of complying with them.

### Origin of the data

All real data comes from Equinor's open release of the Volve field archive,
2008–2016, held locally as 24 read-only zip archives. The archive folder is
never written to; everything derived lands in `data/`, which is rebuildable.
Detail: [`docs/data-inventory.md`](docs/data-inventory.md) and
[`docs/data-dictionary.md`](docs/data-dictionary.md).

| Code | What it is | Present locally |
|---|---|---|
| `PROD` | Daily and monthly production and injection | Yes — one XLSX workbook, 15,635 daily rows |
| `WITSML` | Drilling messages, BHA runs, mud log | Yes — 4,094 XML documents. **No log curves**: `mnemonicList` appears in none of them |
| `TRAJ` | Directional survey stations | Yes — 32 XML documents |
| `DDR` | Daily drilling reports | Yes — 1,759 each of XML, HTML, PDF |
| `LOG` | Well logs | Yes — 100 LAS (2.0 and 3.0), plus DLIS not parsed |
| `VSP` | Borehole seismic checkshots | Yes — 4 checkshot files, 68 SEG-Y |
| `SIM` | Eclipse simulation output | Yes — one 238 MB print file |
| `GEOM` | Fault polygons, horizons, picks, perforations | **No delivery.** Fault definitions exist only as `ADDZCORN` grid records inside the Eclipse model |
| `SEIS` | Surface seismic | **Not delivered.** Headers only, read remotely |

### Real data versus fixtures

| `SOURCE_MODE` | Reads | Used for |
|---|---|---|
| `real` | The Volve archive on disk | The development default. Everything below is from this. |
| `synthetic` | Calibrated fixtures | CI determinism and volume amplification only. |

**Every number in this README and in `docs/performance.md` came from
`SOURCE_MODE=real`.** No fixture-derived figure appears anywhere in this
repository or its documentation.

Fixtures are generated by `src/hugin/synthetic/`, calibrated against the real
silver tables by `calibrate.py`. The profile records which parameters were
measured and which were assumed — currently 12 calibrated, 7 assumed, where the
assumptions are the four anomaly classes that occur **zero** times in the real
data plus the telemetry ranges, which cannot be calibrated because the delivery
contains no telemetry. Fixture wellbores are named `15/9-X-*`, which does not
exist in the field, so a fixture row is identifiable on sight.

### Provenance per table

| Table | Origin | Note |
|---|---|---|
| `bronze.prod_daily`, `bronze.prod_monthly` | **Real** | Volve production workbook, 14,859 daily rows in the replay window |
| `bronze.ddr_activity` | **Real** | 1,759 daily drilling reports |
| `bronze.trajectory_station` | **Real** | EDT/Compass survey exports |
| `bronze.las_curve_header`, `bronze.las_sample` | **Real** | LAS 2.0 and 3.0; sample load bounded to 8 files |
| `bronze.vsp_checkshot` | **Real** | 4 checkshot files |
| `bronze.segy_header` | **Real** | Headers only, 3,840 bytes per file |
| `bronze.sim_summary` | **Real** | Eclipse balance pages |
| `bronze.geom_fault_record` | **Real** | `ADDZCORN` grid records; no GEOM product exists |
| `bronze.witsml_message` | **Real** | Drilling messages |
| `bronze.witsml_log_header`, `bronze.witsml_log_data` | **Empty** | The delivery has no log curves. Populated only by fixtures, and only in CI |
| all `silver.*`, `gold.*`, `mart.*` | **Real** | Built from the bronze tables above under `SOURCE_MODE=real` |
| `data/fixtures/**` | **Fixture** | Generated, `15/9-X-*` wellbores, never loaded into the tables above |

No table in the running warehouse holds fixture data. The fixtures exist for CI,
which builds them into a separate DuckDB file, and for the load test.

## 6. How to run

```bash
make setup                       # uv sync
make inventory && make extract   # read the archives, land the files
make up                          # MinIO, PostgreSQL, Trino, Metabase, Airflow
make identity && make seed       # BR-12 crosswalk, then bronze
cd transform && dbt build --target trino
```

`make gen-data` calibrates against silver and writes the CI fixtures;
`make test` runs the Python suite; `make counts` prints bronze row counts and
identity coverage. The archive folder is read-only and no target writes to it.

## 7. Dashboard

**Not built.** Metabase runs in the compose stack and is reachable on
`localhost:3000`, but no dashboard has been created, no charts exist, and
`docs/metabase-export.json` and `docs/img/` are empty.

Saying so is cheaper than a screenshot of an empty Metabase. The five charts
this needs — production rate by wellbore, water cut trend, allocation variance,
identity coverage, uptime — all have their data in `mart_well_performance`,
`mart_allocation_reconciliation` and `mart_identity_coverage` already.

## 8. Measured results

Full analysis, including what the numbers do *not* show, in
[`docs/performance.md`](docs/performance.md).

Every metric in SPEC §13 is now measured. Four met, three missed, one met on
latency and failed on the mechanism it existed to demonstrate.

| Metric | Target (SPEC §13) | Measured | Met |
|---|---|---|:--:|
| Ingest bronze, one replay day | < 60 s | 53.3 s | yes |
| `dbt build`, Trino | < 8 min | 67.4 s | yes |
| `dbt build`, DuckDB | < 90 s | 60.2 s | yes |
| Backfill 24 replay months | < 25 min | 26.2 s | yes |
| Backfill re-run, identical result | required | 23.9 s, identical | yes |
| Depth-range query, `fct_log_sample` | < 3 s | 0.145 s | yes |
| — with partition pruning active | pruning active | not partitioned, whole table scanned | **no** |
| Streaming throughput, producer path | > 20,000 rows/s | 15,712 rows/s | **no** |
| Iceberg file size after compaction | 128–512 MB | 6.9 KB on the worst table | **no** |
| File count after compaction | down > 70% | 0.1% overall | **no** |

**The ingest figure is the one to read carefully.** Thirty-eight rows took 53
seconds, and almost none of that is data: it is a fixed Trino round trip per
reader plus full scans of sources that have no date index. The number is nearly
flat in data volume and linear in the number of sources, so it would breach the
target by adding readers rather than by adding data.

**The three misses share one cause with the half-miss**, and it is the most
useful thing on this page. Bronze is partitioned by a `varchar` `_replay_date`
— SPEC §3 requires the varchar, SPEC §4.1 requires the partition, and a
partition transform on a varchar can only be identity — so 3,044 field days
become 3,044 partitions holding a median of seven rows. `optimize` rewrites
files *within* a partition and correctly finds nothing to merge. Meanwhile
`fct_log_sample` has no partitioning at all: `EXPLAIN ANALYZE` reports
`Input: 30421 rows, Filtered: 93.32%, Splits: 1` — every row read, 93% discarded
after reading. Bronze has too many partitions and gold has none, from the same
decision taken before there was data to check it against.

Nothing was tuned to improve any of these numbers.
[`docs/performance.md`](docs/performance.md) has the full analysis and the fixes
in the order worth doing; [ADR 009](docs/adr/009-partition-evolution.md) records
why the layout is being left as measured rather than quietly corrected.

## 9. Design decisions

| ADR | Decision |
|---|---|
| [001](docs/adr/001-iceberg-over-delta.md) | Iceberg over Delta and Hudi — engine-agnostic, partition evolution |
| [002](docs/adr/002-replay-clock.md) | The replay clock: exact rationals, no clamping, no wall clock |
| [003](docs/adr/003-identity-resolution.md) | Staged deterministic normalisation, not fuzzy matching |
| [004](docs/adr/004-dbt-adapters.md) | Adding dbt-core and two adapters to a closed dependency list |
| [005](docs/adr/005-local-stack-vs-databricks.md) | Why build locally when Volve is already on Databricks |
| [006](docs/adr/006-synthetic-fixture-strategy.md) | Calibrated fixtures, for CI and load only |
| [007](docs/adr/007-databricks-target-without-adapter.md) | The third dbt target, dispatched and audited but not executed |
| [008](docs/adr/008-osdu-mapping-without-a-deployment.md) | Mapping to OSDU without deploying it, and why `jsonschema` is the one dependency worth adding |
| [009](docs/adr/009-partition-evolution.md) | Partitioning is wrong in two directions, and both are the same decision |
| [0001](docs/adr/0001-stdlib-only-ingestion.md) | Standard library only in the ingestion stage |

## 10. Known limitations

Honest, and specific enough to act on.

- **The WITSML log curves do not exist in this delivery.** `mnemonicList`
  appears in zero of 10,773 extracted files; the `log/` directories hold only
  `MetaFileInfo.txt` listing logs the export never wrote out. The parser is
  built and namespace-driven, and it returns nothing. Layer 2's throughput
  demonstration therefore has no real curve data behind it, and calibrated
  fixtures are the honest way to supply volume for it.
- **BR-06's agreement rate cannot be computed.** The classifier is built and
  tested; the validation against the daily drilling reports returns zero
  comparable rows, because the delivery contains no WITSML log curves and the
  fixture wellbores are not real wells.
  [`docs/rig-state-validation.md`](docs/rig-state-validation.md) says what would
  make the number possible and why forcing an overlap would be worse than having
  no number.
- **BR-10 is not satisfied, and cannot be from these sources.** The trajectories
  declare an azimuth reference, not a coordinate reference system, and
  `fct_trajectory.northing_offset_m` / `easting_offset_m` are offsets from the
  well reference point rather than projected coordinates. `source_crs` is NULL
  for all 475 stations. The SLO for it is kept at 100% and left breached rather
  than lowered, because the day a projected coordinate does arrive it must carry
  its datum. BR-13 is unbuilt: `mart_completion_geology`,
  `mart_well_geometry`, `mart_voidage_replacement` and `mart_sim_vs_actual` do
  not exist.
- **The LAS sample load is bounded, and its curve headers are missing.**
  `fct_log_sample` holds 30,421 rows from 8 LAS files (`--max-las-files 8`); the
  full load is on the order of ten million rows. Separately,
  `bronze.las_curve_header` is **empty**, so `dim_curve` has 0 rows and every
  `curve_key` in `fct_log_sample` is NULL — a real defect that every `not_null`
  test passes over and that the SLO check found. Diagnosis in
  [`docs/slo.md`](docs/slo.md); the fix is a reload, not a code change.
- **The Databricks target has never been executed.** No workspace exists. The
  target, the dispatch implementations and a cross-engine equivalence check are
  all in place and the audit found four latent bugs, but the claim available
  today is *two engines executed and a third audited*, not three engines.
  [ADR 007](docs/adr/007-databricks-target-without-adapter.md) records the line
  and how to cross it.
- **`fct_simulation` is field-level, not per wellbore.** The Eclipse print file
  reports field totals; splitting them across wellbores would be invention.
  `dim_formation`, `dim_rig_state` and `fct_perforation` are not built because
  no source in this delivery feeds them. `fct_drilling_state` *is* built — 1,769
  state spans — but from fixture telemetry, for the reason the bullet above
  gives.
- **The Soda Core scan is a stub.** `hugin_daily` has the task and it skips with
  a reason. Adding `soda-core` needs an ADR under the rule in CLAUDE.md, and
  writing one for a dependency that is not yet used would be an ADR about
  nothing.
- **CI has never run.** There is no GitHub remote, so the workflow in
  `.github/workflows/ci.yml` is untested against Actions. It runs the same four
  commands that pass locally.
- **No DAG has run end to end.** All three parse in the scheduler and
  `resolve_replay_date` has been executed against a real interval, but no
  complete `hugin_daily` run has gone from ingest through dbt test. Every task
  it calls has been run directly and is covered by tests.
- **The measured throughput is the optimistic one.** 15,712 rows/s was measured
  with `--dry-run`, which parses, resolves identity, validates against the Avro
  contract and encodes, but does not produce to Kafka. The end-to-end number is
  lower. It was measured that way deliberately — it locates the cost in the
  reader rather than the broker — and `docs/performance.md` says so where the
  number appears.
- **Production data extends past the replay window.** 775 daily rows fall
  outside 2008-06 .. 2016-09 and can never be reached by a replay-driven run.
  Counted by `out_of_replay_window()`, reported, not resolved — deciding which
  of SPEC and the data is wrong is not a parsing decision.

## 11. Licence and attribution

This repository contains and derives from data from the **Volve field data
village**, released by **Equinor ASA**, and produced under a licence held by
Equinor together with its former Volve licence partners **ExxonMobil
Exploration & Production Norway AS** and **Bayerngas Norge AS**.

The applicable terms are Equinor's *HRS and Terms and conditions for license to
data — Volve*, published as part of the Volve data sharing release
(<https://www.equinor.com/energy/volve-data-sharing>). The copy that governs
this repository is kept verbatim at
[`docs/licenses/HRS and Terms and conditions for license to data - Volve.pdf`](docs/licenses/HRS%20and%20Terms%20and%20conditions%20for%20license%20to%20data%20-%20Volve.pdf).
Per-archive licence files as delivered by the producer are in
[`docs/source-readme/`](docs/source-readme/).

Those terms are based on CC BY 4.0 with two modifications. In summary — the PDF
governs, not this list:

1. The Licensed Material may not be sold.
2. Attribution to Equinor and the former Volve licence partners, with a link to
   the terms, is required. This section is that attribution.
3. The data may not be presented in a misleading, distorted, or untrue manner.
4. Derivative works may not be shared under a licence that prevents the
   recipient from complying with these terms.
5. Equinor's name and marks may not be used to endorse or market any use of the
   data.

This project is an independent portfolio work. It is not affiliated with,
endorsed by, or reviewed by Equinor ASA, ExxonMobil Exploration & Production
Norway AS, or Bayerngas Norge AS. Any error in the derived data is this
repository's, not theirs.

The source code in this repository is separate from the data and is the author's
own work.
