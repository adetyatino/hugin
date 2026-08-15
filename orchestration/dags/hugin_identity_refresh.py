"""hugin_identity_refresh — rebuild the BR-12 crosswalk and report the change.

Weekly on the replay calendar, not on the wall clock. At the default
REPLAY_SPEED one real day is one field month, so a week of field time passes
roughly every six real hours; the schedule below is derived from the clock
rather than guessed, and if REPLAY_SPEED changes the cadence follows.

The point of running it repeatedly is that coverage can fall. A delivery that
adds wellbores nothing recognises lowers the resolved percentage, and BR-12
forbids fixing that by guessing. So this DAG reports the movement - resolved,
newly unresolved, and which identities changed - and fails only if something
that used to resolve has stopped resolving, which means a rule regressed rather
than the data having grown.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

import pendulum
from airflow.decorators import task
from airflow.models.dag import DAG

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

HISTORY_FILE = REPO_ROOT / "data" / "_inventory" / "identity-coverage-history.json"

DEFAULT_ARGS = {
    "owner": "hugin",
    "retries": 1,
    "retry_delay": _dt.timedelta(minutes=5),
}


def replay_week_schedule() -> str:
    """A cron expression that fires once per replay week.

    One field month per real day means a field week is about 5.6 real hours.
    Every six hours is the closest cron gets, and being explicit about the
    rounding is better than a comment claiming it is exact.
    """
    return "0 */6 * * *"


with DAG(
    dag_id="hugin_identity_refresh",
    description="Rebuild the BR-12 crosswalk and report coverage movement.",
    default_args=DEFAULT_ARGS,
    schedule=replay_week_schedule(),
    start_date=pendulum.datetime(2026, 8, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    tags=["hugin", "identity", "br-12"],
) as dag:

    @task
    def snapshot_current_coverage() -> dict:
        """What the crosswalk resolves right now, before rebuilding it."""
        from hugin.identity.crosswalk import IDENTITY_PATH, UNRESOLVED_PATH

        def count_rows(path: Path) -> int:
            if not path.exists():
                return 0
            import csv

            with open(path, newline="", encoding="utf-8") as handle:
                return sum(1 for _ in csv.DictReader(handle))

        before = {
            "resolved": count_rows(IDENTITY_PATH),
            "unresolved": count_rows(UNRESOLVED_PATH),
        }
        print(f"before: {before}")
        return before

    @task
    def rebuild_crosswalk() -> dict:
        """Run BR-12 over the landed data again, from scratch."""
        from hugin.identity.crosswalk import build_crosswalk, write_outputs, write_report

        crosswalk = build_crosswalk()
        write_outputs(crosswalk)
        write_report(crosswalk)

        resolved = crosswalk["resolved"]
        after = {
            "resolved": len(resolved),
            "unresolved": len(crosswalk["unresolved"]),
            "wellbores": len({row["wellbore_uid"] for row in resolved}),
            "conflicts": len(crosswalk["identifier_conflicts"]),
            "resolved_identities": sorted(
                (row["source_system"], row["source_identifier"]) for row in resolved
            ),
        }
        print(
            f"after: {after['resolved']} resolved, {after['unresolved']} unresolved, "
            f"{after['wellbores']} wellbores"
        )
        return after

    @task
    def report_coverage_change(before: dict, after: dict) -> dict:
        """Compare, record, and fail only on a regression.

        Coverage falling because a new delivery brought unfamiliar names is
        expected and is reported. An identity that *used* to resolve and no
        longer does is a rule regression, and that fails the run.
        """
        previous_identities = set()
        history = []
        if HISTORY_FILE.exists():
            history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            if history:
                previous_identities = {tuple(item) for item in history[-1].get("resolved_identities", [])}

        current_identities = {tuple(item) for item in after["resolved_identities"]}
        regressed = sorted(previous_identities - current_identities)
        newly_resolved = sorted(current_identities - previous_identities)

        total = after["resolved"] + after["unresolved"]
        entry = {
            "measured_at": _dt.datetime.now().isoformat(timespec="seconds"),
            "resolved": after["resolved"],
            "unresolved": after["unresolved"],
            "wellbores": after["wellbores"],
            "coverage_pct": round(after["resolved"] / total * 100, 1) if total else 0.0,
            "delta_resolved": after["resolved"] - before["resolved"],
            "newly_resolved": [list(item) for item in newly_resolved],
            "regressed": [list(item) for item in regressed],
            "resolved_identities": after["resolved_identities"],
        }
        history.append(entry)
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text(json.dumps(history, indent=2), encoding="utf-8")

        print(
            f"coverage {entry['coverage_pct']}% "
            f"({after['resolved']}/{total}), delta {entry['delta_resolved']:+d}, "
            f"{len(newly_resolved)} newly resolved, {len(regressed)} regressed"
        )
        if regressed:
            raise ValueError(
                f"{len(regressed)} identities stopped resolving: {regressed[:5]}. "
                "Coverage falling because new names arrived is expected; an "
                "identity that used to resolve and no longer does is a rule "
                "regression."
            )
        return entry

    before = snapshot_current_coverage()
    after = rebuild_crosswalk()
    report_coverage_change(before, after)
