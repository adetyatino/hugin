# Interview notes

Answers to the question bank in `SPEC.md` section 14. Every answer names a
file, a table or a number in this repository, because an answer that could have
been given about any project is not an answer about this one.

> **A note on authorship.** This file was drafted from the repository's own
> evidence — the models, the tests, the measurements in `docs/performance.md`
> and `docs/slo.md`. The reasoning is the code's; the delivery has to be the
> author's. Read it, disagree with the parts you disagree with, and rewrite
> those in your own words before an interview. An answer you cannot defend
> under a follow-up question is worse than no answer, and the last question in
> this file is the one where that matters most.

---

## Modelling

### Why is `fct_production_daily` at wellbore-day grain and `fct_production_monthly` at wellbore-month, instead of one table?

Because they are two different measurements of the same thing, and the
difference between them is information the business needs.

The daily table is what the field's allocation system computed each day. The
monthly table is what the operator *reported* for that month — an accounting
figure that goes through allocation adjustments, well-test reallocation and
month-end corrections. They are not derivable from one another. Summing the
daily rows to a month does not reproduce the reported monthly figure, and that
is not a defect in either.

BR-02 exists to measure the gap rather than to close it.
`mart_allocation_reconciliation` compares 497 wellbore-months: **493 agree
within the ±2% tolerance, 4 breach it, worst at −20.5%**. Both figures are kept.
`assert_br02_reconciliation_finds_real_disagreement.sql` fails if the model ever
finds *nothing* — a reconciliation that always agrees is a reconciliation that
is not comparing anything.

Collapsing them into one table forces a choice about which number is "the"
production for a month, and whichever you pick, the other becomes invisible.
The 4 breaching months are the most interesting rows in the warehouse, and one
table would delete them.

The grain difference also has a plain modelling consequence: the daily fact
joins to `dim_date` on `date_key`, the monthly one on `month_key`. Two grains,
two conformed date roll-ups, one dimension.

### Why does `dim_wellbore` need SCD2 while `dim_well` is fine as SCD1?

Because a wellbore has attributes that change over time and a well, in this
data, does not.

`dim_wellbore` tracks two things, and only one of them is genuinely dated:

- **Well role changes, and it is dated.** Daily production records `WELL_TYPE`
  per day. `15/9-F-1 C` appears as `OP` on some days and `WI` on others — the
  wellbore was converted between producer and water injector, more than once,
  and the dimension carries **four versions** with the dates it happened:
  injector from 2014-04-07, producer from 2014-04-08, injector again from
  2014-07-07, producer from 2014-07-08. That is a real SCD2 event with real
  dates, and it is what makes the dimension more than decoration. 18 versions
  across 7 wellbores.
- **The operator label is tracked but not dated.** `Statoil`, `StatoilHydro`,
  `STATOIL PETROLEUM AS` come from LAS headers and archive names, none of which
  say *when* the label applied. So the label is attached and tracked by the same
  mechanism, and the moment a dated source disagrees the macro emits a new
  version with no code change. Inventing dates for the Statoil/StatoilHydro
  transition would be fabricating history to make a dimension look richer.

`dim_well` carries `well_code`, `wellbore_count`, `sidetrack_count`,
`source_system_count`. None of those is a business attribute that changes and
that anyone would want to query as-of a date; they are counts that are correct
as of the current load. Making it SCD2 would double its rows to record that a
count changed when a new file arrived, which is a fact about the load, not about
the well.

The honest short version: **SCD2 costs a join predicate on every query, and you
pay it where something real changes.** Here it changes on the wellbore.

### If a cross-grain reconciliation difference exceeds tolerance, which side do you fix?

Neither, and that is the design.

BR-02's tolerance is 2%, set once in `dbt_project.yml` as
`allocation_tolerance`, and the model flags rather than corrects. Four
wellbore-months breach it. The reasoning:

