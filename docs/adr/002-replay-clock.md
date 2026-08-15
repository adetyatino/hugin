# ADR 002 — A replay clock maps real time onto the field's life

Status: accepted
Date: 2026-08-12
Scope: `src/hugin/common/replay.py`, every DAG, the `_replay_date` column on
every bronze table

## Context

Volve stopped producing in September 2016 and the archive is complete and
frozen. An archive has no arrival pattern, and a pipeline over data that never
arrives has nothing to be incremental about: one bulk load and the orchestration
story is over. Backfill, late-arriving data, watermarks, and idempotent re-runs
would all be things the repo talks about rather than does.

This is the first of the two structural weaknesses named in SPEC.md section 0,
and it is the one that affects every DAG, so it is settled before any DAG is
written.

## Decision

The field's life — 2008-06-01 to 2016-09-30, 100 whole calendar months — is
projected onto real calendar time by a pure function of the interval Airflow
hands the task. Two settings fix the map:

- `REPLAY_EPOCH` — the real UTC instant at which the replay begins. At that
  instant the replay stands at 2008-06-01.
- `REPLAY_SPEED` — field months per real day. Default 1, so the whole field
  life replays in 100 real days.

`ReplayClock.replay_date(data_interval_start)` returns the field date; `
replay_window(start, end)` returns the closed range of field days a run covers,
which at the default speed is one whole field month per daily run. Every DAG
takes its dates from these. Nothing reads `datetime.now()` — this is the whole
point, and it is asserted by a test.

Three details are decisions in their own right:

**It refuses rather than clamps.** An instant before the epoch raises
`ReplayNotStarted`; one past the end of field life raises `ReplayExhausted`.
Clamping to the first or last field date would map two distinct intervals onto
one `_replay_date` value, so two runs would write the same partition and the
"re-run produces identical output" guarantee would fail exactly where it is
hardest to notice.

**The arithmetic is exact rationals, not floats.** Speeds such as `0.1` have no
binary representation, and the day-within-month step is a floor. A float error
of one part in 2^52 landing across a day boundary would move a run's data into
the neighbouring day for some inputs and not others. `fractions.Fraction` makes
the round trip `real_instant_for -> replay_date` exact for all 3,044 field days
at every speed tested.

**The epoch has no default.** A clock that defaults to "today" reintroduces
wall-clock dependence through the back door, and the failure is invisible: the
pipeline works, and produces different output every day it is run. Missing
`REPLAY_EPOCH` is an error at construction.

## Alternatives considered

**Rewrite timestamps at ingest** — shift every source timestamp forward so the
data appears current. Rejected: it corrupts the data. Production on 2008-06-14
happened on 2008-06-14, and SPEC.md section 10 makes not distorting the data a
licence obligation rather than a preference. The replay clock changes *when a
row is processed*, never what the row says.

**Run the pipeline once, over everything** — and describe incrementality in the
README. Rejected: this is the failure mode the whole ADR exists to avoid. The
DAG would have exactly one shape of run, and every claim about backfill and
idempotency would be untested.

**Drive the replay from a state table** — a counter advanced by each successful
run. Rejected: it makes the run's output depend on execution history rather than
on its interval, so a re-run of an old interval produces a different date than
the original run did. A pure function of `data_interval` is what makes re-runs
and out-of-order backfill safe, and Airflow already stores the interval.

**Speed expressed as field days per real day.** Rejected because it makes the
default awkward: "one field month per real day" is not a fixed number of days,
and any constant chosen (30, 30.44) drifts against the calendar, so after 100
real days the replay would sit somewhere near, but not on, the end of field
life. Months-per-day steps whole calendar months and lands exactly.

## Consequences

- Every bronze table carries `_replay_date` next to `_ingested_at`. The two are
  different clocks and both are needed: one says when the field data is from,
  the other when we processed it. Partitioning of daily sources is on
  `_replay_date`.
- The full replay takes 100 real days at the default speed. Development does
  not wait for it — backfill runs the interval directly, which is the same code
  path.
- Once the replay reaches 2016-09-30 the schedule must stop. `is_exhausted()`
  lets a DAG detect this and finish cleanly rather than catch an exception.
- Moving `REPLAY_EPOCH` after data has landed re-dates the whole replay and
  invalidates every `_replay_date` already written. It is a destructive change;
  `make replay-reset` will be the supported way to do it.
- Demonstration cost: the replay clock is the answer to "the data is a static
  archive, so how does this prove orchestration?" — which is a question a
  reviewer will ask, and better answered by code than by a paragraph.

## When this should be revisited

If a live source is ever attached, the replay clock becomes an adapter concern
and the DAGs keep their shape: `replay_date` would simply track real time. That
substitution is the point of routing every DAG through one function.
