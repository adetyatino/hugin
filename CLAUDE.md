# CLAUDE.md — working rules for this repo

`SPEC.md` is the contract. This file is the short form an agent reads before
touching anything. Where the two disagree, SPEC.md wins and this file is wrong.

## What this project is

HUGIN is a full-field data platform for Volve, a decommissioned North Sea oil
field whose complete operational archive Equinor released openly.
It unifies six classes of source data — daily production, WITSML drilling
telemetry, well logs, well trajectories, geophysical interpretations, and
reservoir simulation output — into one dimensional model.
The point is heterogeneity, not volume: six formats, six different engineering
problems, one conformed model with identity resolution and lineage.
The archive is static, so a replay clock (BR-01) projects the field's 2008–2016
life onto real calendar time, giving incremental loads and backfills real work.
Everything runs locally on Docker Compose; nothing costs money to review.

## Locked decisions (SPEC.md section 1)

There is no "or". Alternatives are argued in `docs/adr/` and not implemented.

| Aspect | Decision | Why |
|---|---|---|
| Object storage | MinIO (S3-compatible) | Identical API to S3, portable to AWS |
| Table format | Apache Iceberg | Engine-agnostic, partition evolution |
| Catalog | Iceberg JDBC catalog on PostgreSQL | Fewest moving parts |
| Query engine + primary dbt target | Trino (`dbt-trino`) | One engine for transform and serving |
| Second dbt target | DuckDB | Fast CI without containers |
| Third dbt target | Databricks SQL | Proof of portability (SPEC.md section 12) |
| Orchestration | Airflow 2.x, LocalExecutor | Industry standard |
| Streaming | Redpanda + Spark Structured Streaming 3.5 | Light on a laptop, Kafka protocol |
| Geospatial | PostGIS + `pyproj` | Datum and geometry transformation |
| BI | Metabase | Free, one container |
| Language | Python 3.11 + SQL | — |
| Dependencies | `uv` | Deterministic lockfile |
| Domain parsing | `lasio` (LAS), `lxml` (WITSML/EDM XML), `segyio` (SEG-Y headers), `selectolax` (DDR HTML) | Standard libraries, not home-made parsers |
| Data quality | dbt tests + Soda Core | Structural and statistical |
| CI | GitHub Actions | — |

## Naming (SPEC.md section 9)

- Tables `snake_case`, prefixed `dim_`, `fct_`, `mart_`.
- Natural keys end `_code` or `_uid`; surrogate keys end `_key`.
- Timestamps end `_at`; dates end `_date`.
- **Units are always a column suffix**: `_sm3`, `_m`, `_bar`, `_c`, `_deg`,
  `_pct`, `_s`, `_hours`. A dimensional quantity without a unit suffix is
  treated as unfinished work, not as a style preference. `oil_sm3`, not `oil`.
  `md_top_m`, not `md_top`. Counts, ratios and flags carry no unit and take
  none.

## Git (SPEC.md section 9)

- One PR per phase. Conventional commits (`feat:`, `fix:`, `chore:`, `docs:`,
  `test:`).
- Never push straight to `main` — the PR history is part of the portfolio.
- No credentials in the repo. `.env` is ignored; `.env.example` is the template.

## Rules

**No new dependency without an ADR.** The list in `pyproject.toml` is closed.
Adding a package means first writing `docs/adr/NNN-*.md` that states what it
buys, what breaks without it, and what was rejected. This applies to Python
packages, dbt packages, and container images alike. `docs/adr/0001` is the
precedent: it records a dependency *not* taken and the exact condition under
which the question reopens.

**Every BR-xx has a test that names it.** SPEC.md section 5 defines BR-01 to
BR-13. Each needs at least one test whose *name* contains the code —
`test_br01_round_trips_every_field_day`, `assert_br02_daily_matches_monthly`.
The code in the name is what makes the rule auditable from test output alone. A
rule implemented without such a test counts as not implemented.