**You cannot fix what you cannot attribute.** The daily figures come from the
field allocation system; the monthly ones come from the operator's reported
production. A −20.5% variance means one of: a well test reallocated volume
after the daily numbers were written, a month-end correction, a shut-in period
counted differently, or a genuine data error. Nothing in this delivery
distinguishes them. Picking a side and adjusting means writing a number that no
source system produced, into a table that looks like it came from one.

**What I would do instead**, in order:

1. Report it — the variance is a column and a flag, `is_out_of_tolerance`,
   queryable and on the dashboard.
2. Take the four cases to whoever owns the allocation process. This is not
   evasion: in a real operator, the reconciliation report is *the deliverable*
   and the resolution is a business decision made by production accounting.
3. If a rule emerges — "monthly wins after a well test" — implement it as a
   named, tested rule with the raw figures preserved beside it, the way BR-03
   keeps `reported_oil_sm3` next to the split-out `oil_sm3`.

**What I would not do** is widen the tolerance until the flag goes away. It is a
variable so that the number is stated once and visible, not so that it is easy
to move.

---

## Pipeline

### How did you make this DAG idempotent, and how do you prove it?

Three mechanisms, and then a measurement.

**1. The date comes from the interval, never from the clock.**
`hugin_daily.resolve_replay_date` reads `data_interval_start` and maps it
through `hugin.common.replay`. A task re-run next week for the same interval
computes the same replay date. If it read `datetime.now()`, every re-run would
write a different partition and "idempotent" would be meaningless. ADR 002 is
why `REPLAY_EPOCH` has no default: a clock defaulting to "today" makes every
run's output depend on the day it ran.

**2. Delete-then-register, per partition, unconditionally.** Every reader
issues `DELETE FROM … WHERE _replay_date = …` before registering anything —
*including when it produced no rows*. That last part is deliberate: re-running
a date after the source shrank must not leave stale rows behind. It costs
about 2 seconds per empty reader, which is most of the 53-second ingest figure,
and `docs/performance.md` says so rather than hiding it.

**3. Dedup by `_row_hash` in silver.** The hash covers business columns only, so
a row re-ingested by a later batch collapses onto the first rather than
duplicating. Ordering by `_ingested_at, _batch_id` keeps the choice
deterministic.

**The proof is a measurement, twice over.**

- `tests/test_bronze_integration.py` loads a replay date twice against the
  running stack and asserts the same row count, the same `_row_hash` set, and
  only the newest `_batch_id` present.
- The 24-month backfill was run twice: **26.2 s then 23.9 s, with identical
  table state** — same row counts (14,859 and 497), same distinct `_row_hash`
  counts, same checksum over the hashes. That is in `docs/performance.md` as a
  table, because "idempotent" asserted is worth nothing and "idempotent"
  measured across two consecutive runs is worth something.
- `assert_silver_dedup_by_row_hash_left_no_duplicates.sql` fails the build if
  the dedup ever stops working.

One thing I would flag before being asked: `max_active_runs=1` on the DAG is
part of this. Twenty-four concurrent runs would race for the same Iceberg
partitions and the loser would write rows the winner had already deleted.
Idempotency per run does not give you idempotency under concurrency, and the
runbook says not to raise that number to make a backfill faster.

### What happens if the streaming job dies mid micro-batch?

Nothing is lost and nothing is double-counted, and this was tested by doing it
rather than by reasoning about it.

Spark Structured Streaming commits Kafka offsets to the checkpoint only after a
micro-batch's write has succeeded. A job killed mid-batch has not committed
those offsets, so on restart it re-reads from the last committed position and
re-processes the partial batch. The Iceberg write is what makes the
re-processing safe: it is an atomic commit, so a half-written batch is not
visible and is not partially committed.

**Measured**: the Spark container was killed outright with `docker kill` while
the stream was running, 3,000 further samples were produced while it was down,
and the job was resubmitted against the same checkpoint. Afterwards: **3,000
rows, 3,000 distinct `(wellbore_uid, ts)` keys, 0 duplicates introduced.**

Two things carry the weight here that are worth naming:

- **`dropDuplicatesWithinWatermark` bounds the state store.** A plain
  `dropDuplicates` keeps every key ever seen, so a long-running job grows
  without limit until it dies of memory — which is a much worse failure than
  the one being defended against.
- **Deleting the checkpoint is the dangerous recovery, not the safe one.**
  Restarting from `earliest` replays the whole topic; BR-07's dedup absorbs it —
  measured at 10,500 messages of which 10,000 were duplicates leaving 500 rows —
  but only for events still inside the watermark. Anything older lands in
  `drilling_telemetry_late`. `docs/runbook.md` §2 says this in the place someone
  would actually reach for it.

### Why a 10-minute watermark and not some other number?

It is bounded below by the source's lateness and above by state size and
correctness, and 10 minutes sits between them for this source.

**Lower bound — real lateness.** WITSML telemetry arrives from a rig link that
buffers. A watermark shorter than the worst realistic buffering flush sends
legitimate events to the late table, where they are counted but not aggregated.
Whatever number is chosen has to exceed the observed arrival skew.

**Upper bound — two costs.** State size: the dedup state store holds every key
inside the watermark, so it grows with watermark × event rate. And staleness:
Spark cannot finalise a window until the watermark passes it, so a longer
watermark delays every windowed result by that amount.

**Why not tune it to zero late events.** That is the trap. Extending the
watermark until nothing is late means the state store grows without a stated
bound and the job becomes fragile in a way that shows up under load rather than
in testing. The late table exists so that lateness is *counted* instead of
prevented — the count is on the dashboard, and a rising count is a signal about
the source rather than a reason to move the number.

**What I would actually do to set it properly**, and have not: measure the
distribution of `_ingested_at - ts` over a real stream and set the watermark at
a stated percentile — p99.9, say — with the residual going to `_late` on
purpose. Ten minutes is a defensible starting value from SPEC.md, not a measured
one, and I would rather say that than dress it up.

### Why Iceberg and not Delta or Hudi?

ADR 001 has the full argument. The short form, and the part I would actually
say:

- **Engine-agnostic, and this project cashes that in.** The same tables are
  read by Trino, by DuckDB through the Parquet files, and by Spark for the
  streaming write. Delta's ecosystem is strongest inside Spark and Databricks;
  this stack is deliberately not that, and SPEC.md section 12's portability
  claim would be much harder to make on a format with one first-class engine.
- **Partition evolution**, which was chosen for and — I would volunteer this —
  has **not been used yet**, and is now the single most consequential open item
  in the repository. Bronze has 3,044 partitions holding seven rows each,
  because SPEC §3 requires a `varchar` `_replay_date` and SPEC §4.1 requires
  partitioning by it, and a partition transform on a varchar can only be
  identity. Compaction achieved **0.1%** against a 70% target. The fix is
  exactly the capability the format was chosen for. ADR 009.
- **Hidden partitioning and snapshot isolation** make the delete-then-register
  idempotent load a metadata operation rather than a rewrite, which is what
  makes the 24-month backfill take 26 seconds.

The honest caveat: at this data size none of the three would perform
differently, so the choice is about the interfaces and the operational story,
not about speed. Anyone who tells you they benchmarked table formats on 15,000
rows is telling you about their benchmark.

---

## Data

### There are unmapped wellbore identities. Why not just guess?

Because a guess and a gap fail differently, and the guess fails worse.

A gap is visible. An unresolved identity goes to
`silver.wellbore_identity_unresolved` with a reason, is counted in
`mart_identity_coverage`, and the facts that reference it get a surrogate
`UNRESOLVED` key rather than a NULL one — so nothing is dropped and nothing
joins to the wrong place. Somebody querying per-well production sees a gap and
asks about it.

A guess is invisible and it is *wrong in a specific direction*: it attributes
production to a wellbore that did not produce it. Both wells are now wrong —
the one that gained volume and the one that lost it — and nothing in the output
distinguishes that from a real operational change. A well quietly credited with
another well's oil looks exactly like a well that did well.

