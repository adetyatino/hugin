# Portability: one dbt project, three targets

SPEC.md section 12 asks for one claim: *the same dbt models run unchanged on
Trino, DuckDB and Databricks SQL.* This page says exactly how much of that
claim is currently earned, and by what.

**Measured**: 2026-08-13.
**Machine**: Windows 11, Docker Desktop. Trino 476 (one node, coordinator is the
worker), DuckDB 1.5.4, Apache Spark 3.5.4 in the compose stack. dbt-core 1.12.2
with dbt-trino 1.10.3 and dbt-duckdb 1.11.0.

## The short version

| Target | Status | Evidence |
|---|---|---|
| `trino` | **executed**, 25 models + 107 tests, all pass | `dbt build --target trino`, 67.4 s |
| `duckdb` | **executed**, same 25 models + 107 tests, all pass | `dbt build --target duckdb`, 60.2 s |
| `databricks` | **not executed** — no workspace exists | dialect audit + cross-engine equivalence, below |

So the honest claim today is *two engines executed, and a third whose dialect
has been audited and whose every difference is verified equivalent on Spark
3.5*. Not three engines. ADR 007 records why no workspace was invented to close
the gap, and what happens on the day one exists.

That distinction is the whole point of this page. A portfolio that says "runs on
Databricks" because a target block exists in `profiles.yml` has claimed
something it cannot show. What follows is what can be shown.

## What the third target was actually worth

The audit found **six** constructs where Trino and DuckDB agree and Databricks
does not. Four of them were sitting inline in models, having been written when
there were only two engines and both happened to accept them.

Each was checked by running it on Spark 3.5 with `spark.sql.ansi.enabled=true`,
because Databricks SQL warehouses enable ANSI mode by default and OSS Spark
does not — a check run under the OSS default would be lenient exactly where
Databricks is strict.

| Construct, as written for Trino/DuckDB | On Spark 3.5, ANSI on | Verdict |
|---|---|---|
| `cast(x as varchar)` | `ParseException` — VARCHAR needs a length | dispatch **required** |
| `strpos(haystack, needle)` | `UNRESOLVED_ROUTINE` — no such function | dispatch **required** |
| `unnest(generate_series(…))` | `UNRESOLVED_ROUTINE` — no `unnest` | dispatch **required** |
| `date_diff('second', a, b)` | `ParseException` — no unit-taking `date_diff` | dispatch **required** |
| `date '1899-12-30' + 41000` | works, returns `2012-04-01` | dispatched as **precaution** |
| `interval '10' minute preceding` | works | dispatched as **precaution** |

The last two are stated as precautions rather than fixes because that is what
they are. The default rendering would have worked on Spark 3.5. They are
dispatched because date-plus-integer is arithmetic ANSI SQL does not define and
a warehouse that tightens it later should not silently change `dim_date`, and
because the plural unquoted interval is the spelling Databricks documents. Two
of six being unnecessary is worth writing down: it is the difference between an
audit and a story about an audit.

### The one that would not have raised anything

`date_diff` deserves its own paragraph, because it is the reason this page
compares *answers* rather than checking that SQL parses.

The natural hand-port of `date_diff('second', a, b)` to Databricks is
`datediff(b, a)`, which exists and returns **whole days**. Measured on the same
two telemetry samples three minutes apart:

| Rendering | Result |
|---|---|
| `datediff(ts, prev_ts)` — the naive port | `0`, `0` |
| `timestampdiff(SECOND, prev_ts, ts)` — what the macro dispatches | `180`, `270` |

Zero seconds between samples makes the rate of penetration zero, and BR-06
classifies every zero-rate sample as `STATIC`. The whole of
`fct_drilling_state` would have been one long non-productive-time span, the
NPT figure in `mart_drilling_efficiency` would have been the entire well, and
nothing anywhere would have thrown an error. This is the failure mode a
compile-only portability check cannot see.

## The macros, and what each was verified against

