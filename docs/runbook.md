# Runbook

Four procedures, in the order they get needed at three in the morning. Each
starts with how to tell it is the problem you have, because the expensive part
of an incident is usually the diagnosis rather than the fix.

Assumed throughout: the compose stack is up (`docker compose --profile core up
-d`), and the project venv is active (`uv sync --all-groups` installs `hugin`
into it, so `python -m hugin.<x>` resolves from any directory — ADR 010). Where a
command writes, it says so.

**Before anything else**, run the two checks that say what is actually wrong:

    python -m hugin.slo                                   # objectives, per table
    cd transform && DBT_PROFILES_DIR=. dbt test --target trino

`hugin.slo` names the table and the consequence; `dbt test` names the rule. If
both are green and something still looks wrong, the problem is upstream of
gold, and the first section is probably not where to start.

---

## 1. Backfill

### When this applies

- `hugin_daily` failed for a range of dates and the retries are exhausted.
- A reader was fixed and the dates it already loaded are now wrong.
- `gold.fct_production_daily.freshness` breached with a lag of many days.

### The one thing to know first

**Loading a range is not the same speed as looping the daily path.**
`BronzeLoader.load_range` makes one pass over the source and one registration
for the whole range; the daily path pays a fixed cost per date whether or not
that date has data. Measured in `docs/performance.md`: 24 replay months as a
range takes **26.2 s**; the same span one date at a time would be roughly
**110 minutes** for the production readers alone. The 25-minute target in
SPEC.md section 13 is met by the range path and missed by the loop.

So: backfill a range as a range.

### Procedure

1. **Establish what is missing**, rather than assuming a start date.

       python -m hugin.ingestion.load_job --counts

   and, per table:

       select _replay_date, count(*) from bronze.prod_daily
       group by 1 order by 1 desc limit 20;

2. **Reload the range.** The load is idempotent by construction: it deletes the
   `_replay_date` partitions in range before registering, so re-running a range
   that partly loaded is safe and is the normal thing to do.

       python -m hugin.ingestion.load_job \
           --date 2008-06-01 --date 2008-06-02          # specific dates
       python -m hugin.ingestion.load_job --demo

   For a long span, drive `BronzeLoader.load_range` rather than passing
   hundreds of `--date` flags.

3. **Rebuild the models.** Bronze holds raw values; silver and gold are derived
   and must be rebuilt for the new rows to appear.

       cd transform && DBT_PROFILES_DIR=. dbt build --target trino

4. **Verify idempotency, not just completion.** Run the same range twice and
   compare. This is the check that catches a reader that appends instead of
   replacing:

       select count(*), count(distinct _row_hash) from bronze.prod_daily;

   The two numbers must be equal, and both must be unchanged between the two
   passes. `docs/performance.md` records this pair measured across two
   consecutive backfills: 14,859 and 14,859, twice.

5. **Re-check the objectives.**

       python -m hugin.slo

### If a backfill through Airflow is wanted instead

`hugin_daily` has `max_active_runs=1` deliberately: twenty-four concurrent runs
would race for the same Iceberg partitions and the loser would write rows the
winner had already deleted. Do not raise it to make a backfill faster. Use the
range path.

### What can still go wrong

- **The replay clock moved.** `REPLAY_EPOCH` re-dates the whole replay. If it
  has been changed, the partitions written before the change belong to
  different dates and a backfill will not line up with them. There is no fix
  except reloading everything; ADR 002 explains why the epoch has no default.
- **Landing data is absent.** Bronze reads `data/landing/`, not the archive.
  If the extract was cleaned, run `make extract` first. The archive itself is
  read-only and is never written to.

---

## 2. The streaming job died

### When this applies

`silver.drilling_telemetry` has stopped growing, or `fct_drilling_state` is
stale, or the Spark container is gone.

### Diagnose first

    docker compose ps spark redpanda
    docker compose logs --tail 200 spark

    # is the topic still receiving?
    docker compose exec redpanda rpk topic describe drilling.telemetry

    # what has landed?
    select count(*), max(ts) from silver.drilling_telemetry;
    select count(*) from silver.drilling_telemetry_late;

Three different failures look the same from the outside:

| Symptom | Likely cause | Section |
|---|---|---|
| Spark container exited, topic has messages | job crashed or was killed | 2a |
| Spark running, no new rows, no errors | producer stopped | 2b |
| Rows arriving in `_late` and not the main table | watermark, not a failure | 2c |

### 2a. Restart against the existing checkpoint

The checkpoint is the whole recovery mechanism. It holds the committed Kafka
offsets, so restarting against it resumes exactly where the job stopped -
neither losing nor double-counting.

    docker compose --profile stream up -d spark
    docker compose exec -d spark /opt/spark/bin/spark-submit \
        --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.0 \
        /opt/hugin/src/hugin/streaming/spark_stream.py \
        --bootstrap redpanda:9092 \
        --checkpoint /opt/hugin/checkpoints/drilling_telemetry

