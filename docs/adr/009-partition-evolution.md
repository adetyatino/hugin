# ADR 009 — Partitioning is wrong in two directions, and both are the same decision

Status: accepted
Date: 2026-08-13
Scope: `transform/models/`, `src/hugin/ingestion/bronze.py`, `scripts/compact.py`

## Context

Two measurements in `docs/performance.md` miss their SPEC.md section 13 targets,
and it took measuring both to see they are one problem.

**Bronze is partitioned far too finely.** SPEC.md section 3 requires every
bronze column to be `varchar`, including `_replay_date`, because that is what
makes replay from bronze possible without re-ingesting. SPEC.md section 4.1
requires bronze to be partitioned by `_replay_date`. A partition transform on a
`varchar` can only be identity, so the field's 3,044 days become 3,044
partitions. `bronze.prod_daily` holds 14,859 rows in **3,044 files** with a
median of seven rows each and a mean file size of **6.9 KB**, against a target
of 128–512 MB. `ALTER TABLE … EXECUTE optimize` moved the overall file count
from 4,136 to 4,131 — **0.1%**, against a target of 70% — and it was right to:
`optimize` rewrites files *within* a partition, and each of those partitions
already holds exactly one file.

**Gold is not partitioned at all.** `gold.fct_log_sample` has no partitioning
property. A depth-range query returns in 0.145 s against a 3 s target, and
`EXPLAIN ANALYZE` shows why the number is uninformative: `Input: 30421 rows,
Filtered: 93.32%, Splits: 1`. Every row is read and 93% discarded after reading.
The target's second clause — "partition pruning active" — is not met, because
there is nothing to prune.

Stated together: **bronze has 3,044 partitions holding seven rows each, and gold
has one partition holding everything.** Neither is a tuning oversight. Both
follow from decisions taken before there was any data to measure, which is
exactly when partitioning decisions get taken and exactly when they cannot be
checked.

## Decision

**Do not change the layout in this delivery. Record the evidence, name the
mechanism, and leave both numbers red.**

Three reasons, in order of weight.

**1. The measurements are the deliverable.** A portfolio that reports 70% file
reduction because the partitioning was quietly fixed before measuring has hidden
the more interesting fact: that a defensible reading of two SPEC.md sections
produces a table that cannot be compacted. SPEC.md section 13 asks for the misses
*and their analysis*, and the analysis is worth more than the number.

**2. The fix is a real design change and belongs with real data.** Bronze at the
full delivery is on the order of ten million log samples, not thirty thousand.
Choosing a partition spec against a bounded load would be choosing it against the
wrong distribution — the same mistake, made faster.

**3. Iceberg was chosen for precisely this.** ADR 001 picked Iceberg over Delta
and Hudi partly for partition evolution, and that capability has not been used.
Using it under pressure, with the before-and-after measured, is a better
demonstration than never having needed it.

### What the fix is, when it happens

**Bronze — coarser partitions than the delete predicate.**

1. Add a typed `_replay_month` alongside the `varchar` `_replay_date`. The
   varchar stays: SPEC.md section 3's rule is about *values*, and a derived
   partition column is not a cleaned value.
2. Evolve the partition spec to `month(_replay_month)`. Existing data keeps its
   old layout, new data lands monthly, and both stay readable — this is the
   whole point of partition evolution. 3,044 partitions become 100.
3. The idempotent load still deletes by `_replay_date`, which is now *finer*
   than the partition. That is supported and is the resolution of the tension:
   a delete predicate may be finer than the partition spec, at the cost of a
   rewrite rather than a metadata-only drop. The daily grain is right for the
   delete and wrong for the layout, and they do not have to be the same thing.
4. Then `optimize` has work to do. A month of production is ~210 rows — still
   small — but a month of telemetry at 5-second sampling is ~500,000, which is
   where the 128–512 MB target becomes reachable.

**Gold — sort before partition.**

`fct_log_sample` is the table with the pruning target, and the cheaper fix is
the better one. Iceberg keeps per-column min/max in the manifest; the existing
single file already reports `depth_m: (min: 2480.0051, max: 4089.0)`. Writing
the table sorted by `depth_m` lets file statistics skip whole files for a depth
range **with no partition spec at all**, at the cost of a sort on write.

Partitioning by `source_file` — one logging run — is the fallback if sorting is
not enough. It is second choice because the natural query is by depth and by
curve, and a partition on neither of those helps them.

## What this costs

- **Two red numbers on the front page.** `docs/performance.md` reports 0.1%
  against 70%, and 6.9 KB against 128–512 MB, and will keep reporting them.
- **A slow bronze scan at scale.** 3,044 partitions is not painful at this data
  size and would be at ten million rows: every query plans over 3,044 manifest
  entries before reading anything.
- **A pruning claim that cannot be made.** SPEC.md section 6 lists
  "`fct_log_sample` with benchmarked partitioning, meeting the section 13
  target" as a layer-3 item. It is measured and not met, and the CV bullet has
  to say so.

## Alternatives considered

**Partition bronze by month now.** The obvious fix, perhaps two hours of work.
Rejected because it would be chosen against 14,859 rows and would have to be
chosen again against ten million, and because doing it before writing this ADR
would delete the evidence that the collision between sections 3 and 4.1 exists
at all.

**Drop the `_replay_date` partition entirely.** Would fix compaction outright.
Rejected: the partition is what makes the idempotent delete a metadata operation
instead of a full-table rewrite, and idempotency is BR-01's whole claim.
Trading a proven property for a file-size number is the wrong trade.

**Type `_replay_date` as a `date` in bronze.** Would allow `month()` as a
transform directly. Rejected because SPEC.md section 3 is explicit that bronze
does not type anything, and that rule is what lets a replay be rebuilt from
bronze without re-reading the sources. A derived column beside it, as above,
gets the same result without breaching the rule.

**Partition `fct_log_sample` by `curve_mnemonic`.** 196 distinct values, and it
would help a per-curve query. Rejected: it would produce 196 partitions of a
1.29 MB table — bronze's mistake, in gold, arrived at from the other direction.

## Consequences

- `docs/performance.md` carries both misses with their `EXPLAIN ANALYZE` and
  `$files` evidence, not a summary of them.
- `scripts/compact.py` stays as it is. It is not broken; it is compacting
  correctly and finding nothing to do.
- The next person to touch partitioning has the before numbers to compare
  against: 4,136 files, 6.9 KB mean, 3,044 partitions on `prod_daily`; one file,
  one split, 93.32% filtered on `fct_log_sample`.

## When this should be revisited

At the first full LAS load, or the first sustained telemetry stream — whichever
produces a table over about a gigabyte. Both fixes should be made together, and
the same three measurements re-run: file count before and after `optimize`, mean
file size, and `EXPLAIN ANALYZE` on the depth-range query showing `Physical
input` fall rather than `Filtered` stay high.
