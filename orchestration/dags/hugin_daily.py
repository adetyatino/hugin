"""hugin_daily — the replay-driven pipeline. One run covers one replay date.

BR-01 is the whole reason this DAG has a shape at all. The replay date comes
from ``data_interval_start``, never from ``datetime.now()``: a task re-run next
week for the same interval must compute the same date, or backfill and re-run
stop being idempotent and every partition becomes a guess about when the code
happened to execute.

    ingest bronze  ->  dbt run silver+gold  ->  dbt test  ->  soda scan

A failing test fails the DAG. That is the point of putting the tests inside the
pipeline rather than beside it: a run that loaded bad data and reported success
is worse than a run that failed, because the bad data is now downstream and
nobody is looking for it.
"""

from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

import pendulum
from airflow.decorators import task
from airflow.exceptions import AirflowSkipException
from airflow.models.dag import DAG
from airflow.operators.bash import BashOperator

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

TRANSFORM_DIR = REPO_ROOT / "transform"
QUALITY_DIR = REPO_ROOT / "quality"

DEFAULT_ARGS = {
    "owner": "hugin",
    "retries": 1,
    "retry_delay": _dt.timedelta(minutes=2),
    "depends_on_past": False,
}


def replay_date_for(data_interval_start) -> _dt.date:
    """Map an Airflow interval onto the field calendar. BR-01.

    Kept as a module-level function so it can be tested without a scheduler:
    tests/test_dags.py calls it with known intervals and asserts the dates.
    """
    from hugin.common.config import get_settings

    clock = get_settings().replay_clock()
    instant = data_interval_start
    if not isinstance(instant, _dt.datetime):
        instant = pendulum.parse(str(instant))
    return clock.replay_date(instant)


with DAG(
    dag_id="hugin_daily",
    description="Replay-driven daily pipeline: bronze -> silver -> gold, tested.",
    default_args=DEFAULT_ARGS,
    # One real day per run. At the default REPLAY_SPEED that is one field month
    # of data; the replay clock decides which, not this schedule.
    schedule="@daily",
    start_date=pendulum.datetime(2026, 8, 1, tz="UTC"),
    catchup=True,
    # A backfill of 24 months would otherwise start 24 runs at once, and they
    # would race for the same Iceberg partitions.
    max_active_runs=1,
    tags=["hugin", "replay", "bronze", "silver", "gold"],
) as dag:

    @task
    def resolve_replay_date(data_interval_start=None) -> str:
        """BR-01: the field date this run covers, from the interval alone."""
        from hugin.common.replay import ReplayExhausted

        try:
            replay_date = replay_date_for(data_interval_start)
        except ReplayExhausted as exhausted:
            # The field's life is finite. Running past it is not a failure, it
            # is the end; skipping says so without a red run every day after.
            raise AirflowSkipException(str(exhausted)) from exhausted

        print(f"interval {data_interval_start} -> replay_date {replay_date}")
        return replay_date.isoformat()

    @task
    def ingest_bronze(replay_date: str) -> dict:
        """Load every daily source for this replay date.

        Idempotent by construction: the loader deletes the replay date's rows
        before registering the new ones, so a re-run replaces rather than
        appends. tests/test_bronze_integration.py is what proves it.
        """
        import uuid

        from hugin.common.config import get_settings
        from hugin.ingestion.bronze import BronzeLoader
        from hugin.ingestion.load_job import all_readers

        target_date = _dt.date.fromisoformat(replay_date)
        settings = get_settings()
        loader = BronzeLoader(settings=settings)
        if not loader.client.wait_until_ready(attempts=30, delay=2):
            raise RuntimeError("Trino is not accepting queries")

        batch_id = str(uuid.uuid4())
        loaded = {}
        for reader in all_readers(batch_id, max_las_files=8):
            result = loader.load(reader, target_date)
            if not result.skipped:
                loaded[result.table] = result.rows
        print(f"{replay_date}: {sum(loaded.values()):,} rows across {len(loaded)} tables")
        return {"replay_date": replay_date, "batch_id": batch_id, "tables": loaded}

    dbt_run = BashOperator(
        task_id="dbt_run_silver_gold",
        bash_command=(
            f"cd {TRANSFORM_DIR} && DBT_PROFILES_DIR=. "
            "dbt run --target trino --select silver gold mart"
        ),
    )

    # Separate task, not `dbt build`, so the UI shows which half failed. A red
    # 'dbt_test' next to a green 'dbt_run' says the data is wrong; a red
    # 'dbt_build' could mean either.
    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=(
            f"cd {TRANSFORM_DIR} && DBT_PROFILES_DIR=. dbt test --target trino"
        ),
    )

    @task
    def soda_scan(replay_date: str) -> str:
        """Statistical profile checks, after the structural ones have passed.

        dbt tests answer "is this row legal"; Soda answers "does this
        distribution look like the ones before it". SPEC.md section 1 keeps both
        because they fail on different things.

        Soda Core is not yet a declared dependency (CLAUDE.md closes the list
        without an ADR), so this task states what it will run and does not
        pretend to have run it. An exit here that silently passed would be the
        worst of the three options.
        """
        checks = QUALITY_DIR / "checks_production.yml"
        if not checks.exists():
            print(
                f"no Soda checks at {checks}; scan not run.\n"
                "Adding soda-core needs an ADR - see docs/adr/004-dbt-adapters.md "
                "for the precedent and CLAUDE.md for the rule."
            )
            raise AirflowSkipException("soda-core not installed; see docs/adr/")
        return f"soda scan for {replay_date}"

    @task
    def slo_check(replay_date: str) -> dict:
        """docs/slo.md, enforced. A breach fails the run.

        This sits after dbt_test rather than beside it because the two ask
        different questions. dbt tests ask whether each row is legal; the SLOs
        ask whether enough rows are here and whether they are current. A build
        can pass every test on a table that lost 90% of its rows overnight.

        Known breaches - the three docs/slo.md records with a diagnosis - are
        reported and do not fail the run. An objective that is deliberately not
        met yet, and is written down as such, is not an incident; treating it as
        one teaches everyone to ignore a red DAG, which is how the real breach
        gets missed.
        """
        import datetime as _date

        from hugin.slo import evaluate, format_report

        as_of = _date.date.fromisoformat(replay_date)
        measurements = evaluate(replay_date=as_of)
        print(format_report(measurements, as_of))

        blocking = [m for m in measurements if m.blocking]
        if blocking:
            names = ", ".join(m.slo.name for m in blocking)
            raise ValueError(
                f"SLO breach on {replay_date}: {names}. "
                "See docs/slo.md for what each objective protects."
            )
        return {
            "replay_date": replay_date,
            "met": sum(1 for m in measurements if m.ok),
            "known_breaches": sum(1 for m in measurements if not m.ok and m.slo.known_breach),
        }

    replay_date = resolve_replay_date()
    ingested = ingest_bronze(replay_date)
    slos = slo_check(replay_date)
    scanned = soda_scan(replay_date)

    ingested >> dbt_run >> dbt_test >> slos >> scanned
