# ADR 004 — Adding dbt-core and two adapters to the closed dependency list

Status: accepted
Date: 2026-08-13
Scope: `transform/`, `pyproject.toml`

## Context

SPEC.md section 1 already locks dbt as the transformation tool and names three
targets: Trino primary, DuckDB for CI, Databricks SQL as portability proof.
That decision is not reopened here.

What is open is the dependency list. CLAUDE.md closes `pyproject.toml` and
requires an ADR before anything is added, precisely so that "the spec says so"
cannot smuggle packages in without anyone stating what they cost. dbt is not one
package: it is a core plus one adapter per target, each pinning its own database
driver.

## Decision

Add three packages to the dev-facing dependency set:

    dbt-core        the compiler, materialisation and test runner
    dbt-trino       the primary target's adapter
    dbt-duckdb      the second target's adapter

Not added:

*   **dbt-databricks.** SPEC.md section 12 makes Databricks the third target,
    and it stays out until there is a Databricks workspace to run against.
    Installing an adapter that no profile targets would be a dependency
    carrying no weight.
*   **dbt-utils, dbt-expectations, or any dbt package.** They arrive through
    `packages.yml` rather than pip, but they are dependencies all the same, and
    the two things this project would use them for — surrogate keys and a
    handful of generic tests — are four macros. Writing those is cheaper than
    auditing a package tree, and `hugin_surrogate_key` has to dispatch across
    Trino and DuckDB anyway, which is the part dbt_utils would not do for us.

They are declared in the `dev` group rather than the runtime dependencies:
nothing in `src/hugin/` imports dbt. The pipeline invokes it as a command, and
a Python module that imported dbt would be a sign the boundary had slipped.

## What this costs

- **A version matrix.** dbt-core, the two adapters and their drivers move
  together; an adapter release can lag core by weeks. The lockfile is what
  keeps that from being discovered during a build.
- **Two engines to keep honest.** Every model must compile and run on both.
  That is the point — SPEC.md section 12's portability claim is only credible
  if CI exercises it — but it means a dialect difference is a build failure
  rather than a footnote.
- **A second test framework.** `pytest` covers Python, `dbt test` covers models.
  Both run in CI and a rule can now fail in two places, which is better than a
  rule that can only fail in one.

## Alternatives considered

**SQL scripts run by the existing Python code.** No new dependency, and it was
genuinely tempting given how much of the pipeline is already Python. Rejected
because it would mean writing dependency resolution, incremental
materialisation, test running and documentation generation — badly — and
because SPEC.md commits to dbt as the thing being demonstrated. A portfolio that
avoids the industry-standard transformation tool in order to keep a dependency
list short has optimised the wrong thing.

**SQLMesh.** A real alternative with better handling of incrementality and a
column-level lineage story dbt lacks. Rejected on the same ground as any
substitution: SPEC.md section 1 says "there is no 'or'", and the argument for
changing a locked decision would have to be about the platform, not about
preference. Worth revisiting if the incremental models in layer 2 turn out to
be the painful part.

**Only the Trino adapter, with DuckDB dropped.** Cheapest option, and it would
halve the dialect work. Rejected because the DuckDB target is what makes CI
possible without containers (SPEC.md section 13 targets a 90-second CI build),
and because a portability claim tested on one engine is not a portability
claim.

## Consequences

- `make dbt-build` stops being a TODO.
- Dialect differences are now a real design constraint, not a note. They are
  resolved in `transform/macros/` with `adapter.dispatch`, never with
  `if target.type` inside model SQL — CLAUDE.md is explicit, and the reason is
  that a branch inside SQL is invisible to `dbt compile` on the other target.
- CI gains a second install path and a second build. The DuckDB one is the
  fast one and should stay that way.

## When this should be revisited

When a Databricks workspace exists, `dbt-databricks` joins the list — under
this ADR, since the decision to have a third target is already made and only
its timing was deferred.