The decisive case in this data makes the argument concretely. Production writes
`NO 15/9-F-4 AH`. Parsed as a name, `AH` is a sidetrack — and no register knows
a sidetrack `AH` on that well. The NPD code in the same row, 5693, resolves to
`15/9-F-4`. **The identifier wins, the name is recorded as a variant, and the
disagreement is reported.** A fuzzy matcher confident enough to invent the
sidetrack would have created a wellbore that does not exist and split one
well's history across two.

That is also why ADR 003 chose staged deterministic normalisation over fuzzy
matching. `hugin.identity.normalize` has five separately testable stages so
that the answer to "why did this resolve" is *"stage c rewrote the separators,
stage d took `B` off as a sidetrack"* — not "the regex matched" and not "the
similarity was 0.87".

`mart_identity_coverage` is the model that keeps this honest: coverage can go
*down* when a new delivery arrives with unfamiliar names. A crosswalk that
filtered its own failures would report 100% forever.

### How do you know your datum transformation is correct?

I do not, for this delivery, and the reason is worth being precise about
because it is a better answer than a confident one.

**BR-10 is not satisfied and cannot be from these sources.** The directional
surveys declare an *azimuth* reference — grid north — not a coordinate
reference system. `fct_trajectory.northing_offset_m` and `easting_offset_m` are
offsets from the well reference point, not projected coordinates, which is why
they are named `_offset_`. `source_crs` is NULL for all 475 stations. There is
nothing to transform, and CLAUDE.md forbids assuming one — Volve-era data is
ED50 / UTM zone 31N and modern systems are WGS84 or ETRS89, and in the North Sea
that difference is hundreds of metres. Hard-coding ED50 would be right by luck
and silent when wrong.

The SLO for this is **kept at 100% and left breached** rather than lowered to
fit, because lowering it would encode the absence as acceptable, and the day a
projected coordinate does arrive it must carry its datum.

**What I *can* show is the validation method**, applied to the part that does
have an independent check — the trajectory geometry:

1. **Against the contractor's own numbers.** Recomputing TVD from raw MD,
   inclination and azimuth lands within **3 mm** of the surveying contractor's
   computed values on a 469-station survey — three orders of magnitude inside
   SPEC.md's 0.1% threshold. That is this implementation against software used
   to steer a well.