**Never assume a CRS, a datum, or a NULL sentinel. Read it from the source
header, every file, every time.** Volve-era data is ED50 / UTM zone 31N; modern
systems are WGS84 or ETRS89, and in the North Sea the difference is hundreds of
metres. LAS files usually declare `-999.25` in `~WELL`, but not all of them do,
and a sentinel that reaches an aggregation corrupts the result without raising
anything. Hard-coding either value is a bug even when it happens to be right,
because it is right by luck and silent when wrong. Store `source_crs` alongside
the coordinates, and both coordinate pairs (BR-10). Read the sentinel per file
(BR-08).

**Never drop or guess an unmapped well identity.** One physical wellbore appears
across systems as `15_9-F-12`, `Norway-Statoil-15_$47$_9-F-12`, and
`Norway-Statoil-NO 15_$47$_9-F-12`; operator labels shift Statoil →
StatoilHydro → Statoil. BR-12 resolves what it can and records `match_method`
and `match_confidence`. What does not resolve goes to
`silver.wellbore_identity_unresolved` and is counted in `mart_identity_coverage`.
Silently dropping rows destroys data; guessing attributes production to the
wrong wellbore, which is worse than a gap because it looks like an answer.

**No vendor-specific functions in dbt models.** The same models must build on
Trino, DuckDB, and Databricks SQL without edits (SPEC.md section 12). Dialect
differences are resolved in macros with `adapter.dispatch`, never with `if
target.type == ...` branching inside model SQL. If a model needs a function that
one engine lacks, write `hugin_<thing>()` with per-adapter implementations and
call that.

## Volve licence obligations (SPEC.md section 10)

CC BY 4.0 with two changes. Commercial use, derivatives, and redistribution are
all permitted. The obligations:

1. Do not sell the Licensed Material.
2. Attribute Equinor and the former Volve licence partners — ExxonMobil
   Exploration & Production Norway AS and Bayerngas Norge AS — with a link to
   the terms.
3. Do not present the data in a misleading, distorted, or untrue way.
4. Do not redistribute derivatives under a licence that stops the recipient
   complying with these terms.
5. Do not use Equinor's name or marks to endorse or market your use.

Obligation 3 makes honesty a licence condition, not an ethical preference: a
figure produced with `SOURCE_MODE=synthetic` must never be presented as a
finding about Volve. Every table, chart, and CV bullet states which mode it came
from. The terms PDF lives in `docs/licenses/` and is linked from the README.

## Make targets

| Target | Does |
|---|---|
| `setup` | `uv sync --all-groups` |
| `inventory` | Scan archives, detect duplicates, classify sources — no extraction |
| `extract` | Extract to `data/landing/`, then regenerate `docs/` |
| `report` | Regenerate `docs/` from existing artefacts |
| `identity` | BR-12: build `silver.wellbore_identity` from `data/landing/` |
| `gen-data` | Calibrate against silver, then generate CI fixtures |
| `seed` | *TODO* — load `data/landing/` into bronze |
| `up` / `down` | *TODO* — `docker compose --profile core up` / `down` |
| `test` | `pytest` |
| `lint` | `ruff check` + `ruff format --check` (sqlfluff joins with `transform/`) |
| `dbt-build` | `dbt build` on both targets: trino then duckdb |
| `benchmark` | Measure against the SPEC section 13 targets, into `docs/performance.md` |
| `replay-reset` | *TODO* — clear DAG runs, drop replayed `_replay_date` partitions |

TODO targets print the phase that fills them and exit non-zero, so nothing
mistakes unwritten for done. GNU make is absent on Windows; `make.cmd` mirrors
every target and must be kept in step with the Makefile.

## The archive is read-only

`VOLVE_ARCHIVE_DIR` holds 24 zips and the licence PDF. Nothing in this repo
writes there, ever — not to tidy names, not to unzip in place. Everything
derived lands in `data/`, which is rebuildable and git-ignored, with one
deliberate exception: `data/_inventory/name-mapping.csv` is committed, because
it is the only record of how sanitised names map back to original ones.
