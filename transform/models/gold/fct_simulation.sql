{{ config(materialized='table') }}

-- Grain: date_key x phase x row_label. Field-level, not per wellbore.
--
-- SPEC.md section 4.3 gives the grain as wellbore x date x phase. The Eclipse
-- print file in this delivery reports field totals only, so there is no
-- wellbore to key on and the column is absent rather than filled with a
-- fabricated split. BR-11 can still compare field totals against summed
-- production; per-well comparison needs a per-well simulation report that was
-- not delivered.

with results as (
    select * from {{ ref('silver_simulation_result') }}
)

select
    cast({{ hugin_date_key('sim_date') }} as integer) as date_key,
    sim_date,
    phase,
    row_label,
    report_number,
    days_from_start,
    model_name,
    simulator_version,
    simulated_volume_sm3,
    average_pressure_bara,
    _row_hash as row_hash
from results
where sim_date is not null
