{{ config(materialized='table') }}

-- Grain: wellbore_key x md_m. One row per survey station along a wellbore.
--
-- northing and easting are the *offsets* the surveying system computed from the
-- well reference point, not projected coordinates: the source declares no CRS,
-- so there is nothing to project into yet. BR-10 fills that in once a real
-- datum is established, and the column names say offset so nobody mistakes them
-- for map coordinates in the meantime.

with stations as (
    select * from {{ ref('silver_trajectory_station') }}
),

wellbore_current as (
    select wellbore_key, wellbore_uid
    from {{ ref('dim_wellbore') }}
    where is_current
),

ranked as (
    select
        s.*,
        row_number() over (
            partition by s.wellbore_uid, s.md_m
            order by s.station_date desc, s.trajectory_uid, s.station_seq
        ) as station_rank
    from stations s
)

select
    coalesce(w.wellbore_key, {{ hugin_surrogate_key(["'UNRESOLVED'", 'r.source_identifier']) }}) as wellbore_key,
    r.wellbore_uid,
    r.trajectory_uid,
    r.station_seq,
    r.station_date,
    r.md_m,
    r.tvd_m,
    r.inclination_deg,
    r.azimuth_deg,
    r.northing_offset_m,
    r.easting_offset_m,
    r.vertical_section_m,
    r.dogleg_severity_deg_per_m,
    r.azi_ref,
    r.source_crs,
    r._row_hash as row_hash
from ranked r
left join wellbore_current w
    on r.wellbore_uid = w.wellbore_uid
where r.station_rank = 1
