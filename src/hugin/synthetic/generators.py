"""Fixture generators, one per format. Same schemas as the real delivery.

Every generator writes the format the real source uses, so the same parser reads
both: production as an ``.xlsx`` workbook with the real column names, logs as
LAS with a declared sentinel in ``~WELL``, telemetry as WITSML 1.4 with a
``mnemonicList``. A fixture in a convenient format would test the fixture reader
rather than the real one.

Determinism is a hard requirement: the same seed must produce byte-identical
files. That rules out anything touching the wall clock, dictionary iteration
order, or a zip timestamp, and every one of those is handled explicitly below.

Nothing here produces Volve data. The wellbore names are deliberately outside
the real field's numbering (``15/9-X-*``), so a fixture row cannot be mistaken
for a measurement even if it escapes its directory.
"""

from __future__ import annotations

import hashlib
import io
import random
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

__all__ = [
    "FIXTURE_WELLBORES",
    "GeneratorContext",
    "write_las",
    "write_manifest_entry",
    "write_production_workbook",
    "write_telemetry",
    "write_trajectory",
    "write_well_picks",
]

#: Fixture wellbores use an X series. The real field has F, and 15/9-19 for the
#: exploration wells; nothing in the delivery is named 15/9-X-*, so a fixture
#: row is identifiable as one on sight.
FIXTURE_WELLBORES = ("15/9-X-1", "15/9-X-2", "15/9-X-3 A", "15/9-X-4")

#: Fixed epoch for zip entries. Zip stores a modification time, and using the
#: real one would make byte-identical output impossible.
ZIP_TIMESTAMP = (2020, 1, 1, 0, 0, 0)

XLSX_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


@dataclass
class GeneratorContext:
    """Everything a generator needs, including its own seeded RNG."""

    out_dir: Path
    seed: int
    scale: str
    dirt_level: int
    profiles: dict

    def rng(self, stream: str) -> random.Random:
        """A separate RNG per stream, derived from the seed.

        One shared RNG would couple the generators: adding a row to production
        would shift every subsequent log value. Deriving a per-stream seed keeps
        each file reproducible on its own.
        """
        derived = hashlib.sha256(f"{self.seed}:{stream}".encode()).digest()
        return random.Random(int.from_bytes(derived[:8], "big"))

    def parameter(self, name: str, default=None):
        entry = self.profiles.get("parameters", {}).get(name)
        return entry["value"] if entry else default


