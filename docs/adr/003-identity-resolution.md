# ADR 003 — Staged deterministic normalisation for identity resolution, not fuzzy matching

Status: accepted
Date: 2026-08-13
Scope: `src/hugin/identity/`, `silver.wellbore_identity`,
`silver.wellbore_identity_unresolved`, `mart_identity_coverage`

## Context

One physical hole in the Volve field appears under many written names. The same
wellbore is `15_9-F-12` in a per-well archive, `Norway-Statoil-15_$47$_9-F-12`
in a drilling-system export, `NO 15/9-F-12` in the daily drilling reports,
`15_9_F-12` in a LAS header, and `P-F-12` in the Eclipse model. Operator labels
shift with corporate history — Statoil, StatoilHydro, Statoil. `$47$` is an
escape for `/`. Sidetracks are marked by a suffix that is sometimes separated by
a space and sometimes not: `15/9-F-15 A`, `15/9-F-15A`, `15/9-F15S`.

Nothing in the platform works until these are reconciled. Production volumes,
drilling telemetry, logs and trajectories all key on the wellbore, and joining
them on the wrong key does not fail loudly — it produces a plausible number for
the wrong hole.

The dataset also contains three official identifier systems, and this turns out
to matter more than any string rule: NPD (Sodir) register numbers in the daily
drilling reports and the production workbook, Statoil well-master `W-`/`B-`
numbers in the older drilling exports, and UUIDs in the newer ones.

## Decision

Resolve identity with **ordered deterministic stages**, each a pure function
that records what it did, and let an official identifier overrule a parsed name.

Stages, in BR-12's order — `unescape_slash`, `strip_prefixes`,
`canonical_separators`, `split_sidetrack`, `classify_identifier`. The
composition returns the intermediate value at every step and the name of the
stage that last changed the string, so a mapping can be explained rather than
merely asserted.

Order of authority when they disagree:

1. a manual mapping, if a human recorded one,
2. an official identifier recorded next to the name **by the system entitled to
   name it**,
3. the name itself, through stages a-d,
4. nothing — the identity goes to `wellbore_identity_unresolved` with a reason.

Rule 2 has a sharp edge that is worth stating. Production data writes
`NO 15/9-F-4 AH` and, in the next column, NPD code 5693, whose registered name
is `15/9-F-4`. Reading the name alone invents a sidetrack `AH` that no register
knows; the identifier says otherwise and wins. But the reverse is also guarded:
only a name that is the identifier's *own registered name* may teach the index
what that identifier means. Letting `NO 15/9-F-4 AH` define NPD 5693 would make
the register agree with the operator's spelling and destroy the only independent
check available. That distinction is one boolean in the code and the difference
between five false conflicts and none.

## Alternatives considered

**Fuzzy string matching** — Levenshtein, Jaro-Winkler, or a token-set ratio over
all names with a similarity threshold. Rejected, and not narrowly:

- *The near-misses here are real distinctions.* `15/9-F-15` and `15/9-F-15 A`
  differ by two characters and are different holes drilled years apart.
  `15/9-F-1 B` and `15/9-F-11 B` differ by one. `15/9-19 B` and `15/9-19 BT2`
  are a wellbore and its technical sidetrack. Any threshold loose enough to
  join `15_9_F-12` to `15/9-F-12` is loose enough to join wellbores that must
  stay apart, because the *within-wellbore* spelling variation is larger than
  the *between-wellbore* distance. There is no threshold that separates them.
- *A score is not an explanation.* "0.92 similarity" cannot be reviewed by
  someone who knows the field. "Stage c rewrote the separators, stage d took
  `S` off as a sidetrack" can, and the person who can spot the error is a
  drilling engineer, not the author of the matcher.
- *Thresholds are silent when they drift.* A new source with a different
  convention shifts scores everywhere at once, and nothing fails.
- *The hard cases are not spelling problems.* `P-F-14` versus `15/9-F-14` is not
  a near-miss — it is a different naming scheme, and no edit distance recovers
  the block number. It needs a declared rule, which is what it gets.

