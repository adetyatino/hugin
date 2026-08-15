"""Tests for BR-12, wellbore identity resolution.

Two layers, following tests/test_inventory.py:

* Stage and resolution tests run anywhere. They use the identity strings this
  dataset actually contains, quoted verbatim, so a rule that stops matching the
  data fails here rather than silently mis-mapping a wellbore.
* Dataset tests assert the BR-12 invariants over the real crosswalk in
  data/_inventory/. They skip when it has not been built yet.

Test names carry `br12` where they assert a rule from SPEC.md section 5.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from hugin.identity import crosswalk as cw
from hugin.identity import normalize as nz

REPO_ROOT = Path(__file__).resolve().parents[1]

# --------------------------------------------------------------------------
# Stage a: unescape
# --------------------------------------------------------------------------

def test_stage_a_restores_the_slash_escape():
    assert nz.unescape_slash("Norway-Statoil-15_$47$_9-F-12") == "Norway-Statoil-15_/_9-F-12"
    # It appears inside entry paths too, not only in archive names.
    assert nz.unescape_slash("15_$47$_9-F-9 A (W-986464)") == "15_/_9-F-9 A (W-986464)"


def test_stage_a_leaves_a_name_without_the_escape_alone():
    assert nz.unescape_slash("15/9-F-12") == "15/9-F-12"


# --------------------------------------------------------------------------
# Stage b: prefixes and operator labels
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("raw", "expected", "systems", "operator"),
    [
        ("Norway-Statoil-NO 15/9-F-12", "15/9-F-12", ("Norway", "NO"), "Statoil"),
        ("Norway-StatoilHydro-15/9-F-15B", "15/9-F-15B", ("Norway",), "StatoilHydro"),
        ("Norway-NA-15/9-F-9 A", "15/9-F-9 A", ("Norway", "NA"), None),
        ("NO 15/9-F-11 T2", "15/9-F-11 T2", ("NO",), None),
        ("NO_15/9-F-15_A", "15/9-F-15_A", ("NO",), None),
        ("15/9-F-12", "15/9-F-12", (), None),
    ],
)
def test_stage_b_strips_origin_and_operator(raw, expected, systems, operator):
    text, found_systems, found_operator = nz.strip_prefixes(raw)
    assert text == expected
    assert found_systems == systems
    assert found_operator == operator


def test_stage_b_prefers_the_longer_operator_label():
    """StatoilHydro must be tried before Statoil, or 'Hydro' is left behind."""
    text, _systems, operator = nz.strip_prefixes("StatoilHydro-15/9-F-15")
    assert operator == "StatoilHydro"
    assert text == "15/9-F-15"


def test_stage_b_keeps_the_operator_label_rather_than_discarding_it():
    """dim_wellbore is SCD2 over exactly this label."""
    _text, _systems, operator = nz.strip_prefixes("Norway-Statoil-15/9-F-12")
    assert operator == "Statoil"


# --------------------------------------------------------------------------
# Stage c: separators
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("15_9-F-11", "15/9-F-11"),          # archive folder name
        ("15_/_9-F-12", "15/9-F-12"),        # after stage a
        ("15_9_F-12", "15/9-F-12"),          # LAS ~WELL
        ("15_9_F_14", "15/9-F-14"),          # LAS ~WELL
        ("15/9-F15", "15/9-F-15"),           # LAS ~WELL, missing dash
        ("15/9-F15S", "15/9-F-15 S"),        # LAS ~WELL, no separators at all
        ("15/9-F-15B", "15/9-F-15 B"),       # WITSML nameWell
        ("15/9-F-15_A", "15/9-F-15 A"),      # LAS after prefix strip
        ("15_9-19 SR", "15/9-19 SR"),        # exploration well, no series letter
        ("15_9_19_ST2", "15/9-19 ST2"),      # DDR file name stem
        ("15/9-F-12", "15/9-F-12"),          # already canonical
    ],
)
def test_stage_c_produces_the_canonical_form(raw, expected):
    canonical, failure = nz.canonical_separators(raw)
    assert failure is None
    assert canonical == expected


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        ("Relief well location 3", "no_block_and_quadrant"),
        ("F-15 C Top Resevoir Intersection", "no_block_and_quadrant"),
        ("08SCA0059", "no_block_and_quadrant"),   # a LAS API number
        ("999999999999", "no_block_and_quadrant"),  # a placeholder UWI
        ("", "empty"),
    ],
)
def test_stage_c_refuses_what_is_not_a_well_name(raw, reason):
    canonical, failure = nz.canonical_separators(raw)
    assert canonical is None
    assert failure == reason


# --------------------------------------------------------------------------
# Stage d: sidetrack
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("canonical", "well", "sidetrack"),
    [
        ("15/9-F-12", "15/9-F-12", None),
        ("15/9-F-15 A", "15/9-F-15", "A"),
        ("15/9-F-15 D", "15/9-F-15", "D"),
        ("15/9-F-11 T2", "15/9-F-11", "T2"),
        ("15/9-19 BT2", "15/9-19", "BT2"),
        ("15/9-19 SR", "15/9-19", "SR"),
    ],
)
def test_stage_d_splits_the_sidetrack_into_its_own_field(canonical, well, sidetrack):
    well_code, code, failure = nz.split_sidetrack(canonical)
    assert failure is None
    assert (well_code, code) == (well, sidetrack)


def test_stage_d_reports_a_suffix_it_does_not_recognise():
    """'15/9-F-10 - Main Wellbore' is a descriptor, not a sidetrack code."""
    well_code, code, failure = nz.split_sidetrack("15/9-F-10 MAIN WELLBORE")
    assert (well_code, code) == (None, None)
    assert failure.startswith("unrecognised_suffix")


def test_stage_d_distinguishes_no_sidetrack_from_an_empty_one():
    _well, sidetrack, _failure = nz.split_sidetrack("15/9-F-12")
    assert sidetrack is None, "the original hole has no sidetrack code, not an empty one"


# --------------------------------------------------------------------------
# Stage e: official identifiers
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("value", "kind"),
    [
        ("W-353084", "W_NUMBER"),
        ("B-353084", "B_NUMBER"),
        ("a82580d7-d94f-4e5a-9a04-be8bcae02998", "UUID"),
        ("5599", "NPD_NUMBER"),
    ],
)
def test_stage_e_recognises_each_identifier_system(value, kind):
    ident = nz.classify_identifier(value)
    assert ident is not None and ident.kind == kind


@pytest.mark.parametrize("value", ["", "15/9-F-12", "Main Wellbore", "P-F-14"])
def test_stage_e_returns_none_for_what_is_not_an_identifier(value):
    assert nz.classify_identifier(value) is None


# --------------------------------------------------------------------------
# Composition: which stage decided
# --------------------------------------------------------------------------

def test_the_trace_names_the_stage_that_decided_the_match():
    """A mapping has to be explainable, not just correct."""
    result = nz.normalize("Norway-Statoil-15_$47$_9-F-12")
    stages = [s.name for s in result.trace if s.changed]
    assert stages == [
        "a_unescape_slash", "b_strip_prefixes", "c_canonical_separators",
    ]
    assert result.decided_by == "c_canonical_separators"

    sidetracked = nz.normalize("Norway-StatoilHydro-15_$47$_9-F-15S")
    assert sidetracked.decided_by == "d_split_sidetrack"
    assert sidetracked.wellbore_name == "15/9-F-15 S"


def test_an_already_canonical_name_needs_no_stage():
    assert nz.normalize("15/9-F-12").decided_by == "none (already canonical)"


# --------------------------------------------------------------------------
# Requirement: the three 15/9-F-12 variants
# --------------------------------------------------------------------------

def test_br12_three_variants_of_f12_map_to_one_wellbore_uid():
    """The example named in SPEC.md section 2: one hole, three written forms.

    Folder name, W-number archive, UUID archive.
    """
    variants = [
        "15_9-F-12",
        "Norway-Statoil-15_$47$_9-F-12",
        "Norway-Statoil-NO 15_$47$_9-F-12",
    ]
    uids = {nz.normalize(v).wellbore_name for v in variants}
    assert uids == {"15/9-F-12"}, f"variants split across {uids}"


def test_br12_f12_variants_agree_on_well_code_and_have_no_sidetrack():
    for variant in ("15_9-F-12", "NO 15/9-F-12", "15_9_F-12", "15/9-F-12"):
        result = nz.normalize(variant)
        assert result.well_code == "15/9-F-12"
        assert result.sidetrack_code is None


# --------------------------------------------------------------------------
# Requirement: the F-15 family
# --------------------------------------------------------------------------

def test_br12_f15_family_shares_a_well_code_with_distinct_sidetracks():
    """F-15 and its sidetracks are one well, five wellbores.

    The written forms differ per source: WITSML writes '15/9-F-15A' with no
    space, DDR writes '15/9-F-15 A', the archive writes
    'Norway-StatoilHydro-15_$47$_9-F-15B'. All must land on one well_code.
    """
    forms = {
        None: "15_9-F-15",
        "A": "Norway-StatoilHydro-15_$47$_9-F-15A",
        "B": "Norway-StatoilHydro-15_$47$_9-F-15B",
        "D": "NO 15/9-F-15 D",
        "S": "Norway-StatoilHydro-15_$47$_9-F-15S",
    }
    results = {expected: nz.normalize(raw) for expected, raw in forms.items()}

    assert {r.well_code for r in results.values()} == {"15/9-F-15"}
    assert {expected: r.sidetrack_code for expected, r in results.items()} == {
        None: None, "A": "A", "B": "B", "D": "D", "S": "S",
    }
    # Five distinct wellbores, not one.
    assert len({r.wellbore_name for r in results.values()}) == 5


def test_br12_a_sidetrack_is_never_confused_with_its_parent_well():
    parent = nz.normalize("15/9-F-15")
    child = nz.normalize("15/9-F-15 D")
    assert parent.well_code == child.well_code
    assert parent.wellbore_name != child.wellbore_name


# --------------------------------------------------------------------------
# Property: normalisation is idempotent
# --------------------------------------------------------------------------

def _generated_identity_strings() -> list[str]:
    """Every combination of the written forms this dataset actually uses.

    A generated grammar rather than `hypothesis`, which is declared in
    pyproject.toml but not installed here. The grammar is not arbitrary: each
    part below is quoted from a name that appears in the Volve delivery, so the
    product covers the real input space rather than random strings.
    """
    origins = ["", "Norway-", "NO ", "NO_", "NA-", "Norway-NA-"]
    operators = ["", "Statoil-", "StatoilHydro-", "Statoil "]
    blocks = ["15/9", "15_9", "15_$47$_9", "15-9"]
    series = ["-F-", "-F", "_F_", "-"]
    numbers = ["1", "9", "11", "12", "15", "19"]
    suffixes = ["", " A", "A", " T2", "BT2", " ST2", "_D", " SR"]

    out: list[str] = []
    for origin in origins:
        for operator in operators:
            for block in blocks:
                for sep in series:
                    for number in numbers:
                        for suffix in suffixes:
                            out.append(f"{origin}{operator}{block}{sep}{number}{suffix}")
    return out


def test_property_normalization_is_idempotent():
    """normalize(canonical form) == the same canonical form, for every input.

    This is the property the crosswalk leans on: a name that has already been
    through the stages must survive a second pass unchanged, or resolving an
    identity twice could produce two wellbores.
    """
    cases = _generated_identity_strings()
    assert len(cases) > 3000, "the generated grammar shrank; check the parts"

    checked = 0
    for raw in cases:
        first = nz.normalize(raw)
        if not first.resolved:
            continue
        again = nz.normalize(first.wellbore_name)
        assert again.resolved, f"{raw!r} -> {first.wellbore_name!r} stopped resolving"
        assert again.wellbore_name == first.wellbore_name, (
            f"{raw!r}: {first.wellbore_name!r} -> {again.wellbore_name!r}"
        )
        assert again.well_code == first.well_code
        assert again.sidetrack_code == first.sidetrack_code
        # And a third pass, to catch a rule that alternates rather than settles.
        assert nz.normalize(again.wellbore_name).wellbore_name == first.wellbore_name
        checked += 1

    assert checked > 2000, f"only {checked} of {len(cases)} generated names resolved"


def test_property_failures_are_stable_too():
    """A name that does not resolve must not resolve on a second pass either."""
    for raw in ("Relief well location 1", "PJ1", "P_NW", "FIELD", "999999999999"):
        first = nz.normalize(raw)
        assert not first.resolved
        assert not nz.normalize(first.without_prefixes).resolved


# --------------------------------------------------------------------------
# Resolution: identifier beats name
# --------------------------------------------------------------------------

def _index_from(pairs: list[tuple[str, str, str]]) -> cw.IdentifierIndex:
    index = cw.IdentifierIndex()
    for kind, value, name in pairs:
        index.add(nz.Identifier(kind, value), name, "test")  # type: ignore[arg-type]
    return index


def test_br12_an_official_identifier_overrules_a_parsed_name():
    """The real case: production writes 'NO 15/9-F-4 AH' with NPD code 5693.

    The name parses to a sidetrack 'AH' that no register knows. The NPD number
    in the same row says the wellbore is 15/9-F-4. The identifier wins, and the
    disagreement is recorded rather than smoothed away.
    """
    index = _index_from([("NPD_NUMBER", "5693", "15/9-F-4")])
    obs = cw.Observation(
        source_system="PROD", source_identifier="NO 15/9-F-4 AH",
        identity_kind="WELL_BORE_CODE", context="test",
        identifiers=(("NPD_NUMBER", "5693"),),
    )
    result = cw.resolve([obs], index)[("PROD", "NO 15/9-F-4 AH")]

    assert result.wellbore_uid == "15/9-F-4"
    assert result.sidetrack_code is None
    assert result.match_method == "IDENTIFIER"
    assert result.match_confidence == 1.0
    assert "15/9-F-4 AH" in result.evidence, "the overruled reading must be recorded"


def test_br12_name_and_identifier_that_agree_stay_on_the_name_path():
    index = _index_from([("NPD_NUMBER", "7405", "15/9-F-1 C")])
    obs = cw.Observation(
        source_system="PROD", source_identifier="NO 15/9-F-1 C",
        identity_kind="WELL_BORE_CODE", context="test",
        identifiers=(("NPD_NUMBER", "7405"),),
    )
    result = cw.resolve([obs], index)[("PROD", "NO 15/9-F-1 C")]
    assert result.wellbore_uid == "15/9-F-1 C"
    assert result.match_method == "NORMALIZED"
    assert "corroborated" in result.evidence


def test_br12_a_bare_identifier_resolves_through_the_index():
    """A UUID is not a name. It resolves only because a source paired it with one."""
    uuid = "a82580d7-d94f-4e5a-9a04-be8bcae02998"
    index = _index_from([("UUID", uuid, "15/9-F-12")])
    obs = cw.Observation(
        source_system="WITSML", source_identifier=uuid, identity_kind="XML_UID_WELL",
        context="test", identifiers=(("UUID", uuid),),
    )
    result = cw.resolve([obs], index)[("WITSML", uuid)]
    assert result.wellbore_uid == "15/9-F-12"
    assert result.match_method == "IDENTIFIER"


def test_br12_an_identifier_naming_two_wellbores_is_a_conflict_not_a_choice():
    index = cw.IdentifierIndex()
    index.add(nz.Identifier("NPD_NUMBER", "5599"), "15/9-F-12", "source A")
    index.add(nz.Identifier("NPD_NUMBER", "5599"), "15/9-F-14", "source B")
    assert index.by_value[("NPD_NUMBER", "5599")] == "15/9-F-12", "first wins, silently never"
    assert len(index.conflicts) == 1
    assert index.conflicts[0]["second"] == "15/9-F-14"


def test_br12_a_simulator_name_needs_corroboration_before_it_resolves():
    """'P-F-14' only resolves because a source that named its own block agrees.

    'I-F4G' parses to 15/9-F-4 G under the same assumption, and no register in
    this dataset knows that wellbore — so it stays unresolved.
    """
    index = cw.IdentifierIndex()
    observations = [
        cw.Observation("SIM", "P-F-14", "ECLIPSE_WELSPECS", "test"),
        cw.Observation("SIM", "I-F4G", "ECLIPSE_WELSPECS", "test"),
    ]
    results = cw.resolve(observations, index, corroborated={"15/9-F-14"})

    good = results[("SIM", "P-F-14")]
    assert good.wellbore_uid == "15/9-F-14"
    assert good.match_confidence == pytest.approx(0.70), "an assumption is not full confidence"
    assert "assumed" in good.evidence

    bad = results[("SIM", "I-F4G")]
    assert bad.wellbore_uid is None
    assert "15/9-F-4 G" in bad.failure


def test_br12_unresolvable_names_are_kept_with_a_reason_not_dropped():
    index = cw.IdentifierIndex()
    observations = [
        cw.Observation("TRAJ", "Relief well location 3", "WELL_FOLDER", "test"),
        cw.Observation("SIM", "PJ1", "ECLIPSE_WELSPECS", "test"),
    ]
    results = cw.resolve(observations, index)
    assert len(results) == 2
    for result in results.values():
        assert result.wellbore_uid is None
        assert result.failure, "an unresolved identity must carry its reason"


def test_br12_a_manual_mapping_is_read_ahead_of_every_rule():
    index = cw.IdentifierIndex()
    obs = cw.Observation("SIM", "PJ1", "ECLIPSE_WELSPECS", "test")
    manual = {("SIM", "PJ1"): {
        "source_system": "SIM", "source_identifier": "PJ1",
        "wellbore_uid": "15/9-F-5", "reason": "confirmed against the model readme",
    }}
    result = cw.resolve([obs], index, manual=manual)[("SIM", "PJ1")]
    assert result.wellbore_uid == "15/9-F-5"
    assert result.match_method == "MANUAL"
    assert "readme" in result.evidence


def test_the_main_wellbore_descriptor_resolves_to_the_wells_own_hole():
    index = cw.IdentifierIndex()
    obs = cw.Observation("TRAJ", "15/9-F-10 - Main Wellbore", "XML_NAME_WELLBORE", "test")
    result = cw.resolve([obs], index)[("TRAJ", "15/9-F-10 - Main Wellbore")]
    assert result.wellbore_uid == "15/9-F-10"
    assert result.match_confidence == pytest.approx(0.90)


def test_observations_merge_to_one_row_per_source_and_identifier():
    """The same name in 2,000 files is one identity, not 2,000."""
    merged = cw.merge_observations([
        cw.Observation("WITSML", "NO 15/9-F-15", "XML_NAME_WELL", "a.xml", occurrences=5),
        cw.Observation("WITSML", "NO 15/9-F-15", "XML_NAME_WELL", "b.xml", occurrences=7,
                       identifiers=(("UUID", "dd19bf7b-02a7-4383-9038-ce201cee4d91"),)),
        cw.Observation("DDR", "NO 15/9-F-15", "XML_NAME_WELL", "c.xml", occurrences=1),
    ])
    assert len(merged) == 2, "same name, different source system, stays two identities"
    witsml = next(m for m in merged if m.source_system == "WITSML")
    assert witsml.occurrences == 12
    assert witsml.identifiers == (("UUID", "dd19bf7b-02a7-4383-9038-ce201cee4d91"),)


# --------------------------------------------------------------------------
# Dataset-level BR-12 invariants (skip when the crosswalk is not built)
# --------------------------------------------------------------------------

IDENTITY_CSV = REPO_ROOT / "data" / "_inventory" / "wellbore-identity.csv"
UNRESOLVED_CSV = REPO_ROOT / "data" / "_inventory" / "wellbore-identity-unresolved.csv"


def _load(path: Path) -> list[dict]:
    if not path.exists():
        pytest.skip(f"{path.name} not built yet: run 'make identity'")
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_assert_br12_no_uid_maps_to_two_wells():
    """A wellbore_uid belongs to exactly one well_code, everywhere it appears."""
    wells: dict[str, set[str]] = {}
    for row in _load(IDENTITY_CSV):
        wells.setdefault(row["wellbore_uid"], set()).add(row["well_code"])
    offenders = {uid: codes for uid, codes in wells.items() if len(codes) > 1}
    assert not offenders, f"wellbore_uid mapping to two well_codes: {offenders}"


def test_assert_br12_every_source_identifier_appears_once():
    """Each (source_system, source_identifier) appears exactly once, in exactly
    one of the two tables. Nothing is dropped, nothing is counted twice."""
    resolved = _load(IDENTITY_CSV)
    unresolved = _load(UNRESOLVED_CSV)

    keys = [(r["source_system"], r["source_identifier"]) for r in resolved + unresolved]
    duplicates = {k for k in keys if keys.count(k) > 1}
    assert not duplicates, f"identity appears more than once: {sorted(duplicates)}"

    both = {(r["source_system"], r["source_identifier"]) for r in resolved} & {
        (r["source_system"], r["source_identifier"]) for r in unresolved
    }
    assert not both, f"identity both resolved and unresolved: {sorted(both)}"


def test_dataset_br12_every_resolved_row_has_the_columns_br12_requires():
    for row in _load(IDENTITY_CSV):
        assert row["wellbore_uid"], row
        assert row["well_code"], row
        assert row["match_method"] in {"EXACT", "NORMALIZED", "IDENTIFIER", "MANUAL"}, row
        assert 0.0 < float(row["match_confidence"]) <= 1.0, row
        assert row["evidence"], "a mapping without evidence cannot be reviewed"


def test_dataset_br12_every_unresolved_row_carries_a_reason():
    for row in _load(UNRESOLVED_CSV):
        assert row["reason"], row
        assert not row.get("wellbore_uid"), "an unresolved row must not carry a uid"


def test_dataset_br12_the_wellbore_uid_is_its_own_canonical_form():
    """Round-trip: normalising a uid produces the same uid. Guards manual rows."""
    for row in _load(IDENTITY_CSV):
        again = nz.normalize(row["wellbore_uid"])
        assert again.wellbore_name == row["wellbore_uid"], row
        assert again.well_code == row["well_code"], row
        assert (again.sidetrack_code or "") == row["sidetrack_code"], row


def test_dataset_br12_the_three_f12_variants_resolve_together_in_the_real_data():
    rows = _load(IDENTITY_CSV)
    f12 = {
        r["source_identifier"] for r in rows if r["wellbore_uid"] == "15/9-F-12"
    }
    for variant in ("15_9-F-12", "Norway-Statoil-15_$47$_9-F-12",
                    "Norway-Statoil-NO 15_$47$_9-F-12"):
        assert variant in f12, f"{variant!r} did not land on 15/9-F-12"


def test_dataset_br12_the_f15_family_is_one_well_in_the_real_data():
    rows = _load(IDENTITY_CSV)
    uids = {r["wellbore_uid"] for r in rows if r["well_code"] == "15/9-F-15"}
    assert {"15/9-F-15", "15/9-F-15 A", "15/9-F-15 B", "15/9-F-15 D"} <= uids
