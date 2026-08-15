{{ config(materialized='table') }}

-- Grain: wellbore_uid. Drilling performance per wellbore.
--
-- NPT percentage, rate of penetration, connection duration and metres per day -
-- the four numbers a drilling superintendent looks at. All of them derive from
-- fct_drilling_state, so all of them inherit BR-06's thresholds and its
-- measured agreement rate; docs/rig-state-validation.md is the caveat that
-- travels with this table.

with states as (
    select * from {{ ref('fct_drilling_state') }}
),

per_wellbore as (
    select
        wellbore_uid,
        count(*) as state_span_count,
        sum(duration_s) as total_seconds,
        sum(case when is_npt then duration_s else 0 end) as npt_seconds,
        sum(case when state = 'DRILLING' then duration_s else 0 end) as drilling_seconds,
        sum(case when state = 'CONNECTION' then duration_s else 0 end) as connection_seconds,
        sum(case when state = 'CONNECTION' then 1 else 0 end) as connection_count,
        sum(case when state in ('TRIPPING_IN', 'TRIPPING_OUT') then duration_s else 0 end)
            as tripping_seconds,
        sum(case when state = 'DRILLING' then depth_to_m - depth_from_m else 0 end)
            as drilled_m,
        min(started_at) as first_sample_at,
        max(ended_at) as last_sample_at
    from states
    group by wellbore_uid
)

select
    wellbore_uid,
    state_span_count,
    total_seconds,
    npt_seconds,
    drilling_seconds,
    connection_seconds,
    tripping_seconds,
    drilled_m,
    {{ hugin_safe_divide('npt_seconds * 100.0', 'total_seconds') }} as npt_pct,
    {{ hugin_safe_divide('drilling_seconds * 100.0', 'total_seconds') }} as drilling_pct,
    -- Rate of penetration over the time actually spent drilling, not over the
    -- whole run: including trips would report a number no bit ever achieved.
    {{ hugin_safe_divide('drilled_m * 3600.0', 'drilling_seconds') }} as rop_m_per_hour,
    {{ hugin_safe_divide('connection_seconds', 'connection_count') }} as mean_connection_s,
    {{ hugin_safe_divide('drilled_m * 86400.0', 'total_seconds') }} as metres_per_day,
    first_sample_at,
    last_sample_at
from per_wellbore
