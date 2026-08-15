# ADR 008 — Mapping to OSDU without deploying OSDU, and the dependency that needs

Status: accepted
Date: 2026-08-13
Scope: `src/hugin/osdu/`, `docs/osdu-mapping.md`, `pyproject.toml`

## Context

SPEC.md section 7 cuts a real OSDU deployment — "needs a licence and a large
infrastructure. Mapping plus a validator is enough" — and section 6 asks layer 3
for `docs/osdu-mapping.md` column by column, plus a `validate_osdu.py` that
passes.

Two questions follow from that, and they are not the same question.

**What is the deliverable, if the platform is out of scope?** An OSDU mapping
that nobody can run against an instance risks being a table of names in a
document: unfalsifiable, and therefore worth nothing in the interview where it
will be discussed. It needs something that can fail.

**What validates it?** JSON Schema validation is a solved problem with a
specification and several conforming implementations. This repository has a
standing habit of not adding dependencies — `hugin.common.trino` is a REST
client written over `httpx` rather than the official Trino driver, and ADR 0001
records an ingestion path deliberately built on the standard library. That habit
points at writing a small Draft-07 subset validator here.

## Decision

**The mapping is executable, and its grain changes are explicit.**
`src/hugin/osdu/mapping.py` maps three kinds:

    gold.dim_wellbore    -> osdu:wks:master-data--Wellbore:1.0.0
    gold.fct_log_sample  -> osdu:wks:work-product-component--WellLog:1.0.0
    gold.fct_trajectory  -> osdu:wks:work-product-component--WellboreTrajectory:1.0.0

Two of the three change grain, and that is the substance of the mapping rather
than a detail of it. `fct_log_sample` is one row per reading; a WellLog record
is one *logging run*, carrying a `Curves` array and pointing at a bulk dataset
for the readings. The same for trajectory stations. A mapping that emitted one
OSDU record per fact row would be a mapping that had not read the schema.

**The column-by-column mapping is data, not prose.** `WELLBORE_COLUMNS`,
`WELL_LOG_COLUMNS` and `TRAJECTORY_COLUMNS` are tuples of `ColumnMapping`, and
`docs/osdu-mapping.md` is generated from them. A mapping documented in a
markdown table and implemented in code separately is a mapping that will
disagree with itself within a month.

**The unmapped columns are part of the deliverable.**
`UNMAPPED_GOLD_COLUMNS` and `UNFILLED_OSDU_PROPERTIES` are exported alongside
the mappings, because the interesting half of any schema mapping is what does
not fit. `wellbore_key` has no OSDU home because an OSDU id *is* the identifier
and exporting a warehouse-local md5 would create a second identity for the same
wellbore — the exact failure BR-12 exists to prevent.

**`jsonschema` is added to the dependency list.** This is the part that
reverses the repository's usual answer, so it needs stating plainly: the value
of `validate_osdu.py` is that *something other than me* says the payload
conforms. A validator written here, checking a mapping written here, against a
schema reduced here, would be marking its own homework twice over. An
independent implementation of the specification is the only link in that chain
not authored by this project, and removing it would remove the point.

**The schemas are reduced local copies, and say so.**
`src/hugin/osdu/schemas/` holds three JSON Schema documents carrying the
published `$id` and `x-osdu-schema-source`, the published top-level `required`
(`kind`, `acl`, `legal`), the id and kind patterns, and every property this
project maps. They drop the `AbstractCommonResources` / `AbstractFacility` /
`AbstractSpatialLocation` `$ref` trees, which the published schemas resolve
over the network. `additionalProperties` stays permissive, because a reduced
schema that rejected unknown properties would be rejecting valid OSDU records —
the reduction failing, not the payload.

**Nothing talks to an OSDU instance, and the placeholders look like
placeholders.** `OsduContext` defaults `legal.legaltags` to
`hugin-placeholder-legal-tag` and the ACL groups to `@hugin.example.com`
addresses. A record carrying those cannot be mistaken for one that has been
through a real entitlements service.

## What this costs

- **A dependency that only one module uses.** `jsonschema` is imported by
  `validate_osdu.py` and nothing else. It is in the runtime dependency list
  rather than the dev group because `src/hugin/` imports it, and a module in
  `src/` importing a dev-only package is a boundary violation waiting to
  surprise someone.
- **A pass that means less than it looks like it means.** Green here says the
  envelope, kind, id form and mapped property types are right. It does not say
  an OSDU instance would accept the record — `UNFILLED_OSDU_PROPERTIES` lists
  nine things that are still missing, starting with real entitlements and a
  real legal tag. Both `validate_osdu.py`'s docstring and the schema README say
  this, in those words, because a reader who takes the green line at face value
  has been misled by us rather than by themselves.
- **Reduced schemas drift.** OSDU publishes new versions; these copies are
  1.0.0, read on 2026-08-13. Nothing here notices when that changes.

## Alternatives considered

**A hand-written Draft-07 subset validator.** Consistent with ADR 0001 and with
`hugin.common.trino`, and perhaps 120 lines. Rejected on the ground above: the
independence of the checker is the deliverable. It is worth noticing that the
habit was right in the other two cases for the same reason it is wrong here —
a REST client is infrastructure, and a conformance checker is evidence.

**Vendoring the published schemas whole.** The honest maximum. Rejected because
they resolve `$ref` against `schema.osdu.opengroup.org`, so either the network
is hit during a test run — a validator that quietly requires internet access is
worse than one that does not run — or the entire transitive definition tree is
vendored, a few hundred kilobytes of JSON of which this project reads perhaps
thirty lines.

**Standing up an OSDU instance.** Explicitly cut by SPEC.md section 7. Even the
lightweight community deployments want a Kubernetes cluster and a cloud identity
provider, which is two more things SPEC.md section 7 also cuts.

**Mapping production data too.** `fct_production_daily` has an OSDU home in
newer releases. Rejected as scope: SPEC.md section 6 names three kinds, and
three well-argued mappings are worth more than five hurried ones. It is recorded
in `UNMAPPED_GOLD_COLUMNS` rather than left for a reader to notice.

## Consequences

- `docs/osdu-mapping.md` is generated by `scripts/osdu_report.py` from the
  mapping tuples. Editing the document by hand is a mistake the next
  regeneration corrects.
- `python -m hugin.osdu.validate_osdu` needs the compose stack for its gold
  read, but `--records` validates from disk, so CI can check payloads without
  Trino.
- `tests/test_osdu.py` runs the mapping over fixture rows and validates the
  output, so the mapping is covered without a warehouse.
- Adding a fourth kind means adding a `ColumnMapping` tuple, a reduced schema,
  and an entry in `KINDS`. The document follows.

## When this should be revisited

If a real OSDU sandbox becomes available — some clouds offer one at low cost —
the reduced schemas should be replaced by the published ones, fetched at build
time rather than vendored, and the nine unfilled properties should turn into
either real values or a shorter list. Until then, the mapping is the claim and
the validator is what keeps it honest.
