{{ config(materialized='table') }}

-- Grain: wellbore_uid x prod_date. One row per wellbore per production day.
--
-- This is where bronze's varchar becomes typed data, and where the cleaning
-- SPEC.md section 3 forbids in bronze happens instead:
--
--   * the Excel serial in dateprd becomes a date (the replay date is a
--     different thing and is kept alongside it),
--   * every measure becomes a double through hugin_to_number, which also
--     absorbs a decimal comma,
--   * duplicates are removed by _row_hash,
--   * production and injection are separated (BR-03),
--   * choke size is normalised to percent (BR-05).
--
-- Production and injection are deliberately not summed. BR-03 exists because a
-- cubic metre of water pushed into an injector is not production, and a model
-- that added them would make that error unrecoverable downstream.

with bronze_rows as (
    select * from {{ source('bronze', 'prod_daily') }}
),

-- Dedup by _row_hash. The hash covers the business columns only, so a row
-- re-ingested by a later batch collapses onto the first rather than
-- duplicating. Ordering by _ingested_at keeps the choice deterministic.
deduplicated as (
    select *
    from (
        select
            bronze_rows.*,
            row_number() over (
                partition by _row_hash
                order by _ingested_at, _batch_id
            ) as row_rank
        from bronze_rows
    ) ranked
    where row_rank = 1
),

typed as (
    select
        _wellbore_uid as wellbore_uid,
        _source_identifier as source_identifier,
        {{ hugin_date_from_excel_serial('dateprd') }} as prod_date,
        try_cast(_replay_date as date) as replay_date,
        npd_well_bore_code as npd_wellbore_code,
        npd_well_bore_name as npd_wellbore_name,
        npd_facility_code as facility_code,
        npd_facility_name as facility_name,
        flow_kind,
        well_type,
        {{ hugin_to_number('on_stream_hrs') }} as on_stream_hours,
        {{ hugin_to_number('bore_oil_vol') }} as bore_oil_sm3,
        {{ hugin_to_number('bore_gas_vol') }} as bore_gas_sm3,
        {{ hugin_to_number('bore_wat_vol') }} as bore_water_sm3,
        {{ hugin_to_number('bore_wi_vol') }} as bore_water_inj_sm3,
        {{ hugin_to_number('avg_downhole_pressure') }} as dh_pressure_bar,
        {{ hugin_to_number('avg_downhole_temperature') }} as dh_temperature_c,
        {{ hugin_to_number('avg_whp_p') }} as whp_bar,
        {{ hugin_to_number('avg_wht_p') }} as wht_c,
        {{ hugin_to_number('avg_annulus_press') }} as annulus_pressure_bar,
        {{ hugin_to_number('avg_dp_tubing') }} as dp_tubing_bar,
        {{ hugin_to_number('avg_choke_size_p') }} as choke_size_raw,
        avg_choke_uom as choke_uom_raw,
        {{ hugin_to_number('dp_choke_size') }} as dp_choke_size,
        _row_hash,
        _source_file
    from deduplicated
)

select
    wellbore_uid,
    source_identifier,
    prod_date,
    replay_date,
    npd_wellbore_code,
    npd_wellbore_name,
    facility_code,
    facility_name,
    flow_kind,
    well_type,
    -- BR-03. WELL_TYPE is the source's own classification: OP produces, WI
    -- injects water. It is carried through rather than inferred from whether a
    -- volume happens to be zero, because a producer shut in for a month is not
    -- an injector.
    case when upper(coalesce(well_type, '')) = 'WI' then true else false end as is_injector,
    on_stream_hours,
    -- BR-03: a producer's volumes are production, an injector's are not. The
    -- split follows the well type, so an injector reporting a stray oil volume
    -- contributes zero production while the raw figure stays visible in
    -- reported_oil_sm3 for anyone auditing it.
    case when upper(coalesce(well_type, '')) = 'WI' then 0.0 else coalesce(bore_oil_sm3, 0.0) end as oil_sm3,
    case when upper(coalesce(well_type, '')) = 'WI' then 0.0 else coalesce(bore_gas_sm3, 0.0) end as gas_sm3,
    case when upper(coalesce(well_type, '')) = 'WI' then 0.0 else coalesce(bore_water_sm3, 0.0) end as water_sm3,
    coalesce(bore_water_inj_sm3, 0.0) as water_inj_sm3,
    bore_oil_sm3 as reported_oil_sm3,
    bore_gas_sm3 as reported_gas_sm3,
    bore_water_sm3 as reported_water_sm3,
    dh_pressure_bar,
    dh_temperature_c,
    whp_bar,
    wht_c,
    annulus_pressure_bar,
    dp_tubing_bar,
    -- BR-05: choke size normalised to percent. The unit is written per row in
    -- AVG_CHOKE_UOM, so the conversion reads it rather than assuming one.
    case
        when choke_size_raw is null then null
        when upper(coalesce(choke_uom_raw, '%')) in ('%', 'PCT', 'PERCENT') then choke_size_raw
        when upper(choke_uom_raw) in ('FRAC', 'FRACTION') then choke_size_raw * 100.0
        else null
    end as choke_pct,
    choke_size_raw,
    choke_uom_raw,
    dp_choke_size,
    _row_hash,
    _source_file
from typed
where prod_date is not null
