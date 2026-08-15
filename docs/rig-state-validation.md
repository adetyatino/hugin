# Rig state validation (BR-06)

SPEC.md section 5 requires the classified rig state to be cross-checked against
the activity codes in `silver.ddr_activity`, the agreement reported as measured,
and — explicitly — **the thresholds not to be adjusted to improve the number**.

## The agreement rate cannot be computed on this delivery

Not "is low". Cannot be computed, and the reason is worth being precise about,
because it is the same reason that runs through this whole project.

**There is no real drilling telemetry.** `mnemonicList` appears in zero of the
10,773 extracted files. The WITSML `log/` directories contain only
`MetaFileInfo.txt` listings naming curves — "12.25 in Section - Time Log",
"Real Time MWD/LWD data - 8.5in. Pilot - MD Log" — that the export never wrote
out. The curves exist in the source system; they were not delivered.

So the only telemetry the classifier can run on is the generated fixture
(`--scale load`), and the fixture's wellbores are `15/9-X-*`, which do not
exist. The daily drilling reports cover `15/9-F-*` and `15/9-19`. The join
between classified states and reported activities returns **zero rows**, because
the two sides describe different wells — one of which is not a well.

A number produced from that join would be meaningless, and a number produced by
mapping fixture wellbores onto real ones to force an overlap would be worse
than meaningless: it would be a fabricated agreement rate between synthetic
telemetry and real drilling reports, presented as a validation. SPEC.md section
10 makes that a licence problem as well as an engineering one.

## What has been validated instead

The classifier itself, against the rule rather than against the field:

| Check | Where | Result |
|---|---|---|
| Each of the six states from its smallest defining case | `tests/test_rig_state.py` | 18 tests pass |
| Evaluation order — CONNECTION before STATIC, DRILLING before CIRCULATING | same | pass |
| The 10-minute CONNECTION window trims by time, not sample count | same | pass |
| Physical invariant: the bit is never below the hole bottom | `Sample.__post_init__`, and rejected at the stream boundary | pass |
| Totality: every physically valid sample yields one of six states | hypothesis, 300 examples | pass |
| Tripping direction always matches the sign of the depth rate | hypothesis, 200 examples | pass |
| Spans cover every sample exactly once | hypothesis, 50 examples | pass |

The thresholds in `src/hugin/streaming/rig_state.py` are SPEC.md's, in one
dictionary, unmodified. Nothing in this repository tunes them, and there is
nothing to tune them against.

## What would make the comparison possible

In order of how much each would actually settle:

1. **A WITSML delivery containing log curves for a Volve well.** Then the
   classifier runs on real telemetry for a wellbore the drilling reports also
   cover, and the agreement rate is a real measurement. This is the only option
   that produces the number SPEC.md asks for.
2. **Any real surface log for any well with daily reports**, even from another
   field. The rate would not be about Volve, and would have to say so, but it
   would test the classifier against a driller's own account of the same hours.
3. **Nothing else.** In particular, generating fixture telemetry *from* the
   drilling reports and then classifying it would produce a high agreement rate
   that measures only that the generator and the classifier agree with each
   other — a circular result that looks like validation.

## What the disagreement would likely be, when it can be measured

Worth writing down in advance, so the analysis is not written to fit whatever
number appears:

- **Reports are coarse.** A daily drilling report records an activity per
  interval, often to the quarter hour, while the classifier works per sample.
  Short connections inside a drilling interval will be classified and not
  reported, and that is the classifier being more granular rather than wrong.
- **`STATIC` covers several reported activities.** Waiting on weather, waiting
  on cement and rig repair all look identical at the surface sensors. BR-06's
  NPT flag captures the duration but not the reason, so the mapping from
  reported code to classified state is many-to-one and the agreement rate is
  bounded above by that.
- **The report's clock is the driller's.** Activity times are entered by hand
  and rounded; telemetry timestamps come from the acquisition system. A
  systematic offset of a few minutes would depress agreement at every state
  boundary without either side being wrong.

That analysis belongs here now rather than later, because writing it after
seeing the number is how thresholds get tuned without anyone deciding to tune
them.
