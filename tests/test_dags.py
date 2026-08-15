"""DAG logic, tested without a scheduler.

Airflow does not install on Windows and is not a declared dependency of this
package — it runs in its own container. That is no reason to leave the DAGs
untested: the parts worth testing are plain functions, and the import machinery
Airflow needs can be stubbed.

So this module stubs `airflow.*` in `sys.modules`, imports each DAG file as
source, and exercises the logic. It checks two things a parse error would not:
that BR-01 is honoured (the replay date comes from the interval, never the wall
clock) and that the arrival sensor actually notices arrivals.
"""

from __future__ import annotations

import ast
import datetime
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

DAGS_DIR = REPO_ROOT / "orchestration" / "dags"
DAG_FILES = sorted(DAGS_DIR.glob("hugin_*.py"))


# --------------------------------------------------------------------------
# Stubs: enough Airflow for the module bodies to execute
# --------------------------------------------------------------------------

class _StubDAG:
    """Records what the DAG was configured with, then swallows the body."""

    instances: list[dict] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        _StubDAG.instances.append(kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _StubOperator:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def __rshift__(self, other):
        return other

    def __rrshift__(self, other):
        return self


def _stub_task(fn=None, **_kwargs):
    """Stand in for @task.

    Airflow's @task returns a factory: calling it inside the DAG body builds a
    task, it does not run the function. A stub that ran the body instead would
    execute every task at import — which is how this first failed, with
    pendulum trying to parse a data_interval_start of None.

    The undecorated function stays reachable as `.function`, which is also how
    Airflow exposes it, so tests can call the real logic directly.
    """
    def wrap(func):
        def factory(*_args, **_kwargs):
            return _StubOperator(task_id=func.__name__)

        factory.function = func
        factory.__name__ = func.__name__
        return factory

    return wrap(fn) if fn is not None else wrap


def _install_airflow_stubs(monkeypatch) -> None:
    modules: dict[str, types.ModuleType] = {}

    def module(name: str, **attrs) -> types.ModuleType:
        mod = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(mod, key, value)
            modules[name] = mod
        modules[name] = mod
        return mod

    class AirflowSkipException(Exception):
        pass

    module("airflow")
    module("airflow.decorators", task=_stub_task)
    module("airflow.exceptions", AirflowSkipException=AirflowSkipException)
    module("airflow.models")
    module("airflow.models.dag", DAG=_StubDAG)
    module("airflow.operators")
    module("airflow.operators.bash", BashOperator=_StubOperator)
    module("airflow.sensors")
    module("airflow.sensors.python", PythonSensor=_StubOperator)

    for name, mod in modules.items():
        monkeypatch.setitem(sys.modules, name, mod)


def load_dag_module(path: Path, monkeypatch):
    """Execute a DAG file with Airflow stubbed, returning its namespace."""
    pytest.importorskip("pendulum")
    _install_airflow_stubs(monkeypatch)
    _StubDAG.instances = []
    namespace: dict = {"__file__": str(path), "__name__": f"dagtest_{path.stem}"}
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)
    return namespace


# --------------------------------------------------------------------------
# Every DAG file
# --------------------------------------------------------------------------

def test_dag_files_exist():
    assert {p.name for p in DAG_FILES} == {
        "hugin_daily.py",
        "hugin_wellbore_static.py",
        "hugin_identity_refresh.py",
    }


@pytest.mark.parametrize("path", DAG_FILES, ids=lambda p: p.stem)
def test_dag_file_is_valid_python(path):
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


@pytest.mark.parametrize("path", DAG_FILES, ids=lambda p: p.stem)
def test_dag_declares_id_schedule_and_catchup(path, monkeypatch):
    load_dag_module(path, monkeypatch)
    assert len(_StubDAG.instances) == 1, "one DAG per file"
    config = _StubDAG.instances[0]
    assert config["dag_id"] == path.stem
    assert "schedule" in config
    assert "start_date" in config
    assert config.get("max_active_runs") == 1, (
        "concurrent runs would race for the same Iceberg partitions"
    )


@pytest.mark.parametrize("path", DAG_FILES, ids=lambda p: p.stem)
def test_no_dag_reads_the_wall_clock_for_its_business_date(path):
    """BR-01. A DAG deriving its date from now() cannot be backfilled.

    The check is textual on purpose: it reads like a lint rule because that is
    what it is, and it fails on the exact construct SPEC.md section 5 forbids.
    """
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        name = getattr(target, "attr", None) or getattr(target, "id", None)
        if name in {"now", "today", "utcnow"}:
            offenders.append(f"line {node.lineno}: {name}()")
    # datetime.now() is legitimate for recording *when a run happened*; it is
    # not legitimate for deciding *which data a run covers*. The identity DAG
    # timestamps its coverage history, so the rule is scoped to files that
    # resolve a replay date.
    if "replay_date" in source:
        assert not offenders, f"{path.name} derives a date from the wall clock: {offenders}"