`scripts/dialect_check.py` renders every macro out of
`transform/macros/dialect.sql` through a re-implementation of
`adapter.dispatch` that resolves as dbt's does — `<target>__name` first,
`default__name` otherwise — then executes the DuckDB rendering in DuckDB and the
Databricks rendering on Spark and compares the rows. The macros are not copied
into the script, so editing one changes what is tested.

    make dialect-check          # needs: docker compose --profile stream up -d spark

**15 of 15 cases agree.** Full results in `docs/dialect-check.json`.

| Macro | Dispatched for Databricks? | Cases agree | What the case checks |
|---|:--:|:--:|---|
| `hugin_as_text` | yes — `string` not `varchar` | 2/2 | text form of a string and of a double |
| `hugin_surrogate_key` | via `hugin_as_text` | 1/1 | md5 hex identical, e.g. `0f650d8e8fb6f492f75142e07a2ec35e` |
| `hugin_date_from_excel_serial` | yes — `date_add(date, int)` | 1/1 | serial 41000 → `2012-04-01` on both |
| `hugin_date_from_iso` | no — default works | 1/1 | `2016-08-04T00:00:00+02:00` → `2016-08-04`, no UTC shift |
| `hugin_to_number` | via `hugin_as_text` | 1/1 | decimal comma, embedded spaces, `try_cast` returning NULL not raising |
| `hugin_null_if_sentinel` | via `hugin_as_text` | 1/1 | BR-08: `-999.25` and `nan` both become NULL |
| `hugin_safe_divide` | no — default works | 1/1 | 1/0 → NULL under ANSI mode, not an error |
| `hugin_month_key` / `hugin_date_key` | no — default works | 2/2 | `2014-04-07` → `201404` / `20140407` |
| `hugin_strpos` | yes — `locate`, arguments reversed | 2/2 | the `15/9-F-15 D` well/sidetrack split |
| `hugin_seconds_between` | yes — `timestampdiff` | 1/1 | 180, 270, 300, 690 seconds |
| `hugin_minutes_preceding` | yes — plural unquoted interval | 1/1 | the ten-minute block-travel window frame |
| `hugin_date_spine` | yes — `explode` not `unnest` | 1/1 | 3,044 rows, `2008-06-01` to `2016-09-30` |

The surrogate-key row is the one that would have been most expensive to get
wrong. `hugin_as_text` sits inside every `_key` column in the warehouse, so a
text cast that formatted `39600.0` differently on one engine would not fail —
it would produce a different md5, and every join across a warehouse built on
two engines would miss. The case checks the double form explicitly for that
reason: both give `39600.0`.

## Per-model status

Every model is built and tested on Trino and DuckDB by `make dbt-build`. The
Databricks column is `not executed` for all of them and will stay that way
until there is a warehouse; what it does record is whether the model contains
anything that would have needed attention.

