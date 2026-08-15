# ADR 006 — Calibrated fixtures, for two jobs and no others

Status: accepted
Date: 2026-08-13
Scope: `src/hugin/synthetic/`, `data/fixtures/`, CI

> **On the number.** The brief asked for this as ADR 004. That number was taken
> in the previous session by the dbt adapter decision, and ADRs are never
> renumbered — a decision referenced by number in a commit message and a README
> must keep it. This is 006.

## Context

Two problems, and they are unrelated except that generated data solves both.

**CI cannot use the real delivery.** The Volve archive is 24 zip files and the
extracted tree is 10,773 files, including a 238 MB Eclipse print file and a
1.17 TB seismic volume that is never downloaded. GitHub Actions has neither the
data nor the time. Without something to read, CI can lint and unit-test but
cannot run a single dbt model — which is most of what there is to test.

**There is no telemetry to load-test with.** SPEC.md section 0 anticipated a
thin streaming subset. The delivery is thinner than that: `mnemonicList` appears
in **zero** of the 10,773 extracted files, so there are no WITSML log curves at
all. A throughput demonstration has nothing to demonstrate on.

Against that sits a licence obligation. Equinor's terms forbid presenting the
data in a misleading, distorted or untrue manner (SPEC.md section 10). Generated
data that could be mistaken for measurements is exactly that, and the failure
mode is not hypothetical: a number in a README outlives the paragraph explaining
where it came from.

## Decision

Generate fixtures, **for two jobs only**, from parameters measured in the real
data:

1. **CI fixtures** — small, deterministic, enough for the whole dbt test suite
   to run with no lakehouse and no large file.
2. **Load fixtures** — telemetry only, amplified, for a streaming throughput
   test.

Fixtures never substitute for real data in development. `SOURCE_MODE=real` is
the default and everything in `docs/performance.md` was measured with it.

Three properties make this safe rather than merely useful.

**Calibration is measured or marked.** `calibrate.py` reads the silver tables
and writes `profiles.json`, where every parameter carries `origin:
"calibrated"` with the row count behind it, or `origin: "assumed"` with a stated
reason. The current profile is 12 calibrated and 7 assumed, and the assumptions
are not arbitrary — they are the things this delivery cannot answer:

- Four of the five anomaly classes the brief lists occur **zero** times in the
  real production data. Duplicated rows: 0. Frozen values: 0. Spikes beyond
  5 sigma: 0. Clock skew: structurally impossible, because production carries a
  date and not a timestamp. Only dropout is real — 173 missing calendar days —
  and only its rate is calibrated. Reporting small non-zero rates for the other
  four would be inventing defects and calling them measurements.
- Telemetry channel ranges and rig-state distributions cannot be calibrated at
  all, because there is no telemetry. They are plausible drilling ranges,
  labelled as assumptions, and they exist to give the load test volume.

**Fixtures are identifiable on sight.** Wellbores are named `15/9-X-*`. The
field has an F series and the exploration wells are `15/9-19`; nothing in the
delivery is named X. A fixture row that escaped its directory would still be
recognisable as one.

**Determinism is checked, not hoped for.** The same seed produces byte-identical
files, and `MANIFEST.json` records the sha256 of each. This caught a real bug:
the telemetry generator used Python's builtin `hash()` for a document uid, which
is salted per process, so output differed between runs in a way no
single-process test would show. The determinism test now regenerates in a
subprocess with a different `PYTHONHASHSEED`.

## The fixtures carry the business rules as planted cases

A fixture that is merely well-shaped tests nothing. The CI set contains, by
construction:

| Rule | Planted case |
|---|---|
| BR-02 | months where the reported monthly volume differs from the summed daily rows by more than the tolerance |
| BR-03 | an injector reporting produced oil |
| BR-04 | a day with zero on-stream hours and a non-zero volume |
| BR-08 | one LAS file per sentinel spelling the real data declares, including `-9999` |
| BR-12 | one wellbore written four ways, including `Norway-Statoil-15_$47$_9-X-3 A` |
| BR-13 | a perforation interval crossing a formation boundary, 60 m in one and 40 m in the next |

Each has a test asserting the case is present, so a generator change that
quietly dropped one fails rather than making the rule tests pass vacuously.

## Alternatives considered

**Commit a small slice of the real data to the repository.** Simplest option,
and it would make CI test the genuine article. Rejected on the licence: the
terms permit redistribution, but a slice of production data in a public
repository is a subset presented without its context, and keeping the honesty
rules simple is worth more than the convenience. It also would not solve the
second problem at all — there is no telemetry to slice.

**Random data with no calibration.** Cheaper, and enough to make dbt models run.
Rejected because the tests would then be about plumbing only: a water cut that
does not rise, a decline curve that does not decline, and a sentinel rate of
zero would let a real regression through. Calibration is what makes a fixture
test mean something.

**Record and replay real rows through the pipeline.** Attractive, and the right
answer if the concern were only CI speed. Rejected for the same licence reason
as committing a slice, and because a recording cannot be amplified: a load test
needs more rows than exist.

## Consequences

- CI can run `dbt build` against a fixture tree without a lakehouse, which is
  what makes the 90-second DuckDB target in SPEC.md section 13 reachable.
- `profiles.json` is a derived artefact that must be regenerated when silver
  changes materially. It records `calibrated_at` and the row counts it was
  computed from, so a stale profile is visible rather than silent.
- Every generated format is read back by the *real* parser in
  `tests/test_synthetic.py`. A fixture the production reader cannot parse would
  be testing the fixture reader, which is the failure this guards.
- One fixture has no real counterpart. There is no GEOM delivery at all, so the
  well-picks and perforation file for BR-13 uses this project's own layout. It
  is the only fixture that does not exercise a reader used against real data,
  and it says so in its own header comment.
- The honesty rules become mechanical: the manifest carries the warning, the
  wellbore names are outside the field's numbering, and `SOURCE_MODE` decides
  which source is read. Nothing relies on remembering.

## When this should be revisited

If a real WITSML delivery with log curves ever arrives, the load generator's
assumed channel ranges should be recalibrated against it, and the telemetry
parameters would move from `assumed` to `calibrated` with no code change — that
is what the origin tagging is for.
