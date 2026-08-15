# ADR 000 — Title, in the form of the decision taken

Status: proposed | accepted | superseded by ADR NNN
Date: YYYY-MM-DD
Scope: the code, table, or stage this binds

## Context

What forced a decision. The constraint, the deadline, the property of the data —
whatever made "just pick one" not good enough. Facts here, no advocacy: if a
reader disagrees with the decision, they should still agree with this section.

## Decision

One sentence, in the active voice, saying what was chosen. Then the specifics
that make it actionable: versions, table names, config keys.

## Alternatives considered

At least one, honestly stated. An alternative described only by its weaknesses
means the comparison was not made. For each: what it would have bought, and the
specific reason it lost here — not in general.

## Consequences

What this costs. New operational burden, capabilities given up, work now
required elsewhere. Positive consequences belong here too, but the negative ones
are the reason this section exists.

## When this should be revisited

The condition that would reopen the question — a data volume, a target
platform, a dependency reaching a version. "Never" is a legitimate answer if it
is true.

---

Conventions: files are `NNN-kebab-case-title.md`, numbered in the order taken,
never renumbered. `SPEC.md` reserves 001, 002, and 005; the rest are allocated
as decisions arrive. One exception predates this template:
`0001-stdlib-only-ingestion.md` uses a four-digit number and is referenced by
generated output in `docs/data-inventory.md`, so it keeps its name.