2. **Against an independent measurement.** The VSP checkshot knows nothing about
   the directional survey, which is exactly why it is the right check. It
   **disagrees**: mean **+32.45 m** over 142 comparable points, with structure —
   a few metres to 2400 m, then divergence to +82 m.
   `docs/trajectory-validation.md` reports that as measured and lists the
   candidates with what would settle each, rather than picking one. The shallow
   offset is probably a depth datum (the checkshot declares MSL; surveys are
   normally RKB, and Volve's wellhead elevation is 54.9 m). The deep divergence
   is not explained by a datum — a reference offset does not grow from 6 m to
   82 m over 250 m of hole — and the most likely explanation is that the VSP was
   run in a different hole.

The methodological point, which is the one worth making in an interview:
**agreeing with the source that produced the number proves the arithmetic;
disagreeing with an independent measurement is the finding.** The validation
also caught the delivery declaring four surveys in **radians** — `0.371` reads
plausibly as degrees and is 21.3°, and reading it as degrees puts computed TVD
**188 m** out. `Station.from_uom()` now raises on a missing or unrecognised unit
rather than defaulting to degrees, because defaulting would have hidden it.

### What is the problem with `-999.25`, and why not hard-code it?

The sentinel is a property of the file, not a constant, and this delivery proves
it: it declares **four** spellings — `-999.25`, `-9999`, `-999.2500` and
`-999.25000` — each in the file that uses it.

Code comparing against the literal `-999.25` would carry three of those through
as measurements. And they do not announce themselves. A depth reading of −9999
does not look wrong in an average until the average is wrong; a gamma-ray curve
with a few −999.25 values has a mean that is plausible, monotone in the right
direction, and false. The failure is silent by construction, which is what makes
it worth a business rule.

BR-08's implementation reads the sentinel per file at ingest
(`src/hugin/ingestion/las.py`), carries it onto the sample row, and
`hugin_null_if_sentinel` in `transform/macros/dialect.sql` compares each reading
against **its own file's** declared value. A file declaring something new needs
no code change. Two details that came from the data rather than from the spec:

- the macro also treats the string `nan` as a sentinel, because `lasio`
  substitutes NaN for the declared null when it reads a LAS 2.0 file — so the
  sentinel arrives at bronze already transformed, and comparing only against
  the declared number would miss it;
- `was_sentinel` survives into `fct_log_sample`, so the count of discarded
  readings is *countable* rather than inferred from the absence of rows.
  `assert_br08_sentinel_conversion_is_counted_not_hidden.sql` enforces that.

The general principle, which is the same one as the CRS: **hard-coding a value
read from a header is a bug even when it happens to be right, because it is
right by luck and silent when wrong.**

---

## Decisions

### The data is a static archive. How does this project demonstrate orchestration?

By making the archive's own timeline into the schedule, rather than pretending
a static file needs a daily job.

BR-01's replay clock (`src/hugin/common/replay.py`, ADR 002) maps Airflow's
`data_interval` onto the field's 2008–2016 life as a pure function of the
interval — exact rationals, no wall clock, no clamping at either end. At the
default speed, one real day is one field month, so the field's whole ~100-month
life replays in ~100 real days.

What that buys is not cosmetic. It makes the following *real* rather than
simulated:

- **Incremental loads.** Each run has a genuinely new set of dates to load, and
  a partition that did not exist before.
- **Backfill.** Reprocessing 24 replay months is an actual reprocessing of an
  actual range: measured at 26.2 s, and 23.9 s the second time with identical
  table state.
- **Idempotency.** A re-run for the same interval must produce the same
  partition, which is only testable if the date is derived from the interval.
  26 tests named `test_br01_*`.
- **Late-arriving data and catch-up.** `catchup=True` with
  `max_active_runs=1` behaves exactly as it would on a live source.

The alternative — a DAG that reloads the same static file every night — proves
that Airflow can be installed. This proves the pipeline handles time.

I would also concede the limit unprompted: the replay clock does not simulate
*arrival* variability. Real sources deliver late, out of order, and sometimes
twice. The streaming path exercises that (watermark, late table, dedup); the
batch path does not, and a replay clock cannot manufacture it honestly.

### Why build a local stack when the data is already on Databricks?

ADR 005 is the written answer; four points, and the fourth is the one that
actually persuades.

1. **Building the components proves understanding of them.** Catalog, table
   format, orchestration, engine — assembling them is a different claim from
   being able to click a managed service. This repository has a JDBC Iceberg
   catalog on Postgres, a REST client written against Trino's protocol, and a
   partition layout whose consequences it can explain. That is the demonstrable
   part.
2. **A reviewer can run it with no account and no bill.** `docker compose
   --profile core up` and nothing costs money. A portfolio nobody can execute is
   a portfolio nobody executes.
3. **Iceberg + Trino + Airflow ports anywhere.** The decision is not
   anti-cloud; it is anti-lock-in, and the same stack maps onto AWS, GCP or
   Azure with the catalog swapped.
4. **Databricks is still used for the two things it is better at**: reading
   SEG-Y headers from terabyte files without moving them, and proving dbt
   portability.

And then the part I would raise before the interviewer does, because they will:
**point 4 is currently aspirational.** There is no workspace, so
`dbt build --target databricks` has **not** been run. What exists is the target,
the `databricks__` dispatch implementations, and a cross-engine equivalence
check that runs each macro's Databricks rendering on Spark 3.5 under ANSI mode
and compares the answers — 15 of 15 agree. That is worth something and it is not
the same as a green build, and `docs/portability-report.md` says `not executed`
in every row of the Databricks column.

The audit did earn its keep, which is the interesting part: it found **six**
constructs that Trino and DuckDB happen to agree on and Databricks does not,
four of them inline in models. The dangerous one is `date_diff('second', a, b)`.
Its obvious Databricks port, `datediff(b, a)`, exists and returns whole **days**
— measured, it returns `0` where the correct answer is `180`. Rate of
penetration becomes zero, and BR-06 classifies every rig state as `STATIC`. No
error anywhere. Two engines agreeing is not portability; it is a coincidence
nobody has tested.

### Which part of this project would you do differently?

Four things. The first two are the real answers.

**1. I would have decided the partition layout against measurements, not
against the spec, and I would have measured it in week two rather than week
ten.**

This is the one that actually cost something. Bronze is partitioned by a
`varchar` `_replay_date`, so 3,044 field days become 3,044 partitions holding a
median of **seven rows** each, mean file size **6.9 KB** against a 128–512 MB
target. Compaction moved 4,136 files to 4,131 — **0.1%** against a 70% target —
and it was *right* to: `optimize` rewrites within a partition, and each of those
partitions already held one file. Meanwhile `fct_log_sample` has no partitioning
at all, and its depth-range query reads every row and discards 93.32% after
reading.

Both follow from decisions taken before there was data to check them against —
which is when partitioning decisions always get taken, and exactly why the first
thing to build should have been the measurement. What I would do differently
concretely: partition bronze by month with a derived typed column, keep the
delete predicate at day grain (Iceberg supports a delete finer than the
partition), and sort `fct_log_sample` by `depth_m` so file statistics prune it
without a partition spec at all. Two hours of work I did not do because nothing
was failing.

**2. I would have built the dialect audit when there were two engines, not
three.**

The third target found four latent bugs that had been sitting in models for
weeks — `strpos`, an unlengthed `cast(… as varchar)`, `unnest`, and the
`date_diff` one that would have silently broken BR-06. All four were written
when Trino and DuckDB both accepted them, and both accepting something is not
portability. The audit is now mechanical — `tests/test_portability.py` scans
every model for eleven constructs, and one of its tests failed the first time it
ran, on a macro with no equivalence case — but I built the enforcement after the
violations, which is the wrong order. A twenty-line regex test in week four
would have prevented all four.

**3. I would put an index on the date-bearing sources before writing the
ingest.**

The 53-second ingest for a day that loaded **38 rows** is nearly all fixed cost:
`witsml_message` spends 7.7 s opening 4,094 XML files to find nothing for that
date, `sim_summary` spends 5.4 s streaming a 238 MB print file for the same
answer. The number is flat in data volume and linear in *number of sources*, so
it breaches the target by adding readers rather than by adding data. Building a
date → file-offset index at extraction time turns each of those scans into a
lookup. I knew the shape of this when writing the readers and deferred it, and
the cost is that the backfill analysis now carries a caveat: only the two
production readers were exercised over 24 months, and a backfill across all
thirteen would not meet the 25-minute target until they are indexed.

**4. I would have checked the SLOs earlier, because they found something no test
could.**

`bronze.las_curve_header` is empty, so `dim_curve` has 0 rows and **every**
`curve_key` in `fct_log_sample` is NULL — 30,421 rows out of 30,421. Every dbt
test passes: `not_null` on `curve_key` was never declared, `unique` on an empty
dimension is vacuously true, and the row-count tests are all about
`fct_log_sample`, which has plenty of rows. It took a completeness objective —
"99% of samples must resolve to a curve" — to make it visible, and I wrote that
objective in week ten. dbt tests ask whether each row is legal; nothing was
asking whether enough of the right rows were there.

**What I would not change.** The refusal to produce numbers that cannot be
produced honestly — the BR-06 agreement rate that is reported as *not
computable* rather than forced, the checkshot disagreement reported at +32.45 m
rather than explained away, the Databricks column that says `not executed`.
Each of those is a place where a number would have looked better and meant
nothing, and the discipline of writing down the miss is the part of this project
I would carry to the next one unchanged.
