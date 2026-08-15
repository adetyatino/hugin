"""hugin_wellbore_static — the per-wellbore sources, triggered by arrival.

LAS logs, trajectories, GEOM fault records, daily drilling reports, SEG-Y
headers and the Eclipse print file have no daily rhythm. A log is acquired once
and never again; a survey is run when a section is finished. Giving them a
schedule would mean re-reading a hundred unchanged files every day to discover
that nothing had changed.

So this DAG is triggered by files appearing, not by the clock: a sensor watches
the landing tree and the run happens when its contents change. ``schedule=None``
means nothing starts it otherwise - a manual trigger or the sensor, and that is
all.

Why a poke sensor rather than a Dataset. Airflow Datasets would be the modern
answer if the producer were another DAG, but the producer here is
``make extract``, run by a person against a read-only archive. Nothing inside
Airflow emits an event when that happens, so something has to look.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import sys
from pathlib import Path

import pendulum
from airflow.decorators import task
from airflow.exceptions import AirflowSkipException
from airflow.models.dag import DAG
from airflow.operators.bash import BashOperator
from airflow.sensors.python import PythonSensor

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

TRANSFORM_DIR = REPO_ROOT / "transform"
STATE_FILE = REPO_ROOT / "data" / "_inventory" / "static-sources-fingerprint.txt"

#: The landing subdirectories this DAG owns. Production and WITSML messages are
#: the daily DAG's business and are deliberately absent.
WATCHED_SUBDIRS = ("log", "traj", "ddr", "vsp", "sim")

DEFAULT_ARGS = {
    "owner": "hugin",
    "retries": 1,
    "retry_delay": _dt.timedelta(minutes=5),
}


def landing_fingerprint(landing_dir: Path) -> str:
    """A hash of what the watched directories currently contain.

    Name, size and mtime of every file. Content hashing would be honest too and
    would cost minutes over 10,000 files; this catches an added, removed,
    replaced or re-extracted file, which is what "new files arrived" means here.
    """
    digest = hashlib.sha256()
    for subdir in WATCHED_SUBDIRS:
        root = landing_dir / subdir
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            stat = path.stat()
            digest.update(str(path.relative_to(landing_dir)).encode("utf-8"))
            digest.update(f"{stat.st_size}:{int(stat.st_mtime)}".encode())
    return digest.hexdigest()


def new_files_have_arrived() -> bool:
    """True when the landing tree differs from the last successful run.

    The fingerprint is stored outside Airflow's metadata on purpose: it is a
    fact about the data directory, and it must survive the metadata database
    being reset.
    """
    from hugin.common.config import get_settings

    current = landing_fingerprint(get_settings().landing_dir)
    previous = STATE_FILE.read_text(encoding="utf-8").strip() if STATE_FILE.exists() else ""
    if current == previous:
        print("landing tree unchanged; nothing to ingest")
        return False
    print(f"landing tree changed: {previous[:12] or '(none)'} -> {current[:12]}")
    return True


with DAG(
    dag_id="hugin_wellbore_static",
    description="Per-wellbore sources: LAS, trajectory, GEOM, DDR, SEG-Y, Eclipse.",
    default_args=DEFAULT_ARGS,
    # Arrival-triggered. Nothing on a timer.
    schedule=None,
    start_date=pendulum.datetime(2026, 8, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    tags=["hugin", "static", "arrival-triggered"],
) as dag:

    wait_for_files = PythonSensor(
        task_id="wait_for_new_files",
        python_callable=new_files_have_arrived,
        # reschedule, not poke: this sensor may wait days, and holding a worker
        # slot for that is how a small Airflow deadlocks itself.
        mode="reschedule",
        poke_interval=15 * 60,
        timeout=7 * 24 * 60 * 60,
        soft_fail=True,
    )

    @task
    def ingest_static_sources() -> dict:
        """Load every per-wellbore source on its static load date.

        These readers carry no usable acquisition date - LAS DATE headers say
        UNKNOWN, 'Wed Nov 26 21-01-09', or nothing - so they load on one
        declared date rather than being given a schedule they do not have. See
        hugin.ingestion.las.STATIC_LOAD_DATE.
        """
        import uuid

        from hugin.common.config import get_settings
        from hugin.ingestion.bronze import BronzeLoader
        from hugin.ingestion.eclipse import EclipseBalanceReader
        from hugin.ingestion.geom import FaultRecordReader
        from hugin.ingestion.las import (
            STATIC_LOAD_DATE,
            LasCurveHeaderReader,
            LasSampleReader,
        )
        from hugin.ingestion.segy import SegyHeaderReader
        from hugin.ingestion.trajectory import TrajectoryStationReader
        from hugin.ingestion.vsp import VspCheckshotReader

        settings = get_settings()
        loader = BronzeLoader(settings=settings)
        if not loader.client.wait_until_ready(attempts=30, delay=2):
            raise RuntimeError("Trino is not accepting queries")

        batch_id = str(uuid.uuid4())
        common = {"settings": settings, "batch_id": batch_id}
        readers = [
            LasCurveHeaderReader(**common),
            LasSampleReader(max_files=8, **common),
            TrajectoryStationReader(**common),
            FaultRecordReader(**common),
            SegyHeaderReader(**common),
            VspCheckshotReader(**common),
            EclipseBalanceReader(**common),
        ]

        loaded: dict[str, int] = {}
        for reader in readers:
            result = loader.load(reader, STATIC_LOAD_DATE)
            if not result.skipped:
                loaded[result.table] = result.rows
        print(f"loaded {sum(loaded.values()):,} rows across {len(loaded)} tables")
        return {"batch_id": batch_id, "tables": loaded}

    @task
    def ingest_drilling_reports() -> dict:
        """Daily drilling reports, which do have dates, over the field's life.

        DDR is in this DAG rather than the daily one because it arrives as a
        complete historical set rather than a day at a time, but each report
        keeps its own date so the rows still land on the right partitions.
        """
        import uuid

        from hugin.common.config import get_settings
        from hugin.common.replay import FIELD_END, FIELD_START
        from hugin.ingestion.bronze import BronzeLoader
        from hugin.ingestion.ddr import DDRActivityReader

        settings = get_settings()
        loader = BronzeLoader(settings=settings)
        reader = DDRActivityReader(settings=settings, batch_id=str(uuid.uuid4()))
        result = loader.load_range(reader, FIELD_START, FIELD_END)
        print(f"{result.table}: {result.rows:,} rows ({result.note})")
        return {result.table: result.rows}

    @task
    def record_fingerprint() -> str:
        """Remember what was ingested, so the sensor stays quiet until it changes."""
        from hugin.common.config import get_settings

        fingerprint = landing_fingerprint(get_settings().landing_dir)
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(fingerprint, encoding="utf-8")
        return fingerprint

    dbt_run = BashOperator(
        task_id="dbt_run_static_models",
        bash_command=(
            f"cd {TRANSFORM_DIR} && DBT_PROFILES_DIR=. "
            "dbt build --target trino --select "
            "silver_log_curve+ silver_trajectory_station+ silver_ddr_activity+ "
            "silver_vsp_checkshot+ silver_simulation_result+"
        ),
    )

    wait_for_files >> ingest_static_sources() >> ingest_drilling_reports() >> dbt_run >> record_fingerprint()
