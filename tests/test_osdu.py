"""The OSDU mapping, over fixture rows, validated against the reduced schemas.

No warehouse and no platform: the rows below have the shape gold produces, and
the validator is the same one `python -m hugin.osdu.validate_osdu` uses. What
this covers is the mapping's judgement calls - the grain changes, the BR-12
refusal, the escaping of a wellbore name that is not URI-safe - rather than
whether Trino is up.
"""

from __future__ import annotations

import datetime as dt

import pytest

from hugin.osdu import mapping
from hugin.osdu.validate_osdu import validate_records

CONTEXT = mapping.OsduContext(partition="test")


WELLBORE_ROWS = [
    {
        "wellbore_uid": "15/9-F-15 D",
        "well_code": "15/9-F-15",
        "sidetrack_code": "D",
        "version_number": 1,
        "well_role": "PRODUCER",
        "operator_label": "STATOIL PETROLEUM AS",
        "valid_from": dt.date(2008, 6, 1),
        "valid_to": None,
        "is_current": True,
        "source_system_count": 3,
        "identity_variant_count": 5,
    },
    {
        "wellbore_uid": "15/9-F-1 C",
        "well_code": "15/9-F-1",
        "sidetrack_code": "C",
        "version_number": 2,
        "well_role": "INJECTOR",
        "operator_label": None,
        "valid_from": dt.date(2014, 4, 8),
        "valid_to": dt.date(2014, 7, 7),
        "is_current": False,
        "source_system_count": 2,
        "identity_variant_count": 3,
    },
]

LOG_ROWS = [
    {
        "wellbore_uid": "15/9-F-15 D",
        "source_file": "data/landing/log/15_9-F-15_D/WL_RAW_GR.LAS",
        "curve_mnemonic": "GR",
        "curve_key": "curve-gr",
        "index_mnemonic": "DEPT",
        "depth_m": 2500.0,
        "depth_uom": "M",
        "was_sentinel": False,
    },
    {
        "wellbore_uid": "15/9-F-15 D",
        "source_file": "data/landing/log/15_9-F-15_D/WL_RAW_GR.LAS",
        "curve_mnemonic": "GR",
        "curve_key": "curve-gr",
        "index_mnemonic": "DEPT",
        "depth_m": 2600.0,
        "depth_uom": "M",
        "was_sentinel": True,
    },
    {
        "wellbore_uid": "15/9-F-15 D",
        "source_file": "data/landing/log/15_9-F-15_D/WL_RAW_GR.LAS",
        "curve_mnemonic": "RHOB",
        "curve_key": "curve-rhob",
        "index_mnemonic": "DEPT",
        "depth_m": 2550.0,
        "depth_uom": "M",
        "was_sentinel": False,
    },
    {
        "wellbore_uid": "15/9-F-1 C",
        "source_file": "data/landing/log/15_9-F-1_C/WL_RAW_CAL.LAS",
        "curve_mnemonic": "CALI",
        "curve_key": "curve-cali",
        "index_mnemonic": "DEPT",
        "depth_m": 1000.0,
        "depth_uom": "M",
        "was_sentinel": False,
    },
]

TRAJECTORY_ROWS = [
    {
        "wellbore_uid": "15/9-F-14",
        "trajectory_uid": "T-680923-1",
        "station_seq": 1,
        "md_m": 3032.17,
        "tvd_m": 2800.0,
        "inclination_deg": 21.8,
        "azimuth_deg": 283.1,
        "dogleg_severity_deg_per_m": 0.01,
        "azi_ref": "grid north",
        "source_crs": "ED50 / UTM zone 31N",
    },
    {
        "wellbore_uid": "15/9-F-14",
        "trajectory_uid": "T-680923-1",
        "station_seq": 2,
        "md_m": 3233.21,
        "tvd_m": 2950.0,
        "inclination_deg": 22.9,
        "azimuth_deg": 283.3,
        "dogleg_severity_deg_per_m": 0.02,
        "azi_ref": "grid north",
        "source_crs": "ED50 / UTM zone 31N",
    },
]


