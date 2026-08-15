{{ config(materialized='table') }}

-- Grain: wellbore_uid x report_date x activity_seq. One row per reported
-- activity within a daily drilling report.
--
-- This is the cross-check BR-06 will be measured against in layer 2: the
-- driller's own account of what the rig was doing, against a classification
-- derived from telemetry. Free-text comments are kept as written, multi-line
-- and all, because they are the evidence.

with bronze_rows as (
    select * from {{ source('bronze', 'ddr_activity') }}
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
    try_cast(report_date as date) as report_date,
    cast({{ hugin_to_number('activity_seq') }} as integer) as activity_seq,
    npd_code_well,
    npd_code_wellbore,
    npd_number,
    rig_alias as rig_name,
    {{ hugin_date_from_iso('activity_dtim_start') }} as activity_start_date,
    activity_dtim_start as activity_started_at,
    activity_dtim_end as activity_ended_at,
    {{ hugin_to_number('activity_md') }} as activity_md_m,
    activity_md_uom,
    phase,
    proprietary_code as activity_code,
    state as activity_state,
    state_detail_activity as activity_state_detail,
    comments,
    source_format,
    _row_hash
from deduplicated
where report_date is not null
