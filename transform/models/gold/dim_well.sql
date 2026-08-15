{{ config(materialized='table') }}

-- Grain: one row per well_code. SCD1 - a well's identity does not change; its
-- wellbores and sidetracks do, and those live in dim_wellbore.

with wells as (
    select
        well_code,
        count(distinct wellbore_uid) as wellbore_count,
        count(distinct case when sidetrack_code is not null then wellbore_uid end) as sidetrack_count,
        count(distinct source_system) as source_system_count
    from {{ ref('silver_wellbore_identity') }}
    where well_code is not null
    group by well_code
)

select
    {{ hugin_surrogate_key(['well_code']) }} as well_key,
    well_code,
    wellbore_count,
    sidetrack_count,
    source_system_count
from wells