# --------------------------------------------------------------------------
# Schema conformance
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind, records",
    [
        ("wellbore", mapping.map_wellbores(WELLBORE_ROWS, CONTEXT)),
        ("welllog", mapping.map_well_logs(LOG_ROWS, CONTEXT)),
        ("trajectory", mapping.map_trajectories(TRAJECTORY_ROWS, CONTEXT)),
    ],
)
def test_mapped_records_validate(kind: str, records: list[dict]) -> None:
    result = validate_records(kind, records, source="fixtures")
    assert result.ok, result.failures
    assert result.records > 0


def test_a_wrong_kind_is_caught() -> None:
    """The validator has to be able to fail, or a pass means nothing."""
    record = mapping.map_wellbores(WELLBORE_ROWS[:1], CONTEXT)[0]
    record["kind"] = "osdu:wks:master-data--Well:1.0.0"
    result = validate_records("wellbore", [record], source="deliberately wrong")
    assert not result.ok


def test_a_missing_legal_tag_is_caught() -> None:
    record = mapping.map_wellbores(WELLBORE_ROWS[:1], CONTEXT)[0]
    del record["legal"]
    result = validate_records("wellbore", [record], source="deliberately wrong")
    assert not result.ok


# --------------------------------------------------------------------------
# The mapping's judgement calls
# --------------------------------------------------------------------------


def test_wellbore_name_is_escaped_not_rewritten() -> None:
    """'15/9-F-15 D' is not URI-safe. Escaping is reversible; renaming is not."""
    record = mapping.map_wellbores(WELLBORE_ROWS[:1], CONTEXT)[0]
    assert record["id"] == "test:master-data--Wellbore:15%2F9-F-15%20D"
    # The human-readable name keeps the slash and the space.
    assert record["data"]["FacilityName"] == "15/9-F-15 D"


def test_scd2_version_becomes_the_record_version() -> None:
    records = mapping.map_wellbores(WELLBORE_ROWS, CONTEXT)
    assert [r["version"] for r in records] == [1, 2]
    # is_current has no OSDU home: the newest version is current by definition.
    assert "is_current" not in records[0]["data"]


def test_undated_operator_label_carries_no_effective_date() -> None:
    """ADR 003: no source dates the Statoil/StatoilHydro change. Nor do we."""
    record = mapping.map_wellbores(WELLBORE_ROWS[:1], CONTEXT)[0]
    operator = record["data"]["FacilityOperators"][0]
    assert operator["FacilityOperatorName"] == "STATOIL PETROLEUM AS"
    assert "EffectiveDateTime" not in operator
    # The role, which *is* dated, keeps its date.
    assert record["data"]["FacilityStates"][0]["EffectiveDateTime"] == "2008-06-01T00:00:00Z"


def test_a_null_operator_label_emits_no_operator() -> None:
    record = mapping.map_wellbores(WELLBORE_ROWS[1:], CONTEXT)[0]
    assert "FacilityOperators" not in record["data"]


def test_well_log_aggregates_to_one_record_per_file() -> None:
    """Four sample rows, two files, two records - the grain change."""
    records = mapping.map_well_logs(LOG_ROWS, CONTEXT)
    assert len(records) == 2

    gr_log = next(r for r in records if r["data"]["Name"] == "WL_RAW_GR.LAS")
    assert gr_log["data"]["TopMeasuredDepth"] == 2500.0
    assert gr_log["data"]["BottomMeasuredDepth"] == 2600.0
    assert [c["Mnemonic"] for c in gr_log["data"]["Curves"]] == ["GR", "RHOB"]


def test_curve_depth_range_is_per_curve_not_per_file() -> None:
    """RHOB spans 2550-2550 while the file spans 2500-2600."""
    gr_log = next(
        r for r in mapping.map_well_logs(LOG_ROWS, CONTEXT) if r["data"]["Name"] == "WL_RAW_GR.LAS"
    )
    rhob = next(c for c in gr_log["data"]["Curves"] if c["Mnemonic"] == "RHOB")
    assert rhob["TopDepth"] == 2550.0
    assert rhob["BaseDepth"] == 2550.0


