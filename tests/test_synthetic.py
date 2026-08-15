"""Fixtures: determinism, physical invariants, and readability by real parsers.

Three things are worth testing about a fixture generator, and only one of them
is about the generator:

1. **Determinism.** The same seed must produce byte-identical files, or CI
   results stop being comparable between runs.
2. **Physical invariants.** A generated wellbore must obey the physics a real
   one does — TVD never exceeds MD, water cut stays in [0, 1] — or tests that
   pass against fixtures say nothing about tests against the field.
3. **Readability by the real parsers.** A fixture the real reader cannot parse
   tests the fixture reader. Every generated format is fed to the same class
   that reads the delivery.

The property tests use hypothesis, which is what it is for: the invariants hold
for every seed, not for seed 42.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from hugin.common.config import Settings
from hugin.ingestion.las import (
    STATIC_LOAD_DATE,
    LasCurveHeaderReader,
    LasSampleReader,
    scan_header,
)
from hugin.ingestion.prod import (
    ProductionDailyReader,
    ProductionMonthlyReader,
)
from hugin.ingestion.trajectory import TrajectoryStationReader
from hugin.ingestion.witsml import WitsmlLogDataReader
from hugin.synthetic.__main__ import IDENTITY_VARIANTS, generate
from hugin.synthetic.calibrate import PROFILES_PATH
from hugin.synthetic.generators import FIXTURE_WELLBORES

REPO_ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    not PROFILES_PATH.exists(),
    reason="profiles.json missing; run python -m hugin.synthetic.calibrate",
)


class FixtureSettings(Settings):
    """Settings whose landing_dir is a fixture tree rather than the delivery."""

    fixture_root: Path = Path("data/fixtures")

    @property
    def landing_dir(self) -> Path:  # type: ignore[override]
        return self.fixture_root


@pytest.fixture(scope="module")
def fixture_dir(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("fixtures")
    generate(out, seed=42, scale="ci", dirt_level=0)
    return out


def settings_for(path: Path) -> FixtureSettings:
    return FixtureSettings(
        replay_epoch="2026-08-01T00:00:00Z", repo_root=REPO_ROOT, fixture_root=path
    )


def digests(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# --------------------------------------------------------------------------
# Determinism
# --------------------------------------------------------------------------

def test_the_same_seed_produces_byte_identical_files(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    generate(first, seed=42, scale="ci", dirt_level=0)
    generate(second, seed=42, scale="ci", dirt_level=0)
    assert digests(first) == digests(second)


def test_determinism_survives_a_different_process_hash_seed(tmp_path):
    """Python salts str hashing per process.

    A generator using the builtin hash() produces different output on every run
    and the difference is invisible in a single-process test. This one is not:
    it regenerates in a subprocess with PYTHONHASHSEED set differently.
    """
    inside = tmp_path / "inside"
    generate(inside, seed=42, scale="ci", dirt_level=0)

    outside = tmp_path / "outside"
    subprocess.run(
        [sys.executable, "-m", "hugin.synthetic", "generate",
         "--out", str(outside), "--seed", "42", "--scale", "ci"],
        check=True, capture_output=True,
        # No PYTHONPATH: the subprocess must find `hugin` the way a container
        # does, through the installed package.
        env={**os.environ, "PYTHONHASHSEED": "12345"},
    )
    assert digests(inside) == digests(outside)


def test_a_different_seed_produces_different_data(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    generate(first, seed=42, scale="ci", dirt_level=0)
    generate(second, seed=7, scale="ci", dirt_level=0)
    assert digests(first) != digests(second)


def test_manifest_records_checksums_parameters_and_the_profile(fixture_dir):
    manifest = json.loads((fixture_dir / "MANIFEST.json").read_text(encoding="utf-8"))

    assert manifest["parameters"] == {"seed": 42, "scale": "ci", "dirt_level": 0}
    assert manifest["profiles"]["calibrated_at"]
    assert manifest["profiles"]["rows_behind_calibration"]
    assert manifest["totals"]["files"] == len(manifest["files"])

    for name, entry in manifest["files"].items():
        actual = hashlib.sha256((fixture_dir / name).read_bytes()).hexdigest()
        assert entry["sha256"] == actual, f"{name} checksum does not match the file"


def test_manifest_says_the_data_is_not_volve(fixture_dir):
    """A licence obligation, not a nicety. SPEC.md section 10."""
    manifest = json.loads((fixture_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    warning = manifest["warning"].lower()
    assert "fixture" in warning
    assert "not volve data" in warning or "is not volve" in warning
    assert all("15/9-X" in name or "15_9-X" in name or "/" not in name
               for name in [w for w in FIXTURE_WELLBORES])


# --------------------------------------------------------------------------
# The real parsers must read the fixtures
# --------------------------------------------------------------------------

def test_the_real_production_reader_reads_the_fixture_workbook(fixture_dir):
    reader = ProductionDailyReader(settings=settings_for(fixture_dir))
    batches = list(reader.read(datetime.date(2020, 1, 11)))
    assert batches, "the fixture workbook produced no rows for a day it covers"
    assert sum(b.num_rows for b in batches) == len(FIXTURE_WELLBORES)


def test_the_real_monthly_reader_reads_the_fixture_workbook(fixture_dir):
    reader = ProductionMonthlyReader(settings=settings_for(fixture_dir))
    assert sum(b.num_rows for b in reader.read(datetime.date(2020, 1, 1))) == len(FIXTURE_WELLBORES)


def test_the_real_las_reader_reads_every_generated_sentinel(fixture_dir):
    reader = LasCurveHeaderReader(settings=settings_for(fixture_dir))
    sentinels = {
        batch.column("null_value_declared")[i].as_py()
        for batch in reader.read(STATIC_LOAD_DATE)
        for i in range(batch.num_rows)
    }
    assert "-999.25" in sentinels
    assert "-9999" in sentinels, "the non-standard sentinel must be present (BR-08)"


def test_the_real_trajectory_reader_reads_the_fixture_survey(fixture_dir):
    reader = TrajectoryStationReader(settings=settings_for(fixture_dir))
    assert sum(b.num_rows for b in reader.read(datetime.date(2020, 1, 5))) > 0


def test_the_real_witsml_reader_reads_the_generated_telemetry(fixture_dir):
    """The one format the delivery does not contain, generated so it can be.

    mnemonicList appears in zero real files, so this is the only way the log
    parser gets exercised against data at all.
    """
    reader = WitsmlLogDataReader(settings=settings_for(fixture_dir))
    rows = sum(b.num_rows for b in reader.read(datetime.date(2020, 1, 1)))
    assert rows > 0
    batch = next(iter(reader.read(datetime.date(2020, 1, 1))))
    assert batch.column("mnemonic")[0].as_py()
    assert batch.column("value")[0].as_py()


# --------------------------------------------------------------------------
# Planted business-rule cases
# --------------------------------------------------------------------------

def test_br04_case_is_present_zero_uptime_with_volume(fixture_dir):
    reader = ProductionDailyReader(settings=settings_for(fixture_dir))
    offenders = []
    for day in range(1, 40):
        for batch in reader.read(datetime.date(2020, 1, 1) + datetime.timedelta(days=day - 1)):
            for i in range(batch.num_rows):
                hours = batch.column("on_stream_hrs")[i].as_py()
                oil = batch.column("bore_oil_vol")[i].as_py()
                if float(hours) == 0.0 and float(oil) > 0.0:
                    offenders.append((batch.column("well_bore_code")[i].as_py(), oil))
    assert offenders, "BR-04 case missing: no day with zero uptime and non-zero volume"


def test_br03_case_is_present_injector_reporting_oil(fixture_dir):
    reader = ProductionDailyReader(settings=settings_for(fixture_dir))
    found = []
    for day in range(1, 40):
        for batch in reader.read(datetime.date(2020, 1, 1) + datetime.timedelta(days=day - 1)):
            for i in range(batch.num_rows):
                if batch.column("well_type")[i].as_py() == "WI" and float(
                    batch.column("bore_oil_vol")[i].as_py()
                ) > 0:
                    found.append(batch.column("well_bore_code")[i].as_py())
    assert found, "BR-03 case missing: no injector reporting produced oil"


def test_br02_case_is_present_monthly_disagrees_with_daily(fixture_dir):
    daily = ProductionDailyReader(settings=settings_for(fixture_dir))
    monthly = ProductionMonthlyReader(settings=settings_for(fixture_dir))

    summed: dict[tuple[str, int], float] = {}
    for offset in range(200):
        day = datetime.date(2020, 1, 1) + datetime.timedelta(days=offset)
        for batch in daily.read(day):
            for i in range(batch.num_rows):
                name = batch.column("npd_well_bore_name")[i].as_py()
                summed[(name, day.month)] = summed.get((name, day.month), 0.0) + float(
                    batch.column("bore_oil_vol")[i].as_py()
                )

    breaches = 0
    for month in (1, 2, 3, 4):
        for batch in monthly.read(datetime.date(2020, month, 1)):
            for i in range(batch.num_rows):
                name = batch.column("wellbore_name")[i].as_py()
                reported = float(batch.column("oil")[i].as_py())
                total = summed.get((name, month), 0.0)
                if total > 0 and abs(total - reported) / reported > 0.02:
                    breaches += 1
    assert breaches > 0, "BR-02 case missing: no month breaches the 2% tolerance"


def test_br08_case_is_present_non_standard_sentinel_in_a_header(fixture_dir):
    files = sorted((fixture_dir / "log").rglob("*.LAS"))
    declared = {scan_header(path).null_value for path in files}
    assert "-9999" in declared, "BR-08 case missing: no file declares a non-standard sentinel"


def test_br08_sentinels_actually_appear_in_the_samples(fixture_dir):
    """The generated files must contain readings at the declared sentinel.

    Two spellings count, and the reason is worth stating: lasio substitutes NaN
    for the declared NULL while reading a LAS 2.0 file, so a sentinel written as
    -999.25 arrives in bronze as 'nan'. Both mean "no reading", both are
    converted to a true NULL by hugin_null_if_sentinel, and a test asserting
    only the raw spelling would fail on a pipeline that is working.
    """
    reader = LasSampleReader(settings=settings_for(fixture_dir))
    seen = 0
    for batch in reader.read(STATIC_LOAD_DATE):
        for i in range(batch.num_rows):
            sentinel = batch.column("null_value_declared")[i].as_py()
            value = (batch.column("value")[i].as_py() or "").strip().lower()
            if value == (sentinel or "").strip().lower() or value in ("nan", "-nan"):
                seen += 1
    assert seen > 0, "sentinels are declared but never occur in the data"


def test_br12_case_is_present_one_wellbore_written_several_ways(fixture_dir):
    from hugin.identity.normalize import normalize

    resolved = {normalize(variant).wellbore_name for variant in IDENTITY_VARIANTS}
    assert len(IDENTITY_VARIANTS) >= 4
    assert resolved == {"15/9-X-3 A"}, f"variants did not fold onto one wellbore: {resolved}"


def test_br13_case_is_present_a_perforation_crossing_two_formations(fixture_dir):
    lines = [
        line.split(",")
        for line in (fixture_dir / "geom" / "well_picks.csv").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]
    picks = [
        (row[2], float(row[3]), float(row[4])) for row in lines if row[1] == "PICK"
    ]
    perforations = [(float(row[3]), float(row[4])) for row in lines if row[1] == "PERF"]

    crossing = []
    for top, base in perforations:
        overlapped = [
            name for name, pick_top, pick_base in picks
            if min(base, pick_base) - max(top, pick_top) > 0
        ]
        if len(overlapped) > 1:
            crossing.append((top, base, overlapped))
    assert crossing, "BR-13 case missing: no perforation crosses two formations"

    top, base, formations = crossing[0]
    penetrated = sum(
        min(base, pick_base) - max(top, pick_top)
        for name, pick_top, pick_base in picks
        if name in formations and min(base, pick_base) - max(top, pick_top) > 0
    )
    assert penetrated == pytest.approx(base - top), (
        "penetrated lengths must sum to the interval length"
    )


# --------------------------------------------------------------------------
# Physical invariants, over many seeds
# --------------------------------------------------------------------------

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import HealthCheck, given, settings as hyp_settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402


@given(seed=st.integers(min_value=0, max_value=2**31 - 1))
@hyp_settings(max_examples=8, deadline=None,
              suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_generated_survey_never_puts_tvd_below_md(seed, tmp_path_factory):
    """TVD <= MD always. A survey violating it is not a well.

    This is BR-09's invariant, checked on the fixture so that a trajectory
    generator producing impossible geometry is caught before it is used to test
    the minimum-curvature implementation.
    """
    out = tmp_path_factory.mktemp(f"traj{seed}")
    generate(out, seed=seed, scale="ci", dirt_level=0)
    reader = TrajectoryStationReader(settings=settings_for(out))
    for offset in range(28):
        day = datetime.date(2020, 1, 1) + datetime.timedelta(days=offset)
        for batch in reader.read(day):
            for i in range(batch.num_rows):
                md = float(batch.column("md")[i].as_py())
                tvd = float(batch.column("tvd")[i].as_py())
                assert tvd <= md + 1e-6, f"seed {seed}: tvd {tvd} exceeds md {md}"


@given(seed=st.integers(min_value=0, max_value=2**31 - 1))
@hyp_settings(max_examples=6, deadline=None,
              suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_water_cut_and_uptime_stay_physical(seed, tmp_path_factory):
    """Water cut in [0, 1], on-stream hours in [0, 24], volumes non-negative."""
    out = tmp_path_factory.mktemp(f"prod{seed}")
    generate(out, seed=seed, scale="ci", dirt_level=0)
    reader = ProductionDailyReader(settings=settings_for(out))

    for offset in range(0, 60, 7):
        day = datetime.date(2020, 1, 1) + datetime.timedelta(days=offset)
        for batch in reader.read(day):
            for i in range(batch.num_rows):
                hours = float(batch.column("on_stream_hrs")[i].as_py())
                oil = float(batch.column("bore_oil_vol")[i].as_py())
                water = float(batch.column("bore_wat_vol")[i].as_py())
                assert 0.0 <= hours <= 24.0, f"seed {seed}: on_stream_hrs {hours}"
                assert oil >= 0.0 and water >= 0.0, f"seed {seed}: negative volume"
                if oil + water > 0:
                    assert 0.0 <= water / (oil + water) <= 1.0
