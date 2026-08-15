{{ config(materialized='table') }}

-- Grain: wellbore_key x date_key. One row per wellbore per production day.
--
-- Every measure carries its unit as a suffix, per SPEC.md section 9: a
-- dimensional quantity without one is treated as unfinished work. Volumes are
-- Sm3 throughout gold; the conversion to boe happens only in mart, with the
-- factor as a dbt variable (BR-05).
--
-- The wellbore key is the SCD2 version current on that production day, so a
-- fact joins to the wellbore as it was described at the time - which is the
-- whole point of versioning the dimension.

with daily as (
    select * from {{ ref('silver_production_daily') }}
),

wellbore_version as (
    select
        wellbore_key,
        wellbore_uid,
        valid_from,
        valid_to
    from {{ ref('dim_wellbore') }}
)

select
    coalesce(w.wellbore_key, {{ hugin_surrogate_key(["'UNRESOLVED'", 'd.source_identifier']) }}) as wellbore_key,
    cast({{ hugin_date_key('d.prod_date') }} as integer) as date_key,
    d.wellbore_uid,
    d.prod_date,
    d.facility_code,
    d.is_injector,
    d.on_stream_hours,
    d.oil_sm3,
    d.gas_sm3,
    d.water_sm3,
    d.water_inj_sm3,
    d.whp_bar,
    d.wht_c,
    d.dh_pressure_bar,
    d.dh_temperature_c,
    d.annulus_pressure_bar,
    d.choke_pct,
    d.replay_date,
    d._row_hash as row_hash
from daily d
left join wellbore_version w
    on d.wellbore_uid = w.wellbore_uid
   and d.prod_date >= w.valid_from
   and (w.valid_to is null or d.prod_date < w.valid_to)