| Model | trino | duckdb | databricks | Dialect surface |
|---|:--:|:--:|:--:|---|
| `silver_production_daily` | pass | pass | not executed | `hugin_date_from_excel_serial`, `hugin_to_number` |
| `silver_production_monthly` | pass | pass | not executed | `hugin_to_number` |
| `silver_production_quarantine` | pass | pass | not executed | — |
| `silver_log_curve` | pass | pass | not executed | `hugin_to_number` |
| `silver_log_sample` | pass | pass | not executed | `hugin_null_if_sentinel` (BR-08) |
| `silver_trajectory_station` | pass | pass | not executed | `hugin_to_number` |
| `silver_ddr_activity` | pass | pass | not executed | `hugin_date_from_iso`, `hugin_to_number` |
| `silver_vsp_checkshot` | pass | pass | not executed | `hugin_to_number` |
| `silver_simulation_result` | pass | pass | not executed | `hugin_to_number` |
| `silver_wellbore_identity` | pass | pass | not executed | **`hugin_strpos`** — was inline `strpos` |
| `dim_date` | pass | pass | not executed | **`hugin_date_spine`** — `unnest` vs `explode` |
| `dim_well` | pass | pass | not executed | `hugin_surrogate_key` |
| `dim_wellbore` | pass | pass | not executed | `hugin_scd2`, which uses **`hugin_as_text`** |
| `dim_curve` | pass | pass | not executed | `hugin_surrogate_key` |
| `dim_facility` | pass | pass | not executed | `hugin_surrogate_key` |
| `fct_production_daily` | pass | pass | not executed | `hugin_date_key`, `hugin_month_key` |
| `fct_production_monthly` | pass | pass | not executed | `hugin_month_key` |
| `fct_log_sample` | pass | pass | not executed | `hugin_surrogate_key` |
| `fct_trajectory` | pass | pass | not executed | `hugin_surrogate_key` |
| `fct_simulation` | pass | pass | not executed | `hugin_date_key` |
| `fct_drilling_state` | pass | pass | not executed | **`hugin_seconds_between`**, **`hugin_minutes_preceding`** — both were inline |
| `mart_well_performance` | pass | pass | not executed | `hugin_safe_divide` |
| `mart_allocation_reconciliation` | pass | pass | not executed | `hugin_safe_divide` |
| `mart_identity_coverage` | pass | pass | not executed | `hugin_safe_divide` |
| `mart_drilling_efficiency` | pass | pass | not executed | `hugin_safe_divide` |

Four models are in bold above because they held inline SQL that a Databricks
build would have rejected or, in one case, silently mis-answered.

## Keeping it true

Three mechanisms, because prose in a document does not fail a build.

1. **`tests/test_portability.py`** — 29 tests, part of the normal `pytest` run,
   no containers needed. Every model file is scanned for the eleven constructs
   above plus a few neighbours (`ilike`, `regexp_like`, `date_format`,
   `approx_percentile`, `to_hex`/`to_utf8`); each failure message names the
   macro to use instead. It also asserts that no model branches on
   `target.type`, that every dispatched macro has a `default__`, and — the one
   that already earned its keep — that every dispatched macro has a case in
   `dialect_check.py`. That test failed when it was first run, on
   `hugin_date_from_iso`, which had no case.
2. **`make dialect-check`** — the cross-engine comparison, run against Spark.
3. **`make dbt-build`** — both executable targets, every time.

## What is still unverified, and would need a workspace

Naming these matters more than the list of things that passed.

- **Nothing has run on Databricks Runtime.** Spark 3.5 is what DBR is built on;
  it is not DBR. Photon, the Databricks-specific `datediff` overloads, and
  Unity Catalog's own function resolution are all untested here.
- **Three-part naming.** `sources.yml` now reads its catalog from
  `HUGIN_CATALOG` (falling back to `TRINO_CATALOG`, then `iceberg`), which is
  the mechanism a Unity Catalog name would arrive through. It has never been
  set to a Unity Catalog name.
- **Materialisation.** Trino writes Iceberg, DuckDB writes into a local
  database file, Databricks would write Delta by default. No model sets a
  file format, which is why they are portable; whether the Delta defaults are
  acceptable is unknown.
- **The bronze subset.** SPEC.md section 12 says "against a subset". Which
  tables, at what grain, and loaded by what — none of that is decided, because
  deciding it without a workspace to load into would be design fiction.
- **Timestamps with offsets.** `hugin_date_from_iso` takes the first ten
  characters deliberately, so no engine's session time zone is involved. That
  is verified on Spark; a warehouse with a non-UTC default session time zone
  has not been tried.

## How to finish it

    export DATABRICKS_HOST=...        # adb-....azuredatabricks.net
    export DATABRICKS_HTTP_PATH=...   # /sql/1.0/warehouses/....
    export DATABRICKS_TOKEN=...
    export DATABRICKS_CATALOG=hugin
    export HUGIN_CATALOG=hugin

    uv add --group dev dbt-databricks        # under ADR 004, no new ADR needed
    cd transform && dbt build --target databricks

Then replace the `not executed` column with what happened — including the
failures. A first run that passes all 25 models would be more surprising than
one that does not, and the surprises are the part worth reading.
