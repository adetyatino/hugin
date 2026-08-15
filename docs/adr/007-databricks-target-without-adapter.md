# ADR 007 — The third dbt target, built and dispatched but not executed

Status: accepted
Date: 2026-08-13
Scope: `transform/profiles.yml`, `transform/macros/dialect.sql`, `scripts/dialect_check.py`, `pyproject.toml`

## Context

SPEC.md section 12 makes Databricks SQL the third dbt target and states the
claim it is there to support: *"the same dbt models run unchanged on Trino,
DuckDB and Databricks SQL."*

ADR 004 added `dbt-core`, `dbt-trino` and `dbt-duckdb` to the dependency list
and explicitly refused `dbt-databricks`, on the ground that installing an
adapter no profile targets would be a dependency carrying no weight. It named
the condition for reopening: *"when a Databricks workspace exists,
`dbt-databricks` joins the list."*

That condition is still unmet. There is no workspace, no host, no HTTP path and
no token available to this repository, and none can be created without a real
account and a real bill. So `dbt build --target databricks` cannot be run, and
saying it has been run would be exactly the kind of claim SPEC.md section 13 and
the Volve licence's third obligation both forbid.

What *is* possible is everything except the execution, and it turns out that is
most of the work — because the value of a third target was never the log line
saying it passed. It was the dialect differences it forces into the open.

## Decision

Three parts.

**1. The target exists.** `transform/profiles.yml` gains a `databricks` output,
driven entirely by `DATABRICKS_HOST`, `DATABRICKS_HTTP_PATH`, `DATABRICKS_TOKEN`
and `DATABRICKS_CATALOG`, with no defaults. A missing variable fails loudly at
profile render; it never falls back to something that happens to answer.

**2. Every dialect difference is dispatched, now.** Auditing the models against
Spark SQL found five constructs that Trino and DuckDB happen to agree on and
Databricks does not — see `docs/portability-report.md` for the list and how each
was found. Each is now a `hugin_*` macro with a `databricks__` implementation in
`transform/macros/dialect.sql`, and the models call the macro. No model changed
behaviour on Trino or DuckDB: the `default__` implementations render the
identical string the models used to contain inline.

**3. `dbt-databricks` stays out of `pyproject.toml`.** ADR 004's reasoning is
unchanged by this ADR. An adapter that cannot connect to anything adds a version
matrix, a driver, and a transitive tree to the lockfile in exchange for nothing
runnable. It joins the list on the day a workspace exists, under ADR 004, with
no further decision needed.

Instead of executing the build, the `databricks__` implementations are verified
by **semantic equivalence against Apache Spark 3.5**, which is what Databricks
Runtime is built on and what the compose stack already runs for the streaming
job. `scripts/dialect_check.py` renders each macro out of `dialect.sql` itself,
evaluates the `default__` rendering in DuckDB and the `databricks__` rendering
in Spark, and asserts the two produce the same answer for the same inputs. A
macro that parses but returns a different value fails the check — which is the
failure mode that matters, because `datediff` returning whole days where
`date_diff('second', …)` returned seconds would not raise anything, it would
send every rig state to STATIC.

## What this costs

- **The strong claim is not available yet.** What can be said today is: the
  models are free of vendor-specific SQL, every difference is dispatched, and
  each Databricks implementation agrees with its Trino/DuckDB counterpart on
  Spark 3.5. What cannot be said is "it built on Databricks". The CV bullet in
  SPEC.md section 14 asserts three engines, and until the run happens it must
  say two engines and a verified dialect, not three.
- **Spark 3.5 is not Databricks Runtime.** DBR adds Photon, its own catalog
  semantics, and its own defaults; it also removes nothing this project uses,
  which is why the check is worth something. But an equivalence proven on OSS
  Spark is evidence, not proof, and `docs/portability-report.md` says so in the
  column headings rather than in a footnote.
- **Three untested surfaces remain**, all of them outside the model SQL:
  Unity Catalog three-part naming, the default Delta materialisation where the
  other two targets write Iceberg and Parquet, and the shape of the bronze
  subset a workspace would have to hold. These are named in the report as
  unverified rather than assumed to work.

## Alternatives considered

**Install `dbt-databricks` anyway and run `dbt parse --target databricks`.**
Cheap, and it would let the profile resolve. Rejected because parse resolves no
macro dispatch and touches no SQL — it would prove the adapter is installed and
nothing else, at the price of a dependency ADR 004 already argued against. The
green line in the log would be worth less than the audit it replaced.

**Sign up for a free-tier or Community Edition workspace.** The honest option,
and the right one eventually. Rejected for now because it needs an account
belonging to a person, not a repository, and because SPEC.md section 3's promise
is that a reviewer can run everything locally at no cost. A target that only the
author can execute is a target only the author can verify.

**Drop the third target and rewrite the claim.** Rejected: the dialect audit is
what produced the five findings, and four of them are latent bugs that would
have shipped in a two-engine project. `date_diff` alone would have silently
misclassified every rig state. Keeping the target keeps the pressure on.

**Per-engine model files.** Explicitly forbidden by CLAUDE.md and by SPEC.md
section 12, and rejected here for the reason those documents give: a second copy
of a model is exercised only on the engine that runs it, so it rots without
anyone noticing.

## Consequences

- `transform/macros/dialect.sql` is now the whole portability surface. Adding a
  fourth engine means adding implementations there and nowhere else.
- `tests/test_portability.py` fails the build if a model reintroduces one of the
  audited constructs inline. The audit is mechanical, so it cannot quietly stop
  being true.
- `scripts/dialect_check.py` needs the `stream` profile up, so it is not part of
  the default CI run. It is invoked by `make dialect-check`.
- `docs/portability-report.md` carries a per-model table with one column per
  target, and the Databricks column says `not executed` in every row until the
  day it does not.

## When this should be revisited

The moment `DATABRICKS_HOST`, `DATABRICKS_HTTP_PATH` and `DATABRICKS_TOKEN`
exist. Then: add `dbt-databricks` under ADR 004, load the bronze subset,
`dbt build --target databricks`, and replace the `not executed` column with
whatever actually happens — including the failures. A first run that passes
every model would be more surprising than one that does not.
