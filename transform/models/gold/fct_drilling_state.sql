{{ config(materialized='table') }}

-- BR-06. Grain: wellbore_key x state_seq. One row per run of consecutive
-- samples sharing a rig state, not one row per sample: a two-hour trip is one
-- fact, and storing it per sample would multiply the table by the logging rate
-- without adding information.
--
-- The classification is the ordered rule from SPEC.md section 5, first match
-- wins. The ordering is not incidental - CONNECTION and STATIC both match a
-- stationary string, DRILLING and CIRCULATING both match a turning one with
-- flow - so a CASE expression is the right shape here precisely because it is
-- ordered.
--
-- The thresholds are SPEC.md's and are not tuned. docs/rig-state-validation.md
-- reports the agreement against the daily drilling reports as measured; SPEC.md
-- forbids adjusting these numbers to improve it.

with samples as (
    select
        wellbore_uid,
        ts,
        bit_depth_m,
        hole_depth_m,
        block_position_m,
        wob_klbf,
        rpm,
        flow_in_lpm
    from {{ source('silver_stream', 'drilling_telemetry') }}
),

with_context as (
    select
        *,
        lag(bit_depth_m) over (partition by wellbore_uid order by ts) as prev_bit_depth_m,
        lag(ts) over (partition by wellbore_uid order by ts) as prev_ts,
        -- Block travel over the trailing ten minutes, which is what separates a
        -- connection from a rig that is simply stopped.
        max(block_position_m) over (
            partition by wellbore_uid order by ts
            range between {{ hugin_minutes_preceding(10) }} and current row
        ) - min(block_position_m) over (
            partition by wellbore_uid order by ts
            range between {{ hugin_minutes_preceding(10) }} and current row
        ) as block_travel_m
    from samples
),

rated as (
    select
        *,
        case
            when prev_ts is null then 0.0
            when {{ hugin_seconds_between('prev_ts', 'ts') }} = 0 then 0.0
            else (bit_depth_m - prev_bit_depth_m) / {{ hugin_seconds_between('prev_ts', 'ts') }}
        end as depth_rate_m_per_s
    from with_context
),

classified as (
    select
        *,
        case
            when coalesce(flow_in_lpm, 0) < 100
             and coalesce(rpm, 0) < 5
             and coalesce(block_travel_m, 0) >= 0.5           then 'CONNECTION'
            when depth_rate_m_per_s < -0.05
             and coalesce(wob_klbf, 0) < 2                    then 'TRIPPING_OUT'
            when depth_rate_m_per_s > 0.05
             and coalesce(wob_klbf, 0) < 2                    then 'TRIPPING_IN'
            when abs(bit_depth_m - hole_depth_m) <= 0.5
             and coalesce(wob_klbf, 0) > 2
             and coalesce(flow_in_lpm, 0) > 1000              then 'DRILLING'
            when coalesce(flow_in_lpm, 0) > 1000
             and abs(depth_rate_m_per_s) < 0.01               then 'CIRCULATING'
            else 'STATIC'
        end as rig_state
    from rated
),

-- Islands and gaps: subtracting a per-state row number from a per-wellbore one
-- gives a constant for each run of the same state.
grouped as (
    select
        *,
        row_number() over (partition by wellbore_uid order by ts)
      - row_number() over (partition by wellbore_uid, rig_state order by ts) as state_group
    from classified
),

spans as (
    select
        wellbore_uid,
        rig_state,
        state_group,
        min(ts) as started_at,
        max(ts) as ended_at,
        min(bit_depth_m) as depth_from_m,
        max(bit_depth_m) as depth_to_m,
        count(*) as sample_count
    from grouped
    group by wellbore_uid, rig_state, state_group
),

sequenced as (
    select
        *,
        row_number() over (partition by wellbore_uid order by started_at) as state_seq,
        {{ hugin_seconds_between('started_at', 'ended_at') }} as duration_s
    from spans
)

select
    coalesce(w.wellbore_key, {{ hugin_surrogate_key(["'UNRESOLVED'", 's.wellbore_uid']) }}) as wellbore_key,
    s.wellbore_uid,
    s.state_seq,
    s.rig_state as state,
    s.started_at,
    s.ended_at,
    s.duration_s,
    s.depth_from_m,
    s.depth_to_m,
    s.sample_count,
    -- BR-06: STATIC for more than 30 minutes is non-productive time.
    case when s.rig_state = 'STATIC' and s.duration_s > 1800 then true else false end as is_npt
from sequenced s
left join (select wellbore_key, wellbore_uid from {{ ref('dim_wellbore') }} where is_current) w
    on s.wellbore_uid = w.wellbore_uid