def write_manifest_entry(path: Path) -> dict:
    """Row count is the generator's business; this records size and checksum."""
    data = path.read_bytes()
    return {
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


# --------------------------------------------------------------------------
# PROD — an .xlsx workbook, because that is the only form the real one has
# --------------------------------------------------------------------------

DAILY_COLUMNS = (
    "DATEPRD", "WELL_BORE_CODE", "NPD_WELL_BORE_CODE", "NPD_WELL_BORE_NAME",
    "NPD_FIELD_CODE", "NPD_FIELD_NAME", "NPD_FACILITY_CODE", "NPD_FACILITY_NAME",
    "ON_STREAM_HRS", "AVG_DOWNHOLE_PRESSURE", "AVG_DOWNHOLE_TEMPERATURE",
    "AVG_DP_TUBING", "AVG_ANNULUS_PRESS", "AVG_CHOKE_SIZE_P", "AVG_CHOKE_UOM",
    "AVG_WHP_P", "AVG_WHT_P", "DP_CHOKE_SIZE", "BORE_OIL_VOL", "BORE_GAS_VOL",
    "BORE_WAT_VOL", "BORE_WI_VOL", "FLOW_KIND", "WELL_TYPE",
)

MONTHLY_COLUMNS = (
    "Wellbore name", "NPDCode", "Year", "Month", "On Stream",
    "Oil", "Gas", "Water", "GI", "WI",
)

EXCEL_EPOCH = date(1899, 12, 30)

#: Facility name carrying a Scandinavian ligature, so the fixture exercises the
#: same encoding path the real workbook does.
FIXTURE_FACILITY = "MÆRSK FIXTURE"


def _excel_serial(day: date) -> int:
    return (day - EXCEL_EPOCH).days


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _column_letter(index: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA."""
    letters = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _sheet_xml(rows: list[list[object]], shared: list[str], lookup: dict[str, int]) -> str:
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        f'<worksheet xmlns="{XLSX_NS}"><sheetData>',
    ]
    for row_index, row in enumerate(rows, start=1):
        parts.append(f'<row r="{row_index}">')
        for column_index, value in enumerate(row):
            if value is None:
                continue
            reference = f"{_column_letter(column_index)}{row_index}"
            if isinstance(value, str):
                if value not in lookup:
                    lookup[value] = len(shared)
                    shared.append(value)
                parts.append(f'<c r="{reference}" t="s"><v>{lookup[value]}</v></c>')
            else:
                parts.append(f'<c r="{reference}"><v>{value}</v></c>')
        parts.append("</row>")
    parts.append("</sheetData></worksheet>")
    return "".join(parts)


def write_production_workbook(context: GeneratorContext, path: Path) -> dict:
    """Write a workbook with the real one's two sheets and column names.

    Planted cases, all of which the BR tests must catch:

    * **BR-04** — a day with zero ON_STREAM_HRS and a non-zero volume.
    * **BR-03** — an injector reporting produced oil.
    * **BR-02** — months where the monthly sheet disagrees with the daily rows
      by more than the tolerance.
    """
    rng = context.rng("production")
    start = date(2020, 1, 1)
    days = 120 if context.scale == "ci" else 365

    rates = context.parameter("production_rate_by_wellbore", {}) or {}
    mean_rates = [v.get("mean_sm3", 500.0) for v in rates.values()] or [500.0]
    base_rate = sum(mean_rates) / len(mean_rates)
    water_cut_rise = float(context.parameter("water_cut_rise_per_year", 0.1) or 0.1)
    uptime = context.parameter("on_stream_hours_distribution", {}) or {}
    shut_in_share = float(uptime.get("shut_in", 0.1))

    daily_rows: list[list[object]] = [list(DAILY_COLUMNS)]
    monthly_totals: dict[tuple[str, int, int], dict[str, float]] = {}

    for well_index, wellbore in enumerate(FIXTURE_WELLBORES):
        is_injector = wellbore == FIXTURE_WELLBORES[-1]
        npd_code = 9000 + well_index
        for offset in range(days):
            day = start + timedelta(days=offset)
            year_fraction = offset / 365.0
            water_cut = min(0.95, 0.05 + water_cut_rise * year_fraction)
            decline = max(0.2, 1.0 - 0.35 * year_fraction)

            shut_in = rng.random() < shut_in_share
            on_stream = 0.0 if shut_in else round(rng.uniform(18.0, 24.0), 2)

            if is_injector:
                oil = gas = water = 0.0
                injected = 0.0 if shut_in else round(base_rate * 2 * rng.uniform(0.8, 1.2), 2)
            else:
                liquid = 0.0 if shut_in else base_rate * decline * rng.uniform(0.85, 1.15)
                oil = round(liquid * (1 - water_cut), 2)
                water = round(liquid * water_cut, 2)
                gas = round(oil * rng.uniform(120, 180), 2)
                injected = 0.0

            # --- planted case, BR-04: volume with no uptime -------------------
            if not is_injector and well_index == 0 and offset == 10:
                on_stream = 0.0
                oil, gas, water = 412.5, 61875.0, 88.2

            # --- planted case, BR-03: an injector reporting produced oil ------
            if is_injector and offset == 20:
                oil = 37.5
                gas = 4200.0

            daily_rows.append([
                _excel_serial(day), f"NO {wellbore}", str(npd_code), wellbore,
                "3420717", "VOLVE-FIXTURE", "999999", FIXTURE_FACILITY,
                on_stream, round(rng.uniform(180, 260), 2), round(rng.uniform(60, 95), 2),
                round(rng.uniform(5, 40), 2), round(rng.uniform(5, 30), 2),
                round(rng.uniform(10, 100), 2), "%",
                round(rng.uniform(10, 60), 2), round(rng.uniform(40, 90), 2),
                round(rng.uniform(1, 20), 2), oil, gas, water, injected,
                "injection" if is_injector else "production",
                "WI" if is_injector else "OP",
            ])

            key = (wellbore, day.year, day.month)
            bucket = monthly_totals.setdefault(
                key, {"oil": 0.0, "gas": 0.0, "water": 0.0, "wi": 0.0, "hours": 0.0,
                      "npd": npd_code, "injector": is_injector})
            bucket["oil"] += oil
            bucket["gas"] += gas
            bucket["water"] += water
            bucket["wi"] += injected
            bucket["hours"] += on_stream

    monthly_rows: list[list[object]] = [list(MONTHLY_COLUMNS),
                                        [None, None, None, None, "hrs", "Sm3", "Sm3", "Sm3", "Sm3", "Sm3"]]
    for position, (key, bucket) in enumerate(sorted(monthly_totals.items())):
        wellbore, year, month = key
        oil = bucket["oil"]
        # --- planted case, BR-02: the monthly figure disagrees ----------------
        # Allocation re-states a well's share after the fact, so the reported
        # monthly number differing from the summed daily one is ordinary. Two
        # months are pushed past the +/-2% tolerance so the mart has something
        # to find; the rest carry a small ordinary difference.
        if position % 7 == 3:
            oil = oil * 1.085
        elif position % 5 == 1:
            oil = oil * 0.94
        else:
            oil = oil * 1.001

        monthly_rows.append([
            wellbore, str(bucket["npd"]), year, month, round(bucket["hours"], 2),
            round(oil, 2), round(bucket["gas"], 2), round(bucket["water"], 2),
            "NULL", round(bucket["wi"], 2) if bucket["injector"] else "NULL",
        ])

    shared: list[str] = []
    lookup: dict[str, int] = {}
    daily_xml = _sheet_xml(daily_rows, shared, lookup)
    monthly_xml = _sheet_xml(monthly_rows, shared, lookup)

    shared_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<sst xmlns="{XLSX_NS}" count="{len(shared)}" uniqueCount="{len(shared)}">'
        + "".join(f"<si><t>{_xml_escape(item)}</t></si>" for item in shared)
        + "</sst>"
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<workbook xmlns="{XLSX_NS}" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets>'
        '<sheet name="Daily Production Data" sheetId="1" r:id="rId1"/>'
        '<sheet name="Monthly Production Data" sheetId="2" r:id="rId2"/>'
        "</sheets></workbook>"
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
        "</Relationships>"
    )
    root_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
        "</Types>"
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in (
            ("[Content_Types].xml", content_types_xml),
            ("_rels/.rels", root_rels_xml),
            ("xl/workbook.xml", workbook_xml),
            ("xl/_rels/workbook.xml.rels", rels_xml),
            ("xl/sharedStrings.xml", shared_xml),
            ("xl/worksheets/sheet1.xml", daily_xml),
            ("xl/worksheets/sheet2.xml", monthly_xml),
        ):
            # A fixed timestamp per entry: zip records mtime, and the real one
            # would make byte-identical output impossible.
            info = zipfile.ZipInfo(name, date_time=ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, content.encode("utf-8"))
    path.write_bytes(buffer.getvalue())

    return {
        "daily_rows": len(daily_rows) - 1,
        "monthly_rows": len(monthly_rows) - 2,
        **write_manifest_entry(path),
    }


# --------------------------------------------------------------------------
# LOG — LAS 2.0, with a non-standard sentinel declared in ~WELL
# --------------------------------------------------------------------------

def write_las(context: GeneratorContext, path: Path, sentinel: str, wellbore: str) -> dict:
    """One LAS file whose ~WELL section declares ``sentinel``.

    Planted case, **BR-08**: the sentinel is taken from the calibrated spelling
    distribution, which includes ``-9999`` — a value code comparing against the
    constant -999.25 would carry through as a measurement.
    """
    rng = context.rng(f"las:{path.name}")
    depth_start, depth_step = 1000.0, 0.5
    samples = 400 if context.scale == "ci" else 4000
    share = float(context.parameter("las_sentinel_sample_share", 0.03) or 0.03)

    lines = [
        "~Version Information",
        "VERS.                 2.0 : CWLS LOG ASCII STANDARD - VERSION 2.0",
        "WRAP.                  NO : ONE LINE PER DEPTH STEP",
        "~Well Information Block",
        "#MNEM.UNIT       DATA               DESCRIPTION",
        f"STRT.M       {depth_start:>10.4f} : START DEPTH",
        f"STOP.M       {depth_start + samples * depth_step:>10.4f} : STOP DEPTH",
        f"STEP.M       {depth_step:>10.4f} : STEP",
        f"NULL.        {sentinel:>10} : NULL VALUE",
        "COMP.        FIXTURE OPERATOR : COMPANY",
        f"WELL.        {wellbore} : WELL",
        "FLD .        VOLVE-FIXTURE : FIELD",
        "DATE.        2020-01-01 : LOG DATE",
        "~Curve Information",
        "DEPT.M               : Depth",
        "GR  .API             : Gamma Ray",
        "RHOB.K/M3            : Bulk Density",
        "NPHI.V/V             : Neutron Porosity",
        "~ASCII",
    ]

    rows = 0
    for index in range(samples):
        depth = depth_start + index * depth_step
        if rng.random() < share:
            # A sentinel reading. All three curves go together, which is what a
            # tool losing contact actually produces.
            values = [sentinel, sentinel, sentinel]
        else:
            values = [
                f"{rng.uniform(15, 140):.4f}",
                f"{rng.uniform(1900, 2750):.4f}",
                f"{rng.uniform(0.05, 0.45):.4f}",
            ]
        lines.append(f"{depth:10.4f} {values[0]:>12} {values[1]:>12} {values[2]:>12}")
        rows += 1

    path.parent.mkdir(parents=True, exist_ok=True)
    # Newline fixed to \n: the platform default would make Windows and Linux
    # produce different bytes from the same seed.
    path.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")
    return {"samples": rows, "sentinel": sentinel, **write_manifest_entry(path)}


# --------------------------------------------------------------------------
# WITSML — telemetry with a mnemonicList. The load-scale generator.
# --------------------------------------------------------------------------

def write_telemetry(context: GeneratorContext, path: Path, wellbore: str, rows: int) -> dict:
    """A WITSML 1.4 log document with logCurveInfo and a comma-separated logData.

    This is the format the real delivery does *not* contain: ``mnemonicList``
    appears in none of its 10,773 files, so there is no real telemetry to
    amplify and the channel ranges here are the assumed ones from profiles.json.
    That makes this generator the load-test's only source of volume, and it is
    labelled as fixture everywhere it appears.
    """
    rng = context.rng(f"telemetry:{wellbore}")
    channels = context.parameter("telemetry_channels", {}) or {}
    states = context.parameter("rig_state_distribution", {}) or {"DRILLING": 1.0}
    interval = int(context.parameter("telemetry_sample_interval_seconds", 5) or 5)

    mnemonics = ["TIME"] + sorted(channels)
    units = ["s"] + ["" for _ in sorted(channels)]

    state_names = sorted(states)
    state_weights = [states[name] for name in state_names]

    start = datetime(2020, 1, 1)
    data_lines = []
    bit_depth = 1000.0
    # The hole is only ever as deep as the deepest the bit has been. Drawing it
    # independently produced samples with the bit below the bottom of the hole,
    # which is not a measurement - the schema rejected 90% of the first load
    # fixture on exactly that invariant, which is the check working and the
    # generator being wrong.
    hole_depth = bit_depth
    for index in range(rows):
        stamp = start + timedelta(seconds=index * interval)
        state = rng.choices(state_names, weights=state_weights, k=1)[0]

        if state == "DRILLING":
            bit_depth += rng.uniform(0.0, 0.4)
            hole_depth = max(hole_depth, bit_depth)
        elif state == "TRIPPING_OUT":
            bit_depth = max(0.0, bit_depth - rng.uniform(0.0, 6.0))
        elif state == "TRIPPING_IN":
            bit_depth = min(hole_depth, bit_depth + rng.uniform(0.0, 6.0))

        values = [stamp.strftime("%Y-%m-%dT%H:%M:%S.000Z")]
        for name in sorted(channels):
            low = float(channels[name]["min"])
            high = float(channels[name]["max"])
            if name == "bit_depth_m":
                values.append(f"{bit_depth:.2f}")
            elif name == "hole_depth_m":
                values.append(f"{hole_depth:.2f}")
            elif state in ("CONNECTION", "STATIC") and name in ("rpm", "wob_klbf", "flow_in_lpm"):
                values.append("0.00")
            else:
                values.append(f"{rng.uniform(low, high):.2f}")
        data_lines.append("<data>" + ",".join(values) + "</data>")

    document = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<logs xmlns="http://www.witsml.org/schemas/1series" version="1.4.1.1">'
        # hashlib, not the builtin hash(): str hashing is salted per process
        # (PYTHONHASHSEED), so hash() here produced a different uid on every
        # run and broke the byte-identical guarantee - caught by the
        # determinism check rather than by reading the code.
        f'<log uidWell="W-FIXTURE" uidWellbore="B-FIXTURE" '
        f'uid="L-{int(hashlib.sha256(wellbore.encode()).hexdigest()[:8], 16) % 100000}">'
        f"<nameWell>{_xml_escape(wellbore)}</nameWell>"
        f"<nameWellbore>{_xml_escape(wellbore)}</nameWellbore>"
        "<name>Fixture Time Log</name><indexType>date time</indexType>"
        + "".join(
            f"<logCurveInfo><mnemonic>{m}</mnemonic><unit>{u}</unit></logCurveInfo>"
            for m, u in zip(mnemonics, units, strict=True)
        )
        + "<logData>"
        f"<mnemonicList>{','.join(mnemonics)}</mnemonicList>"
        f"<unitList>{','.join(units)}</unitList>"
        + "".join(data_lines)
        + "</logData></log></logs>"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document, encoding="utf-8", newline="\n")
    return {"samples": rows, "channels": len(mnemonics) - 1, **write_manifest_entry(path)}


# --------------------------------------------------------------------------
# TRAJ — trajectory stations, for the identity variants (BR-12)
# --------------------------------------------------------------------------

def write_trajectory(context: GeneratorContext, path: Path, written_name: str) -> dict:
    """A trajectory document naming its wellbore in a non-canonical spelling.

    Planted case, **BR-12**: ``written_name`` is a variant such as
    ``15_$47$_9-X-3 A`` or ``NO 15/9-X-3 A``, which BR-12's stages a-d must
    normalise onto the same wellbore as the canonical form.
    """
    rng = context.rng(f"traj:{written_name}")
    stations = 40 if context.scale == "ci" else 200
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<trajectorys xmlns="http://www.witsml.org/schemas/1series" version="1.4.1.1">',
        '<trajectory uidWell="W-FIXTURE" uidWellbore="B-FIXTURE" uid="T-FIXTURE">',
        f"<nameWell>{_xml_escape(written_name)}</nameWell>",
        f"<nameWellbore>{_xml_escape(written_name)}</nameWellbore>",
        "<name>Fixture Survey</name>",
        "<aziRef>grid north</aziRef>",
    ]
    md, tvd, inclination = 0.0, 0.0, 0.0
    for index in range(stations):
        md += 30.0
        inclination = min(88.0, inclination + rng.uniform(0.0, 1.6))
        tvd += 30.0 * max(0.05, (90.0 - inclination) / 90.0)
        parts.append(
            f'<trajectoryStation uid="S-{index}">'
            f"<dTimStn>2020-01-{(index % 28) + 1:02d}T00:00:00.000Z</dTimStn>"
            f'<md uom="m">{md:.2f}</md><tvd uom="m">{tvd:.2f}</tvd>'
            f'<incl uom="dega">{inclination:.2f}</incl>'
            f'<azi uom="dega">{rng.uniform(0, 360):.2f}</azi>'
            f'<dls uom="dega/m">{rng.uniform(0, 0.08):.4f}</dls>'
            "</trajectoryStation>"
        )
    parts.append("</trajectory></trajectorys>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(parts), encoding="utf-8", newline="\n")
    return {"stations": stations, "written_as": written_name, **write_manifest_entry(path)}


# --------------------------------------------------------------------------
# Well picks and perforations — the BR-13 case
# --------------------------------------------------------------------------

def write_well_picks(context: GeneratorContext, path: Path) -> dict:
    """Formation tops and perforation intervals, one crossing two formations.

    Planted case, **BR-13**: the second perforation interval spans the boundary
    between two formations, so mapping it to geology must produce two rows whose
    penetrated lengths sum to the interval length.

    This is the one fixture with no real counterpart: the delivery contains no
    GEOM product at all (docs/data-inventory.md section 6), so there is no real
    schema to imitate. The layout is therefore this project's own, documented
    here and in ADR 006, and it is the only fixture that does not exercise a
    reader used against real data.
    """
    rows = [
        "# fixture well picks and perforations - no real GEOM delivery exists",
        "# wellbore,kind,formation,md_top_m,md_base_m",
        "15/9-X-1,PICK,HUGIN,3050.0,3180.0",
        "15/9-X-1,PICK,SLEIPNER,3180.0,3320.0",
        "15/9-X-1,PERF,,3060.0,3120.0",
        # Crosses the HUGIN/SLEIPNER boundary at 3180: 60 m in HUGIN, 40 m in
        # SLEIPNER, and BR-13 must return both with lengths summing to 100.
        "15/9-X-1,PERF,,3120.0,3220.0",
        "15/9-X-2,PICK,HUGIN,2900.0,3010.0",
        "15/9-X-2,PERF,,2950.0,2990.0",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")
    return {"records": len(rows) - 2, **write_manifest_entry(path)}