def test_br08_sentinel_count_survives_into_the_export() -> None:
    gr_log = next(
        r for r in mapping.map_well_logs(LOG_ROWS, CONTEXT) if r["data"]["Name"] == "WL_RAW_GR.LAS"
    )
    gr = next(c for c in gr_log["data"]["Curves"] if c["Mnemonic"] == "GR")
    assert gr["ExtensionProperties"]["SentinelReadingCount"] == 1


def test_br12_unresolved_identity_is_refused_not_guessed() -> None:
    """No wellbore_uid means no WellboreID. The mapping raises rather than guess."""
    orphan = [dict(LOG_ROWS[0], wellbore_uid=None, source_file="orphan.LAS")]
    with pytest.raises(ValueError, match="BR-12"):
        mapping.map_well_logs(orphan, CONTEXT)

    # A caller may choose to leave them out of an export - but has to say so.
    assert mapping.map_well_logs(orphan, CONTEXT, skip_unresolved=True) == []


def test_trajectory_aggregates_and_keeps_the_declared_crs() -> None:
    records = mapping.map_trajectories(TRAJECTORY_ROWS, CONTEXT)
    assert len(records) == 1
    data = records[0]["data"]
    assert data["TopDepthMeasuredDepth"] == 3032.17
    assert data["BaseDepthMeasuredDepth"] == 3233.21
    # BR-10: the CRS the source declared travels with the record.
    assert data["ExtensionProperties"]["SourceCRS"] == "ED50 / UTM zone 31N"
    # Never defaulted: an azimuth against the wrong north is silently wrong.
    assert data["SurveyReferenceIdentifier"] == "grid north"
    assert data["ExtensionProperties"]["StationCount"] == 2


def test_bulk_data_is_not_smuggled_into_the_record() -> None:
    """Readings and stations belong in a dataset. Datasets is empty and stays so."""
    log = mapping.map_well_logs(LOG_ROWS, CONTEXT)[0]
    trajectory = mapping.map_trajectories(TRAJECTORY_ROWS, CONTEXT)[0]
    assert "Datasets" not in log["data"]  # pruned because empty
    assert "value" not in str(log["data"]["Curves"])
    assert "station_seq" not in str(trajectory["data"])


def test_null_properties_are_omitted_not_nulled() -> None:
    """An absent property says nothing; a null one asserts the value is nothing."""
    record = mapping.map_wellbores(WELLBORE_ROWS[1:], CONTEXT)[0]

    def has_null(value) -> bool:
        if isinstance(value, dict):
            return any(v is None or has_null(v) for v in value.values())
        if isinstance(value, list):
            return any(has_null(v) for v in value)
        return False

    assert not has_null(record)


# --------------------------------------------------------------------------
# The documentation half
# --------------------------------------------------------------------------


def test_the_unmapped_lists_are_populated() -> None:
    """A mapping that records only what fits is a sales document."""
    assert len(mapping.UNMAPPED_GOLD_COLUMNS) >= 5
    assert len(mapping.UNFILLED_OSDU_PROPERTIES) >= 5
    for _column, _what, why in mapping.UNMAPPED_GOLD_COLUMNS:
        assert len(why) > 30, "every unmapped column needs a reason, not a shrug"


def test_every_mapping_entry_has_a_transform() -> None:
    for group in (
        mapping.WELLBORE_COLUMNS,
        mapping.WELL_LOG_COLUMNS,
        mapping.TRAJECTORY_COLUMNS,
    ):
        for entry in group:
            assert entry.transform, f"{entry.osdu_path} has no transform described"
            assert entry.gold_column or entry.note, (
                f"{entry.osdu_path} maps from nothing and explains nothing"
            )


def test_generated_mapping_document_is_current() -> None:
    """docs/osdu-mapping.md is generated. A stale copy is a lie with a date on it."""
    import subprocess
    import sys
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(repo / "scripts" / "osdu_report.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=repo,
    )
    assert result.returncode == 0, result.stdout + result.stderr