**Do not delete the checkpoint to "start clean".** Deleting it and restarting
with `--starting-offsets earliest` replays the whole topic. BR-07's dedup will
absorb the duplicates - that is measured: 10,500 messages of which 10,000 were
duplicates left 500 rows and 500 distinct keys - but only for events still
inside the watermark. Anything older arrives late, lands in
`drilling_telemetry_late`, and does not reach the main table.

This exact recovery is measured in `docs/performance.md`: the container was
killed with `docker kill` mid-stream, 3,000 further samples were produced while
it was down, and the resubmitted job against the same checkpoint left 3,000
rows, 3,000 distinct keys, and no duplicates.

### 2b. The producer stopped

    python -m hugin.streaming.producer \
        --source data/fixtures/witsml --speed 10 \
        --bootstrap localhost:19092

`--speed 0` runs as fast as it can; `--dry-run` parses and encodes without
producing, which is how to tell a broker problem from a parser problem in one
command.

### 2c. Events are landing in `_late`

Not a failure. The watermark is 10 minutes; an event whose `ts` is older than
the watermark at the time it arrives goes to `drilling_telemetry_late` by
design, and the count is on the dashboard. If the late count is large and
growing, the cause is usually replaying an old topic (2a) or a producer sending
historical timestamps at speed.

### When the checkpoint genuinely has to go

Only when the schema of the target table changed incompatibly. Then:

1. Stop the job.
2. Note `max(ts)` in the target table.
3. Move the checkpoint aside rather than deleting it -
   `docker compose exec spark mv /opt/hugin/checkpoints/drilling_telemetry{,.bak}`.
4. Restart with `--starting-offsets earliest`.
5. Compare row counts and distinct `(wellbore_uid, ts)` against the note. They
   should be equal; if the distinct count is lower, the watermark discarded
   history and the gap is real.

---

## 3. A corrupt or unreadable source file

### The rule this follows

A file that cannot be parsed is **recorded, not skipped**. Every reader
collects `(file, reason)` pairs and reports them; a reader that silently
dropped a file would make the row count the only evidence that anything was
missing, and nobody checks a row count they have no reason to doubt.

### Diagnose

    python -m hugin.ingestion.load_job --date <replay-date>

The load report names the files that failed and why. For LAS specifically, the
failure reasons distinguish three cases that need different responses:

| Reason | What it means | Response |
|---|---|---|
| `no data section` | the header parsed, `~A` is missing or empty | file is metadata-only; expected for some deliveries |
| `lasio: <Error>` | the file is malformed | see below |
| `no curves` | header present, `~C` empty | as above |

### Procedure

1. **Confirm the file is actually corrupt** rather than merely unusual.
   Encoding and line endings are the usual culprits, and neither is corruption:

       file "data/landing/log/<path>.LAS"
       head -c 400 "data/landing/log/<path>.LAS" | xxd | head

   Volve files carry Scandinavian characters, and a mis-detected encoding turns
   `MÆRSK INSPIRER` into mojibake without failing. There is a test for exactly
   this: `assert_silver_scandinavian_characters_survived.sql`.

2. **Check whether the archive copy differs.** `data/landing/` is derived and
   rebuildable; the archive is the source of truth and is read-only.

       make extract          # re-extracts to data/landing/, never writes to the archive

   If the extracted copy is corrupt and the archive copy is not, the extract was
   the problem and this step fixes it.

3. **If the archive copy is genuinely corrupt**, that is a fact about the
   delivery, not a bug to fix. Record it:
   - the file stays in `data/landing/`;
   - the reader keeps reporting it as a parse failure, every run;
   - if it is one of a duplicate pair, `data/_inventory/name-mapping.csv`
     already records which archive name it came from - that file is committed
     precisely because it is the only record of the mapping.

   Do **not** hand-edit a landing file to make it parse. The next `make extract`
   silently reverts it, and until then the pipeline is reading something that
   exists nowhere else.

4. **If a whole reader is failing**, bound it rather than disabling it:

       python -m hugin.ingestion.load_job --date <d> --max-las-files 8

   The load report states the bound, so a bounded load cannot be mistaken for a
   complete one. `gold.fct_log_sample.row_floor` in `docs/slo.md` is set against
   the bounded load for this reason and says so.

### What not to do

Do not add a blanket `try/except: continue` to a reader. The failure list is
the deliverable; a reader that swallows errors converts a loud problem into a
quiet wrong answer, which is the failure mode this whole repository is arranged
against.

---

## 4. Adding a new well identity to the crosswalk

