{{ config(materialized='table') }}

-- BR-04, the quarantine side.
--
-- Grain: wellbore_uid x prod_date x violation. One row per rule a production
-- day breaks, so a day breaking two rules appears twice and both are visible.
--
-- The rule: on_stream_hours = 0 means every production volume is zero, and any
-- volume above zero means on_stream_hours is above zero. A day that says it
-- produced 400 Sm3 while flowing for no hours is describing something that did
-- not happen — most likely an allocation adjustment posted to the wrong day.
--
-- SPEC.md section 5 is explicit that violations are quarantined rather than
-- dropped. The rows stay in silver_production_daily; this model is a register
-- of what to distrust, not a filter. Deleting them would make the daily total
-- disagree with the monthly report for a reason nobody could reconstruct.

with daily as (
    select * from {{ ref('silver_production_daily') }}
),

violations as (
    select
        wellbore_uid,
        prod_date,
        'volume_without_uptime' as violation,
        'reports production volume but zero on-stream hours' as violation_detail,
        on_stream_hours,
        oil_sm3,
        gas_sm3,
        water_sm3,
        water_inj_sm3,
        _row_hash
    from daily
    where coalesce(on_stream_hours, 0) = 0
      and (coalesce(oil_sm3, 0) > 0 or coalesce(gas_sm3, 0) > 0 or coalesce(water_sm3, 0) > 0)

    union all

    select
        wellbore_uid,
        prod_date,
        'uptime_without_volume' as violation,
        'reports on-stream hours but no produced or injected volume' as violation_detail,
        on_stream_hours,
        oil_sm3,
        gas_sm3,
        water_sm3,
        water_inj_sm3,
        _row_hash
    from daily
    where coalesce(on_stream_hours, 0) > 0
      and coalesce(oil_sm3, 0) = 0
      and coalesce(gas_sm3, 0) = 0
      and coalesce(water_sm3, 0) = 0
      and coalesce(water_inj_sm3, 0) = 0

    union all

    select
        wellbore_uid,
        prod_date,
        'uptime_out_of_range' as violation,
        'on-stream hours outside 0..24 for a single day' as violation_detail,
        on_stream_hours,
        oil_sm3,
        gas_sm3,
        water_sm3,
        water_inj_sm3,
        _row_hash
    from daily
    where on_stream_hours is not null
      and (on_stream_hours < 0 or on_stream_hours > 24)
)

select * from violations
