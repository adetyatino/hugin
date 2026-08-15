"""Gold to OSDU well-known schemas.

Three mappings, one per kind SPEC.md section 6 names:

    gold.dim_wellbore    -> osdu:wks:master-data--Wellbore:1.0.0
    gold.fct_log_sample  -> osdu:wks:work-product-component--WellLog:1.0.0
    gold.fct_trajectory  -> osdu:wks:work-product-component--WellboreTrajectory:1.0.0

The two work-product-component mappings change grain, and that is the most
important thing on this page. `fct_log_sample` is one row per reading; a
WellLog record is one *logging run*, describing which curves exist over which
depth interval, with the readings themselves living in a bulk dataset the
record points at. Same for the trajectory: OSDU's WellboreTrajectory is the
survey's metadata, not its stations. So both mappings aggregate, and the bulk
side is deliberately left unwritten — see `docs/osdu-mapping.md` and ADR 008.

Nothing here talks to an OSDU instance. The mapping is the deliverable; SPEC.md
section 7 cuts a real deployment, and pretending otherwise would need
credentials that do not exist. What the mapping does is answer the question an
OSDU-adjacent interviewer actually asks: *what in your model is the WellboreID,
and what have you got that OSDU has no place for?*

The unmapped lists at the bottom are not an appendix. A mapping that only
records what fits is a sales document.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

__all__ = [
    "WELLBORE_KIND",
    "WELL_LOG_KIND",
    "TRAJECTORY_KIND",
    "ColumnMapping",
    "WELLBORE_COLUMNS",
    "WELL_LOG_COLUMNS",
    "TRAJECTORY_COLUMNS",
    "UNMAPPED_GOLD_COLUMNS",
    "UNFILLED_OSDU_PROPERTIES",
    "OsduContext",
    "wellbore_record",
    "well_log_record",
    "trajectory_record",
    "map_wellbores",
    "map_well_logs",
    "map_trajectories",
]

WELLBORE_KIND = "osdu:wks:master-data--Wellbore:1.0.0"
WELL_LOG_KIND = "osdu:wks:work-product-component--WellLog:1.0.0"
TRAJECTORY_KIND = "osdu:wks:work-product-component--WellboreTrajectory:1.0.0"

#: OSDU unit-of-measure references. Spelled out rather than inlined because a
#: unit that lives in a string literal in three places will disagree in one of
#: them, and SPEC.md section 9 makes units a first-class concern.
UOM_METRE = "namespace:reference-data--UnitOfMeasure:m:"
UOM_DEGA = "namespace:reference-data--UnitOfMeasure:dega:"


@dataclass(frozen=True)
class ColumnMapping:
    """One gold column, and where it lands in an OSDU record.

    ``transform`` is prose on purpose. The code below is the executable
    version; this is the version that goes in docs/osdu-mapping.md and gets
    read by someone deciding whether to trust it.
    """

    gold_column: str | None
    osdu_path: str
    transform: str
    note: str = ""


# --------------------------------------------------------------------------
# dim_wellbore -> master-data--Wellbore
# --------------------------------------------------------------------------

WELLBORE_COLUMNS: tuple[ColumnMapping, ...] = (
    ColumnMapping(
        "wellbore_uid",
        "data.FacilityName",
        "verbatim",
        "The canonical name BR-12 resolves to, e.g. '15/9-F-15 D'.",
    ),
    ColumnMapping(
        "wellbore_uid",
        "data.FacilityID",
        "verbatim",
        "OSDU separates the human name from the operator's identifier. This "
        "delivery has one string doing both jobs, so both carry it and the "
        "duplication is visible rather than hidden behind an invented ID.",
    ),
    ColumnMapping(
        "wellbore_uid",
        "id",
        "'<partition>:master-data--Wellbore:' + uid with '/' and ' ' percent-escaped",
        "OSDU ids are URI-ish; '15/9-F-15 D' is not, so it is escaped, not rewritten.",
    ),
    ColumnMapping(
        "well_code",
        "data.WellID",
        "'<partition>:master-data--Well:' + escaped well_code",
        "The relationship to master-data--Well. gold.dim_well has the same key.",
    ),
    ColumnMapping(
        "sidetrack_code",
        "data.ExtensionProperties.SidetrackCode",
        "verbatim when present",
        "OSDU carries no sidetrack letter. It is part of the name and of "
        "nothing else, so it goes to ExtensionProperties rather than being "
        "forced into SequenceNumber, which means something else.",
    ),
    ColumnMapping(
        "operator_label",
        "data.FacilityOperators[0].FacilityOperatorName",
        "verbatim when not null",
        "Statoil / StatoilHydro / STATOIL PETROLEUM AS, as the sources spell it.",
    ),
    ColumnMapping(
        None,
        "data.FacilityOperators[0].EffectiveDateTime",
        "omitted",
        "The label has no date in this delivery. dim_wellbore says so and "
        "docs/adr/003 says why. Emitting valid_from here would date an "
        "operator change that no source dates - fabricated history.",
    ),
    ColumnMapping(
        "well_role",
        "data.FacilityStates[0].FacilityStateTypeID",
        "PRODUCER -> ...FacilityStateType:Producing:, INJECTOR -> ...:Injecting:, "
        "UNKNOWN -> omitted",
        "OSDU reference-data value, not the source string.",
    ),
    ColumnMapping(
        "valid_from",
        "data.FacilityStates[0].EffectiveDateTime",
        "date -> RFC3339 at midnight UTC",
        "This one IS dated: the role comes from daily production, which has a "
        "date per row. SCD2 valid_from is the day the role was first asserted.",
    ),
    ColumnMapping(
        "valid_to",
        "data.FacilityStates[0].TerminationDateTime",
        "date -> RFC3339, omitted when the version is current",
        "",
    ),
    ColumnMapping(
        "version_number",
        "version",
        "SCD2 version number -> OSDU record version",
        "Both mean 'which revision of this entity'. The mapping is exact and "
        "is the only place SCD2 survives the crossing: OSDU keeps history in "
        "record versions, so the dimension's versions become them.",
    ),
    ColumnMapping(
        "is_current",
        None,
        "not emitted",
        "OSDU has no is_current. The latest record version is current by "
        "definition, which is what version_number above already carries.",
    ),
    ColumnMapping(
        "identity_variant_count",
        "data.ExtensionProperties.IdentityVariantCount",
        "verbatim",
        "How many strings named this wellbore across the delivery. OSDU has "
        "NameAliases for the strings themselves; the count is ours.",
    ),
    ColumnMapping(
        "source_system_count",
        "data.ExtensionProperties.SourceSystemCount",
        "verbatim",
        "",
    ),
    ColumnMapping(
        None,
        "data.NameAliases",
        "one entry per identity variant, when variants are supplied",
        "This is the natural OSDU home for BR-12's crosswalk. The mapping "
        "accepts them from silver.wellbore_identity; dim_wellbore itself "
        "carries only the count.",
    ),
    ColumnMapping(
        None,
        "data.SpatialLocation",
        "not emitted",
        "BR-10 stores both coordinate pairs on the trajectory, not on the "
        "wellbore, and the surface location is not in gold. Emitting an empty "
        "SpatialLocation would be worse than omitting it.",
    ),
    ColumnMapping(
        None,
        "data.VerticalMeasurements",
        "not emitted",
        "No datum elevation in gold. The trajectory's azi_ref is a direction "
        "reference, not a vertical one.",
    ),
)


# --------------------------------------------------------------------------
# fct_log_sample -> work-product-component--WellLog
# --------------------------------------------------------------------------

WELL_LOG_COLUMNS: tuple[ColumnMapping, ...] = (
    ColumnMapping(
        "source_file",
        "data.Name",
        "basename of the LAS file",
        "fct_log_sample's grain includes source_file because this delivery has "
        "no run identifier and one LAS file is one logging pass. That "
        "substitution is what makes a WellLog record definable at all.",
    ),
    ColumnMapping(
        "source_file",
        "id",
        "'<partition>:work-product-component--WellLog:' + escaped basename",
        "",
    ),
    ColumnMapping(
        "wellbore_uid",
        "data.WellboreID",
        "'<partition>:master-data--Wellbore:' + escaped uid",
        "The relationship that makes the log findable. An unresolved identity "
        "(BR-12) has no wellbore_uid and therefore no WellboreID; those rows "
        "are refused by map_well_logs rather than pointed at a guess.",
    ),
    ColumnMapping(
        "depth_m",
        "data.TopMeasuredDepth",
        "min(depth_m) over the file",
        "",
    ),
    ColumnMapping(
        "depth_m",
        "data.BottomMeasuredDepth",
        "max(depth_m) over the file",
        "",
    ),
    ColumnMapping(
        "curve_mnemonic",
        "data.Curves[].Mnemonic",
        "one Curves entry per distinct mnemonic in the file",
        "The aggregation that changes grain: rows become one record with an "
        "array, not one record per row.",
    ),
    ColumnMapping(
        "curve_key",
        "data.Curves[].CurveID",
        "verbatim",
        "gold.dim_curve's surrogate key, reused as the curve identifier.",
    ),
    ColumnMapping(
        "depth_m",
        "data.Curves[].TopDepth / .BaseDepth",
        "min / max of depth_m for that curve",
        "Per curve, not per file: curves in one LAS file do not all span the "
        "same interval, and collapsing them to the file's range would assert "
        "readings that are not there.",
    ),
    ColumnMapping(
        "depth_uom",
        "data.Curves[].DepthUnit",
        "unit string -> OSDU UnitOfMeasure reference",
        "'M' and 'm' both map to the metre reference. An unrecognised unit is "
        "left as the source wrote it rather than guessed at.",
    ),
    ColumnMapping(
        None,
        "data.Curves[].CurveUnit",
        "from dim_curve.curve_unit when supplied",
        "fct_log_sample does not carry the curve's unit; dim_curve does, "
        "including has_mixed_units for the mnemonics that disagree between "
        "files. Supplying dim_curve fills this in.",
    ),
    ColumnMapping(
        "was_sentinel",
        "data.Curves[].ExtensionProperties.SentinelReadingCount",
        "count of was_sentinel per curve",
        "BR-08's discarded readings, kept countable. OSDU has CurveQuality, "
        "but it takes a reference value from a list this project has no "
        "grounds to pick from, so the count goes to an extension instead of "
        "being dressed up as a quality judgement.",
    ),
    ColumnMapping(
        "value",
        None,
        "not emitted",
        "The readings themselves. In OSDU they belong in a bulk dataset that "
        "data.Datasets points at - a Wellbore DDMS bulk record, not a field "
        "in this JSON. Nothing here writes one, so Datasets is empty and "
        "docs/osdu-mapping.md says so.",
    ),
    ColumnMapping(
        "index_mnemonic",
        "data.ExtensionProperties.IndexMnemonic",
        "verbatim",
        "Usually DEPT. OSDU implies the index rather than naming it.",
    ),
    ColumnMapping(
        None,
        "data.ServiceCompanyID",
        "not emitted",
        "The logging contractor is in some LAS headers and not others, and is "
        "not carried into gold.",
    ),
)


# --------------------------------------------------------------------------
# fct_trajectory -> work-product-component--WellboreTrajectory
# --------------------------------------------------------------------------

TRAJECTORY_COLUMNS: tuple[ColumnMapping, ...] = (
    ColumnMapping(
        "trajectory_uid",
        "data.Name",
        "verbatim",
        "",
    ),
    ColumnMapping(
        "trajectory_uid",
        "id",
        "'<partition>:work-product-component--WellboreTrajectory:' + escaped uid",
        "",
    ),
    ColumnMapping(
        "wellbore_uid",
        "data.WellboreID",
        "'<partition>:master-data--Wellbore:' + escaped uid",
        "",
    ),
    ColumnMapping(
        "md_m",
        "data.TopDepthMeasuredDepth",
        "min(md_m) over the trajectory",
        "",
    ),
    ColumnMapping(
        "md_m",
        "data.BaseDepthMeasuredDepth",
        "max(md_m) over the trajectory",
        "",
    ),
    ColumnMapping(
        "azi_ref",
        "data.SurveyReferenceIdentifier",
        "verbatim",
        "Grid north, true north or magnetic north, as the survey declares. "
        "Never defaulted: an azimuth against the wrong north is wrong by up "
        "to a degree, silently.",
    ),
    ColumnMapping(
        "source_crs",
        "data.ExtensionProperties.SourceCRS",
        "verbatim",
        "BR-10. OSDU puts a CRS inside AbstractSpatialLocation, which belongs "
        "with coordinates; these stations carry offsets from the well "
        "reference point, not projected coordinates, so the CRS the source "
        "declared travels as an extension where it stays visible.",
    ),
    ColumnMapping(
        None,
        "data.AvailableTrajectoryStationProperties",
        "one entry per station property present, with its OSDU unit reference",
        "Declares that this trajectory has MD, TVD, inclination and azimuth - "
        "the metadata OSDU wants in place of the stations themselves.",
    ),
    ColumnMapping(
        None,
        "data.ActiveIndicator",
        "true",
        "fct_trajectory already keeps one station per (wellbore, md) - the "
        "latest survey wins - so every row that survives into gold is from "
        "the active trajectory.",
    ),
    ColumnMapping(
        "station_seq, station_date, tvd_m, inclination_deg, azimuth_deg, "
        "northing_offset_m, easting_offset_m, vertical_section_m, "
        "dogleg_severity_deg_per_m",
        None,
        "not emitted",
        "The stations. Same reason as the log readings: OSDU keeps them in a "
        "bulk dataset referenced by data.Datasets, not in the record.",
    ),
    ColumnMapping(
        None,
        "data.SurveyType",
        "not emitted",
        "Gyro, MWD, magnetic - the source does not say which.",
    ),
    ColumnMapping(
        None,
        "data.VerticalMeasurement",
        "not emitted",
        "No datum elevation in gold, so there is nothing to reference TVD to.",
    ),
)


#: Gold columns with no OSDU home at all, and why. Distinct from a column that
#: maps to an extension property: these have nowhere to go.
UNMAPPED_GOLD_COLUMNS: tuple[tuple[str, str, str], ...] = (
    (
        "dim_wellbore.wellbore_key",
        "surrogate key",
        "An OSDU id is the identifier. Exporting an md5 that means something "
        "only inside this warehouse would create a second identity for the "
        "same wellbore, which is the exact failure BR-12 exists to prevent.",
    ),
    (
        "dim_wellbore.is_current",
        "SCD2 flag",
        "Implied by OSDU record versioning. See version_number above.",
    ),
    (
        "fct_log_sample.value / depth_m",
        "the measurements",
        "Bulk data. Belongs in a dataset record, not in the WPC.",
    ),
    (
        "fct_log_sample.row_hash",
        "dedup key",
        "Internal to the lakehouse; means nothing outside it.",
    ),
    (
        "fct_trajectory.station_*",
        "the survey stations",
        "Bulk data, for the same reason as the log readings: OSDU keeps the "
        "stations in a dataset the record points at, not in the record. What "
        "does survive is their envelope - top and base measured depth, and "
        "which properties the survey carries.",
    ),
    (
        "fct_trajectory.dogleg_severity_deg_per_m",
        "computed by BR-09",
        "Derived per station and therefore bulk. OSDU would recompute it.",
    ),
    (
        "fct_production_daily.*",
        "the whole production fact",
        "Out of scope for these three kinds. Production maps to "
        "work-product-component--ProductionData in newer OSDU releases; "
        "SPEC.md section 6 names three kinds and this maps three.",
    ),
    (
        "fct_drilling_state.*",
        "rig states, BR-06",
        "No OSDU well-known schema covers a derived rig-state classification. "
        "It would be an extension on a Wellbore Activity record, which is not "
        "one of the three kinds mapped.",
    ),
)

#: OSDU properties the mapping leaves empty, and what it would take to fill
#: them. This is the list to read before claiming an OSDU integration.
UNFILLED_OSDU_PROPERTIES: tuple[tuple[str, str], ...] = (
    ("acl.owners / acl.viewers", "Real group identifiers from the entitlements service."),
    (
        "legal.legaltags",
        "A legal tag created in the target partition. The Volve CC BY 4.0 terms "
        "would be its basis.",
    ),
    (
        "data.SpatialLocation",
        "A surface location with a CRS. Not in gold; the trajectory carries "
        "offsets, not coordinates.",
    ),
    ("data.VerticalMeasurements", "A datum elevation. Not in any source read so far."),
    ("data.TrajectoryTypeID", "A reference-data value. The sources do not say gyro or MWD."),
    (
        "data.PrimaryMaterialID",
        "Reference data about the produced fluid. Inferable from well_role, and "
        "deliberately not inferred.",
    ),
    (
        "data.Datasets",
        "Bulk dataset records for the log readings and the survey stations. "
        "Nothing here writes them.",
    ),
    (
        "data.ServiceCompanyID",
        "An Organisation master record for Baker Hughes, Schlumberger and the rest.",
    ),
    (
        "data.FacilityTypeID",
        "A reference-data value for 'wellbore'. Trivially fillable, and left empty "
        "because reference data has to come from the target partition rather than "
        "be invented here.",
    ),
)


# --------------------------------------------------------------------------
# Record construction
# --------------------------------------------------------------------------


def _escape(identifier: str) -> str:
    """Make a Volve name safe inside an OSDU id.

    '15/9-F-15 D' contains a slash and a space, neither of which belongs in
    the identifier segment of an OSDU id. They are percent-escaped rather than
    replaced, because an escape is reversible and a replacement is a second
    name for the same wellbore.
    """
    return identifier.replace("%", "%25").replace("/", "%2F").replace(" ", "%20")


def _iso(value: Any) -> str | None:
    """A date or datetime as RFC3339 UTC, or None."""
    if value is None:
        return None
    text = value.isoformat() if hasattr(value, "isoformat") else str(value)
    if len(text) == 10:  # a plain date
        return f"{text}T00:00:00Z"
    if text.endswith("Z") or "+" in text[10:]:
        return text
    return f"{text}Z"


def _prune(value: Any) -> Any:
    """Drop None, empty dicts and empty lists, recursively.

    OSDU treats an absent property and a null property differently, and the
    difference matters: a null SpatialLocation asserts that the location is
    known to be nothing. Omission asserts nothing at all, which is the true
    statement here.
    """
    if isinstance(value, dict):
        pruned = {k: _prune(v) for k, v in value.items()}
        return {k: v for k, v in pruned.items() if v not in (None, {}, [])}
    if isinstance(value, list):
        items = [_prune(v) for v in value]
        return [v for v in items if v not in (None, {}, [])]
    return value


@dataclass(frozen=True)
class OsduContext:
    """The partition-specific values every record needs and none of which are data.

    Defaults are obviously-fake placeholders, and that is deliberate: a record
    carrying `hugin-placeholder-legal-tag` cannot be mistaken for one that has
    been through a real entitlements service. ADR 008.
    """

    partition: str = "hugin"
    owners: Sequence[str] = ("data.default.owners@hugin.example.com",)
    viewers: Sequence[str] = ("data.default.viewers@hugin.example.com",)
    legal_tags: Sequence[str] = ("hugin-placeholder-legal-tag",)
    countries: Sequence[str] = ("NO",)
    source: str = "Equinor Volve open dataset, via HUGIN"

    @classmethod
    def from_env(cls) -> OsduContext:
        """Read what a real deployment would supply, keeping the placeholders visible."""
        return cls(
            partition=os.environ.get("OSDU_PARTITION", "hugin"),
            owners=tuple(filter(None, os.environ.get("OSDU_OWNERS", "").split(","))) or cls.owners,
            viewers=tuple(filter(None, os.environ.get("OSDU_VIEWERS", "").split(",")))
            or cls.viewers,
            legal_tags=tuple(filter(None, os.environ.get("OSDU_LEGAL_TAGS", "").split(",")))
            or cls.legal_tags,
        )

    def envelope(self, kind: str) -> dict[str, Any]:
        return {
            "kind": kind,
            "acl": {"owners": list(self.owners), "viewers": list(self.viewers)},
            "legal": {
                "legaltags": list(self.legal_tags),
                "otherRelevantDataCountries": list(self.countries),
                "status": "compliant",
            },
        }

    def srn(self, entity_type: str, identifier: str) -> str:
        return f"{self.partition}:{entity_type}:{_escape(identifier)}"


_ROLE_STATES = {
    "PRODUCER": "namespace:reference-data--FacilityStateType:Producing:",
    "INJECTOR": "namespace:reference-data--FacilityStateType:Injecting:",
}

_DEPTH_UNITS = {
    "M": UOM_METRE,
    "METRE": UOM_METRE,
    "METER": UOM_METRE,
}


def wellbore_record(
    row: Mapping[str, Any],
    context: OsduContext | None = None,
    aliases: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """One `dim_wellbore` row -> one master-data--Wellbore record.

    A row per SCD2 version, not per wellbore: OSDU keeps history as record
    versions, so the dimension's versions map onto them one for one.
    """
    ctx = context or OsduContext()
    uid = row["wellbore_uid"]

    state: dict[str, Any] = {}
    role = (row.get("well_role") or "").upper()
    if role in _ROLE_STATES:
        state = {
            "FacilityStateTypeID": _ROLE_STATES[role],
            "EffectiveDateTime": _iso(row.get("valid_from")),
            "TerminationDateTime": _iso(row.get("valid_to")),
        }

    operators: list[dict[str, Any]] = []
    if row.get("operator_label"):
        # No EffectiveDateTime: see WELLBORE_COLUMNS and ADR 003. The label is
        # undated in every source that carries it.
        operators.append({"FacilityOperatorName": row["operator_label"]})

    record = ctx.envelope(WELLBORE_KIND)
    record["id"] = ctx.srn("master-data--Wellbore", uid)
    if row.get("version_number") is not None:
        record["version"] = int(row["version_number"])
    record["data"] = {
        "FacilityName": uid,
        "FacilityID": uid,
        "Source": ctx.source,
        "WellID": ctx.srn("master-data--Well", row["well_code"]) if row.get("well_code") else None,
        "FacilityStates": [state] if state else [],
        "FacilityOperators": operators,
        "NameAliases": [
            {
                "AliasName": alias["source_identifier"],
                "AliasNameTypeID": (
                    "namespace:reference-data--AliasNameType:"
                    f"{alias.get('source_system', 'Unknown')}:"
                ),
            }
            for alias in aliases
        ],
        "ExtensionProperties": {
            "SidetrackCode": row.get("sidetrack_code"),
            "IdentityVariantCount": row.get("identity_variant_count"),
            "SourceSystemCount": row.get("source_system_count"),
            "WellRole": row.get("well_role"),
        },
    }
    return _prune(record)


def well_log_record(
    samples: Sequence[Mapping[str, Any]],
    context: OsduContext | None = None,
    curve_units: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """`fct_log_sample` rows for **one source_file** -> one WellLog record.

    Grain change, aggregating: one record per logging run, with a Curves entry
    per mnemonic. The readings do not travel; see WELL_LOG_COLUMNS.
    """
    if not samples:
        raise ValueError("well_log_record needs at least one sample row")

    ctx = context or OsduContext()
    units = curve_units or {}
    first = samples[0]
    source_file = first["source_file"]
    wellbore_uid = first.get("wellbore_uid")
    if not wellbore_uid:
        # BR-12: an unresolved identity gets no WellboreID. Emitting the record
        # without one would put a log in the platform that is attached to
        # nothing; emitting it with a guessed one is worse.
        raise ValueError(
            f"{source_file} has no resolved wellbore_uid; "
            "an unresolved identity cannot become a WellLog (BR-12)"
        )

    name = source_file.replace("\\", "/").rsplit("/", 1)[-1]

    by_curve: dict[str, dict[str, Any]] = {}
    for sample in samples:
        mnemonic = sample["curve_mnemonic"]
        depth = sample.get("depth_m")
        entry = by_curve.setdefault(
            mnemonic,
            {
                "CurveID": sample.get("curve_key"),
                "Mnemonic": mnemonic,
                "TopDepth": depth,
                "BaseDepth": depth,
                "DepthUnit": _DEPTH_UNITS.get(
                    str(sample.get("depth_uom") or "").upper().strip(),
                    sample.get("depth_uom"),
                ),
                "CurveUnit": units.get(mnemonic),
                "DepthCoding": "REGULAR",
                "ExtensionProperties": {"SentinelReadingCount": 0},
            },
        )
        if depth is not None:
            entry["TopDepth"] = (
                depth if entry["TopDepth"] is None else min(entry["TopDepth"], depth)
            )
            entry["BaseDepth"] = (
                depth if entry["BaseDepth"] is None else max(entry["BaseDepth"], depth)
            )
        if sample.get("was_sentinel"):
            entry["ExtensionProperties"]["SentinelReadingCount"] += 1

    depths = [s["depth_m"] for s in samples if s.get("depth_m") is not None]

    record = ctx.envelope(WELL_LOG_KIND)
    record["id"] = ctx.srn("work-product-component--WellLog", name)
    record["data"] = {
        "Name": name,
        "Source": ctx.source,
        "WellboreID": ctx.srn("master-data--Wellbore", wellbore_uid),
        "TopMeasuredDepth": min(depths) if depths else None,
        "BottomMeasuredDepth": max(depths) if depths else None,
        # Empty, and honestly so: the bulk readings have no dataset record.
        "Datasets": [],
        "Curves": sorted(by_curve.values(), key=lambda curve: curve["Mnemonic"]),
        "ExtensionProperties": {
            "IndexMnemonic": first.get("index_mnemonic"),
            "SampleCount": len(samples),
        },
    }
    return _prune(record)


def trajectory_record(
    stations: Sequence[Mapping[str, Any]],
    context: OsduContext | None = None,
) -> dict[str, Any]:
    """`fct_trajectory` rows for **one trajectory_uid** -> one WellboreTrajectory."""
    if not stations:
        raise ValueError("trajectory_record needs at least one station")

    ctx = context or OsduContext()
    first = stations[0]
    wellbore_uid = first.get("wellbore_uid")
    if not wellbore_uid:
        raise ValueError(
            f"{first.get('trajectory_uid')} has no resolved wellbore_uid; "
            "an unresolved identity cannot become a WellboreTrajectory (BR-12)"
        )

    mds = [s["md_m"] for s in stations if s.get("md_m") is not None]

    available = []
    for column, type_id, unit in (
        ("md_m", "MeasuredDepth", UOM_METRE),
        ("tvd_m", "TrueVerticalDepth", UOM_METRE),
        ("inclination_deg", "Inclination", UOM_DEGA),
        ("azimuth_deg", "Azimuth", UOM_DEGA),
        ("dogleg_severity_deg_per_m", "DoglegSeverity", UOM_DEGA),
    ):
        if any(s.get(column) is not None for s in stations):
            available.append(
                {
                    "TrajectoryStationPropertyTypeID": (
                        f"namespace:reference-data--TrajectoryStationPropertyType:{type_id}:"
                    ),
                    "StationPropertyUnitID": unit,
                    "Name": column,
                }
            )

    record = ctx.envelope(TRAJECTORY_KIND)
    record["id"] = ctx.srn(
        "work-product-component--WellboreTrajectory",
        str(first.get("trajectory_uid") or wellbore_uid),
    )
    record["data"] = {
        "Name": first.get("trajectory_uid"),
        "Source": ctx.source,
        "WellboreID": ctx.srn("master-data--Wellbore", wellbore_uid),
        "TopDepthMeasuredDepth": min(mds) if mds else None,
        "BaseDepthMeasuredDepth": max(mds) if mds else None,
        "SurveyReferenceIdentifier": first.get("azi_ref"),
        "ActiveIndicator": True,
        "Datasets": [],
        "AvailableTrajectoryStationProperties": available,
        "ExtensionProperties": {
            "SourceCRS": first.get("source_crs"),
            "StationCount": len(stations),
        },
    }
    return _prune(record)


# --------------------------------------------------------------------------
# Batch helpers: grain change, made explicit
# --------------------------------------------------------------------------


def map_wellbores(
    rows: Iterable[Mapping[str, Any]],
    context: OsduContext | None = None,
    identities: Iterable[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Every dim_wellbore row becomes a record. One in, one out."""
    by_uid: dict[str, list[Mapping[str, Any]]] = {}
    for identity in identities:
        by_uid.setdefault(identity.get("wellbore_uid"), []).append(identity)
    return [
        wellbore_record(row, context, aliases=by_uid.get(row.get("wellbore_uid"), []))
        for row in rows
    ]


