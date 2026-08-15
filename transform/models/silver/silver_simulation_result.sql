{{ config(materialized='table') }}

-- Grain: sim_date x row_label x phase. One row per phase per labelled line of
-- each Eclipse balance page.
--
-- SPEC.md section 4.2 puts silver.simulation_result at wellbore x date x phase.
-- This delivery's print file reports field totals, not per-well allocation, so
-- wellbore_uid is NULL throughout and the grain is field-level. That is a
-- property of the data rather than a shortcut: attributing a field total to a
-- wellbore would be inventing the split.
--
-- The page is unpivoted into one row per phase, because 'oil, water and gas in
-- three columns' is a report layout, not a fact table.

with bronze_rows as (
    select * from {{ source('bronze', 'sim_summary') }}
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
),

typed as (
    select
        try_cast(report_date as date) as sim_date,
        cast({{ hugin_to_number('report_number') }} as integer) as report_number,
        {{ hugin_to_number('days_from_start') }} as days_from_start,
        model_name,
        simulator_version,
        row_label,
        {{ hugin_to_number('oil_total') }} as oil_sm3,
        {{ hugin_to_number('water_total') }} as water_sm3,
        {{ hugin_to_number('gas_total') }} as gas_sm3,
        {{ hugin_to_number('pav_bara') }} as average_pressure_bara,
        _row_hash
    from deduplicated
    where report_date is not null
)

select sim_date, report_number, days_from_start, model_name, simulator_version,
       row_label, 'OIL' as phase, oil_sm3 as simulated_volume_sm3,
       average_pressure_bara, _row_hash
from typed
union all
select sim_date, report_number, days_from_start, model_name, simulator_version,
       row_label, 'WATER' as phase, water_sm3 as simulated_volume_sm3,
       average_pressure_bara, _row_hash
from typed
union all
select sim_date, report_number, days_from_start, model_name, simulator_version,
       row_label, 'GAS' as phase, gas_sm3 as simulated_volume_sm3,
       average_pressure_bara, _row_hash
from typed
