{{ config(materialized='table') }}

-- Grain: wellbore_uid x trajectory_uid x md_m. One row per survey station.
--
-- source_crs stays NULL because the source declares no CRS - only an azimuth
-- reference of 'grid north' with the magnetic declination and grid correction
-- applied. CLAUDE.md forbids assuming one, so BR-10 has to obtain a real answer
-- before it can transform anything, and a NULL that fails a test is better than
-- an assumption that shifts every well several hundred metres.

with bronze_rows as (
    select * from {{ source('bronze', 'trajectory_station') }}
),

deduplicated as (
    select *
    from (
        select
            bronze_rows.*,
            row_number() over (partition by _row_hash order by _ingested_at, _batch_id) as row_rank
        from bronze_rows
    ) ranked
    where row_rank = 1
)

select
    _wellbore_uid as wellbore_uid,
    _source_identifier as source_identifier,
    trajectory_uid,
    trajectory_name,
    station_uid,
    cast({{ hugin_to_number('station_seq') }} as integer) as station_seq,
    {{ hugin_date_from_iso('dtim_station') }} as station_date,
    type_traj_station,
    status_traj_station,
    {{ hugin_to_number('md') }} as md_m,
    {{ hugin_to_number('tvd') }} as tvd_m,
    {{ hugin_to_number('incl') }} as inclination_deg,
    {{ hugin_to_number('azi') }} as azimuth_deg,
    {{ hugin_to_number('disp_ns') }} as northing_offset_m,
    {{ hugin_to_number('disp_ew') }} as easting_offset_m,
    {{ hugin_to_number('vert_sect') }} as vertical_section_m,
    {{ hugin_to_number('dls') }} as dogleg_severity_deg_per_m,
    md_uom,
    tvd_uom,
    dls_uom,
    azi_ref,
    {{ hugin_to_number('mag_decl_used') }} as magnetic_declination_deg,
    {{ hugin_to_number('grid_cor_used') }} as grid_correction_deg,
    source_crs,
    service_company,
    _row_hash
from deduplicated
where {{ hugin_to_number('md') }} is not null