# --------------------------------------------------------------------------
# hugin_daily: BR-01
# --------------------------------------------------------------------------

def test_br01_daily_dag_maps_the_interval_to_a_field_date(monkeypatch):
    monkeypatch.setenv("REPLAY_EPOCH", "2026-08-01T00:00:00Z")
    monkeypatch.setenv("REPLAY_SPEED", "1")
    from hugin.common.config import get_settings

    get_settings.cache_clear()
    namespace = load_dag_module(DAGS_DIR / "hugin_daily.py", monkeypatch)
    replay_date_for = namespace["replay_date_for"]

    epoch = datetime.datetime(2026, 8, 1, tzinfo=datetime.timezone.utc)
    assert replay_date_for(epoch) == datetime.date(2008, 6, 1)
    assert replay_date_for(epoch + datetime.timedelta(days=1)) == datetime.date(2008, 7, 1)
    get_settings.cache_clear()


def test_br01_the_same_interval_always_gives_the_same_date(monkeypatch):
    """Idempotency rests on this: a re-run computes the date it computed before."""
    monkeypatch.setenv("REPLAY_EPOCH", "2026-08-01T00:00:00Z")
    monkeypatch.setenv("REPLAY_SPEED", "1")
    from hugin.common.config import get_settings

    get_settings.cache_clear()
    namespace = load_dag_module(DAGS_DIR / "hugin_daily.py", monkeypatch)
    replay_date_for = namespace["replay_date_for"]

    interval = datetime.datetime(2026, 8, 18, 6, tzinfo=datetime.timezone.utc)
    assert replay_date_for(interval) == replay_date_for(interval)
    assert replay_date_for(interval) == datetime.date(2009, 11, 8)
    get_settings.cache_clear()


def test_daily_dag_runs_one_at_a_time_and_backfills(monkeypatch):
    load_dag_module(DAGS_DIR / "hugin_daily.py", monkeypatch)
    config = _StubDAG.instances[0]
    assert config["catchup"] is True, "a replay pipeline that cannot backfill is pointless"
    assert config["schedule"] == "@daily"


# --------------------------------------------------------------------------
# hugin_wellbore_static: arrival, not schedule
# --------------------------------------------------------------------------

def test_static_dag_has_no_schedule(monkeypatch):
    """SPEC: triggered by files appearing, not by the clock."""
    load_dag_module(DAGS_DIR / "hugin_wellbore_static.py", monkeypatch)
    assert _StubDAG.instances[0]["schedule"] is None


def test_landing_fingerprint_changes_when_a_file_changes(tmp_path, monkeypatch):
    namespace = load_dag_module(DAGS_DIR / "hugin_wellbore_static.py", monkeypatch)
    fingerprint = namespace["landing_fingerprint"]

    landing = tmp_path / "landing"
    (landing / "log").mkdir(parents=True)
    (landing / "log" / "a.las").write_text("~V\n", encoding="utf-8")
    first = fingerprint(landing)

    assert fingerprint(landing) == first, "unchanged tree, unchanged fingerprint"

    (landing / "log" / "b.las").write_text("~V\n", encoding="utf-8")
    assert fingerprint(landing) != first, "a new file must be noticed"


def test_landing_fingerprint_ignores_directories_the_daily_dag_owns(tmp_path, monkeypatch):
    namespace = load_dag_module(DAGS_DIR / "hugin_wellbore_static.py", monkeypatch)
    fingerprint = namespace["landing_fingerprint"]

    landing = tmp_path / "landing"
    (landing / "log").mkdir(parents=True)
    (landing / "prod").mkdir(parents=True)
    before = fingerprint(landing)

    (landing / "prod" / "new.xlsx").write_text("x", encoding="utf-8")
    assert fingerprint(landing) == before, (
        "production is the daily DAG's business; a change there must not "
        "trigger the static one"
    )


# --------------------------------------------------------------------------
# hugin_identity_refresh: weekly on the replay calendar
# --------------------------------------------------------------------------

def test_identity_dag_runs_on_a_replay_week_cadence(monkeypatch):
    namespace = load_dag_module(DAGS_DIR / "hugin_identity_refresh.py", monkeypatch)
    schedule = _StubDAG.instances[0]["schedule"]
    assert schedule == namespace["replay_week_schedule"]()
    # One field month per real day means a field week is about 5.6 real hours.
    assert schedule == "0 */6 * * *"