Fuzzy matching earns its place where names are free text written by people —
company names, addresses. These are structured identifiers written by machines
following conventions. Conventions can be implemented; guesses cannot be
reviewed.

**One large regular expression.** Rejected because BR-12 requires showing which
step decided a match, and a single pattern that handles `$47$`, prefixes,
separators and sidetracks in one go cannot say which alternation fired. It is
also the shape that rots fastest: every new source adds an alternative branch to
a pattern nobody can safely edit.

**A hand-maintained mapping table only.** Rejected as the primary mechanism — 379
identities and growing, and every new delivery would need manual work before any
data could load. Kept as the *last* resort: `identity-manual-mapping.csv` is
read ahead of every rule and surfaces as `match_method = MANUAL`, so a human
decision is possible, recorded, and visible in the coverage report.

**Guessing the unresolved ones.** Rejected on the same grounds as SPEC.md gives:
a wrong wellbore is worse than a gap, because a gap is visible in
`mart_identity_coverage` and a wrong attribution is not.

## Consequences

- Every mapping is explainable and reproducible. Running the crosswalk twice
  gives the same answer, and the `evidence` column says why each row landed
  where it did.
- Confidence is a stated property of the *path*, not a similarity score:
  1.00 for an official identifier or an already-canonical name, 0.95 for stages
  a-d, 0.90 for the WITSML "Main Wellbore" descriptor and manual mappings, 0.70
  where the block had to be assumed.
- The rules are specific to Norwegian Continental Shelf naming. A field outside
  the NCS would need a new stage c. This is deliberate: a rule that only works
  where it was validated is better than one that appears to work everywhere.
- Coverage is not 100% and is not meant to be. 42 of 379 identities stay
  unresolved, most of them because they never named a wellbore in the first
  place — delivery folders, planned relief-well locations, placeholder UWIs.
- The simulator names carry a permanent asterisk. Eclipse names omit the block,
  so resolving them means assuming the only field in the dataset — an
  assumption that is recorded, given 0.70 confidence, and required to be
  corroborated by a source that stated its own block. `I-F4G` fails that test
  and stays unresolved rather than becoming an invented sidetrack `G`.

## What happens when a new well arrives

This is the question that decides whether the design survives contact with more
data, so it is worth being concrete. A new wellbore — say `15/9-F-16 B` —
arriving in a new delivery:

1. **If it follows NCS naming**, nothing needs doing. Stages a-d resolve it, it
   appears in the crosswalk as `NORMALIZED`, and `dim_wellbore` gains a row. No
   code change, no threshold to retune. This is the common case and the reason
   for the design.
2. **If it carries an official identifier and an unfamiliar name**, the
   identifier resolves it, provided some source pairs that identifier with a
   registered name. The `REF` source (Sodir FactPages) exists in SPEC.md
   section 2 for exactly this.
3. **If it follows a convention this code has never seen** — a new operator's
   export with a different prefix, say — it lands in
   `wellbore_identity_unresolved` with the stage that refused and why. It is
   *visible*, in a report, with a count. Nothing silently attaches to the wrong
   wellbore, and no downstream number moves.
4. **Someone then decides**: add a stage-b prefix, extend the sidetrack grammar,
   or record a manual mapping. Whichever it is, the change is a code or data
   diff with a test naming the case, reviewable by someone who knows wells.

The cost is honest: unfamiliar conventions require human attention rather than
resolving themselves. That cost is the point. A fuzzy matcher would have absorbed
the new well silently, at some similarity score, and the first sign of trouble
would have been a production total that did not reconcile — BR-02 failing months
later, with no way back to the cause.

The operational procedure belongs in `docs/runbook.md`, which SPEC.md section 6
already requires to cover "adding a new well identity". This ADR is the reason
that procedure is short.

## When this should be revisited

If a source ever arrives with genuinely free-text well names — a scanned report
index, an operator's spreadsheet of comments — the deterministic stages will not
reach it, and a *reviewed* candidate-suggestion step might be worth adding:
fuzzy matching to propose, a human to accept, `match_method = MANUAL` to record
it. That is a different thing from fuzzy matching deciding, and it is the only
form of it this project would accept.
