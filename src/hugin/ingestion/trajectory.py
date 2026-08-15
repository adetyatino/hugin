"""TRAJ — directional surveys from the EDT/EDM (Compass) export.

One row per survey station: measured depth, true vertical depth, inclination,
azimuth and the displacements the surveying system computed. These are the
input to BR-09's minimum-curvature calculation and BR-10's datum transform, so
what this reader does *not* do matters as much as what it does.

**The CRS is read from the source, and this source does not declare one.**
CLAUDE.md forbids assuming a CRS or datum anywhere, and SPEC.md section 2 warns
that Volve-era data is ED50 / UTM 31N while modern systems are WGS84 — hundreds
of metres apart in the North Sea. What the trajectory documents actually
declare is:

    aziRef          'grid north' — the azimuth reference, not a CRS
    magDeclUsed     magnetic declination applied, in dega
    gridCorUsed     grid correction applied, in dega

That is enough to know azimuths are grid-referenced, and not enough to know
which grid. So ``azi_ref``, ``mag_decl_used`` and ``grid_cor_used`` are carried
into bronze as written, and ``source_crs`` is left NULL rather than filled with
a plausible guess. BR-10 needs a real answer before it can transform anything;
a NULL that fails a test is better than an assumption that quietly shifts every
well by a few hundred metres.

Station displacements (``dispNs``, ``dispEw``) are *relative* offsets from the
well reference point, not projected coordinates, so they need no CRS to be
meaningful. The projected coordinates BR-10 produces are silver's business.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path

import pyarrow as pa
from lxml import etree

from hugin.ingestion.base import SourceReader

__all__ = ["TrajectoryStationReader"]

BUSINESS_COLUMNS = (
    "name_well",
    "name_wellbore",
    "trajectory_name",
    "trajectory_uid",
    "uid_well",
    "uid_wellbore",
    "service_company",
    "dtim_traj_start",
    "dtim_traj_end",
    "md_min",
    "md_max",
    "azi_ref",
    "azi_vert_sect",
    "mag_decl_used",
    "grid_cor_used",
    "source_crs",
    "station_uid",
    "station_seq",
    "dtim_station",
    "type_traj_station",
    "status_traj_station",
    "md",
    "md_uom",
    "tvd",
    "tvd_uom",
    "incl",
    "incl_uom",
    "azi",
    "azi_uom",
    "disp_ns",
    "disp_ew",
    "vert_sect",
    "dls",
    "dls_uom",
)

#: Station elements this reader keeps, mapped to their bronze column.
_STATION_FIELDS = {
    "dTimStn": "dtim_station",
    "typeTrajStation": "type_traj_station",
    "statusTrajStation": "status_traj_station",
    "md": "md",
    "tvd": "tvd",
    "incl": "incl",
    "azi": "azi",
    "dispNs": "disp_ns",
    "dispEw": "disp_ew",
    "vertSect": "vert_sect",
    "dls": "dls",
}

#: Elements whose ``uom`` attribute is worth keeping: the ones BR-09 computes
#: with. A dogleg in dega/m and one in dega/30m differ by a factor of 30 - and
#: inclination is worse: four of this delivery's trajectories declare
#: ``uom="rad"`` while the rest declare ``uom="dega"``. Treating 0.371 rad as
#: 0.371 deg puts the shoe 188 m out, and nothing about the number looks wrong.
_UOM_FIELDS = {"md": "md_uom", "tvd": "tvd_uom", "incl": "incl_uom", "azi": "azi_uom", "dls": "dls_uom"}

_HEADER_FIELDS = {
    "nameWell": "name_well",
    "nameWellbore": "name_wellbore",
    "name": "trajectory_name",
    "serviceCompany": "service_company",
    "dTimTrajStart": "dtim_traj_start",
    "dTimTrajEnd": "dtim_traj_end",
    "mdMn": "md_min",
    "mdMx": "md_max",
    "aziRef": "azi_ref",
    "aziVertSect": "azi_vert_sect",
    "magDeclUsed": "mag_decl_used",
    "gridCorUsed": "grid_cor_used",
}


def _local(tag: object) -> str:
    return str(tag).rsplit("}", 1)[-1]


def _station_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


class TrajectoryStationReader(SourceReader):
    """One row per trajectory station."""

    source_system = "TRAJ"
    table = "bronze.trajectory_station"
    business_columns = BUSINESS_COLUMNS
    identifier_column = "name_wellbore"

    def source_files(self) -> list[Path]:
        root = self.settings.landing_dir / "traj"
        if not root.exists():
            return []
        return sorted(p for p in root.rglob("*.xml") if p.is_file())

    def read(self, replay_date: date) -> Iterator[pa.RecordBatch]:
        batcher = self.batcher(replay_date)

        for path in self.source_files():
            for record in self._read_file(path, replay_date):
                yield from batcher.add(record, self.relative(path))

        if batcher.pending:
            yield batcher.flush()

    def _read_file(self, path: Path, replay_date: date) -> Iterator[dict[str, str | None]]:
        try:
            tree = etree.parse(str(path))
        except (etree.XMLSyntaxError, OSError):
            return

        for trajectory in tree.getroot().iter():
            if _local(trajectory.tag) != "trajectory":
                continue

            header: dict[str, str | None] = {name: None for name in BUSINESS_COLUMNS}
            header.update({
                "trajectory_uid": trajectory.get("uid"),
                "uid_well": trajectory.get("uidWell"),
                "uid_wellbore": trajectory.get("uidWellbore"),
                # Left NULL deliberately: the source declares an azimuth
                # reference, not a coordinate reference system. See the module
                # docstring and CLAUDE.md.
                "source_crs": None,
            })

            stations: list[etree._Element] = []
            for child in trajectory:
                tag = _local(child.tag)
                if tag == "trajectoryStation":
                    stations.append(child)
                elif tag in _HEADER_FIELDS:
                    header[_HEADER_FIELDS[tag]] = (child.text or "").strip() or None

            # A survey's start date stands in for stations that carry no time
            # of their own, so a station is never silently undated.
            fallback = _station_date(header["dtim_traj_start"])

            for sequence, station in enumerate(stations, start=1):
                record = dict(header)
                record["station_uid"] = station.get("uid")
                record["station_seq"] = str(sequence)
                for node in station:
                    tag = _local(node.tag)
                    column = _STATION_FIELDS.get(tag)
                    if column is None:
                        continue
                    record[column] = (node.text or "").strip() or None
                    if tag in _UOM_FIELDS:
                        record[_UOM_FIELDS[tag]] = node.get("uom")

                observed = _station_date(record["dtim_station"]) or fallback
                if observed != replay_date:
                    continue
                record["_source_identifier"] = record["name_wellbore"] or record["name_well"]
                yield record
