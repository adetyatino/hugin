# Reduced OSDU well-known schemas

These are **reduced local copies**, not the published OSDU schemas. Read that
sentence again before trusting a green validation run.

## What they are

Three JSON Schema documents, one per kind this project maps to:

| File | `x-osdu-schema-source` | Published `$id` |
|---|---|---|
| `master-data--Wellbore.1.0.0.json` | `osdu:wks:master-data--Wellbore:1.0.0` | `https://schema.osdu.opengroup.org/json/master-data/Wellbore.1.0.0.json` |
| `work-product-component--WellLog.1.0.0.json` | `osdu:wks:work-product-component--WellLog:1.0.0` | `https://schema.osdu.opengroup.org/json/work-product-component/WellLog.1.0.0.json` |
| `work-product-component--WellboreTrajectory.1.0.0.json` | `osdu:wks:work-product-component--WellboreTrajectory:1.0.0` | `https://schema.osdu.opengroup.org/json/work-product-component/WellboreTrajectory.1.0.0.json` |

Each keeps, from the published schema:

* the top-level envelope and its `required` list — `kind`, `acl`, `legal`,
  which is exactly what the published schemas require and no more;
* the `kind` pattern, so a payload declaring the wrong kind fails;
* the `id` pattern, which is what enforces `<partition>:<type>:<identifier>`;
* every property this project actually maps, with its published type;
* `ExtensionProperties`, because that is where a non-OSDU value legitimately
  goes.

Each **drops**, deliberately:

* the `AbstractCommonResources`, `AbstractMaster`, `AbstractFacility`,
  `AbstractSpatialLocation` and `AbstractFacilityVerticalMeasurement`
  definition trees, which are resolved by `$ref` against
  `schema.osdu.opengroup.org` in the published documents;
* every property this project does not map, of which there are many.

## Why reduced rather than vendored whole

The published schemas resolve `$ref` over the network. Vendoring them whole
means vendoring the transitive closure of the abstract definitions — a few
hundred kilobytes of JSON that nothing here reads — and a validator that
silently fetches over the network during a test run is worse than one that
does not run at all. `additionalProperties` is left permissive for the same
reason: a reduced schema that forbade unknown properties would reject valid
OSDU payloads, which would be the reduction failing rather than the payload.

## What a pass therefore means, and does not

A pass means: the envelope is right, the kind and id are well formed, the
mapped properties have the published names and types, and nothing that must be
present is missing.

A pass does **not** mean an OSDU instance would accept the record. That needs
the real schema, the real reference-data lists behind every `*ID` property, and
a real `acl`/`legal` from the platform. ADR 008 says why that line is where it
is, and `docs/osdu-mapping.md` lists what a real deployment would still reject.

Provenance: property names and types were read from the published 1.0.0
schemas (Apache-2.0, The Open Group), 2026-08-13.