### When this applies

A new delivery arrives with a wellbore name nothing recognises. Symptoms:
`mart.identity_coverage.total` drops below 95%, or
`silver.wellbore_identity_unresolved` gains rows, or a production row appears
against a wellbore key that joins to nothing.

### The rule this follows

BR-12 resolves what it can, records `match_method` and `match_confidence`, and
sends the rest to `silver.wellbore_identity_unresolved` with a reason. **Never
guess.** A guessed identity attributes production to the wrong wellbore, which
is worse than a gap because it looks like an answer.

### Procedure

1. **See what did not resolve, and why.**

       select * from silver.silver_wellbore_identity where wellbore_uid is null;

   and the file that is the record of it:

       data/_inventory/wellbore-identity-unresolved.csv

2. **Find out whether the source carries an official identifier.** This is the
   first question and it settles most cases. The resolution order in
   `hugin.identity.crosswalk` is fixed:

   1. an official identifier recorded next to the name by the system that wrote
      it - NPD number, W/B number, UUID;
   2. the name itself, through normalisation stages a-d;
   3. nothing: unresolved, with a reason.

   An identifier beats a name, and the reason is concrete. Production writes
   `NO 15/9-F-4 AH` next to NPD code 5693, whose registered name is
   `15/9-F-4`. Reading the name alone invents a sidetrack `AH` that no register
   knows. If the new identity has an identifier, adding it to the reader's
   extraction is the fix, and it is a fix in `hugin/ingestion/`, not here.

3. **If there is no identifier, work out which normalisation stage stopped.**
   The stages are separate functions in `hugin.identity.normalize` so that the
   answer is "stage c rewrote the separators, stage d took `B` off as a
   sidetrack", not "the regex matched":

       python -c "
       from hugin.identity.normalize import normalize
       print(normalize('Norway-Statoil-NO 15_\$47\$_9-F-12'))"

   The trace names each stage and what it did. Extend the stage that failed -
   a new prefix in stage b, a new separator form in stage c - rather than
   adding a special case for the string. A rule that generalises fixes the next
   five names; a special case fixes one and hides the pattern.

4. **Rebuild the crosswalk and look at what moved.**

       python -m hugin.identity.crosswalk
       cd transform && DBT_PROFILES_DIR=. dbt build --target trino \
           --select silver_wellbore_identity+ 

   Coverage can go **down** legitimately - a delivery of unfamiliar names is
   supposed to lower it. What must not happen is coverage going up because rows
   disappeared. Compare before and after:

       select source_system, identity_count, resolved_count, unresolved_count, resolved_pct
       from mart.mart_identity_coverage order by source_system;

   `identity_count` must not fall. Every distinct identity string ever seen
   appears exactly once across the resolved and unresolved tables, and
   `assert_br12_every_source_identifier_appears_once.sql` enforces it.

5. **If it genuinely cannot be resolved**, leave it unresolved. That is a
   supported outcome, not a failure to fix: it stays counted in
   `mart_identity_coverage`, the facts that reference it get a surrogate
   `UNRESOLVED` key rather than a NULL one, and nothing is dropped. The
   objective is 95%, not 100%, for exactly this reason -
   `mart.identity_coverage.total` in `docs/slo.md` says so.

6. **Check the second objective too.** `mart.identity_coverage.no_system_below_half`
   exists because the total can look healthy while one source system resolves
   almost nothing - WITSML contributes 2 identities against PROD's 14, so a
   total-only view would not notice WITSML failing completely.

### Adding an alias by hand

There is no manual override table, and that is deliberate: a hand-maintained
alias list is a place where a guess becomes permanent and unattributable. If a
name truly needs a human decision, the decision belongs in
`hugin.identity.normalize` as a rule, with a comment saying which source and
which delivery motivated it, so the next reader can judge whether it still
applies.

---

## Appendix: the commands, in one place

    docker compose --profile core up -d              # MinIO, Postgres, Trino, Airflow, Metabase
    docker compose --profile stream up -d            # Redpanda, Spark

    python -m hugin.slo                              # objectives; exit 1 on a blocking breach
    python -m hugin.ingestion.load_job --counts      # bronze row counts per table
    python -m hugin.ingestion.load_job --date <d>    # load one replay date
    python -m hugin.identity.crosswalk               # rebuild BR-12's crosswalk
    python -m hugin.osdu.validate_osdu               # map gold to OSDU and validate

    cd transform && DBT_PROFILES_DIR=. dbt build --target trino
    cd transform && DBT_PROFILES_DIR=. dbt build --target duckdb

    python scripts/compact.py --all                  # Iceberg optimize
    python scripts/benchmark.py all                  # SPEC section 13 measurements
    python scripts/dialect_check.py                  # cross-engine macro equivalence