def _group(rows: Iterable[Mapping[str, Any]], key: str) -> dict[Any, list[Mapping[str, Any]]]:
    grouped: dict[Any, list[Mapping[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row.get(key), []).append(row)
    return grouped


def map_well_logs(
    rows: Iterable[Mapping[str, Any]],
    context: OsduContext | None = None,
    curve_units: Mapping[str, str] | None = None,
    skip_unresolved: bool = False,
) -> list[dict[str, Any]]:
    """Sample rows -> one record per source_file.

    `skip_unresolved` exists so a caller can choose to leave BR-12's
    unresolved identities out of an export. It defaults to False because the
    default should be that a mapping refuses rather than quietly drops - the
    same reasoning as `silver.wellbore_identity_unresolved`.
    """
    records = []
    for _source_file, samples in _group(rows, "source_file").items():
        try:
            records.append(well_log_record(samples, context, curve_units))
        except ValueError:
            if not skip_unresolved:
                raise
    return records


def map_trajectories(
    rows: Iterable[Mapping[str, Any]],
    context: OsduContext | None = None,
    skip_unresolved: bool = False,
) -> list[dict[str, Any]]:
    """Station rows -> one record per trajectory_uid."""
    records = []
    for _uid, stations in _group(rows, "trajectory_uid").items():
        try:
            records.append(trajectory_record(stations, context))
        except ValueError:
            if not skip_unresolved:
                raise
    return records
