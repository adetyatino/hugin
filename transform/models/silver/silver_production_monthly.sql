{{ config(materialized='table') }}

-- Grain: wellbore_uid x year_month. One row per wellbore per reported month.
--
-- The monthly sheet encodes its date as separate integer Year and Month
-- columns where the daily sheet uses an Excel serial. That is the dual date
-- encoding this delivery really has, and it is resolved here rather than by
-- forcing either sheet into the other's shape.
--
-- These are the operator's *reported* figures. They are not a re-aggregation of
-- the daily rows, which is exactly why BR-02 has something to compare.

with bronze_rows as (
    select * from {{ source('bronze', 'prod_monthly') }}
),

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
)

select
    _wellbore_uid as wellbore_uid,
    _source_identifier as source_identifier,
    cast({{ hugin_to_number('year') }} as integer) as prod_year,
    cast({{ hugin_to_number('month') }} as integer) as prod_month,
    cast({{ hugin_to_number('year') }} as integer) * 100
        + cast({{ hugin_to_number('month') }} as integer) as year_month,
    npdcode as npd_wellbore_code,
    {{ hugin_to_number('on_stream') }} as on_stream_hours,
    coalesce({{ hugin_to_number('oil') }}, 0.0) as oil_sm3,
    coalesce({{ hugin_to_number('gas') }}, 0.0) as gas_sm3,
    coalesce({{ hugin_to_number('water') }}, 0.0) as water_sm3,
    -- GI and WI are gas and water injection. The sheet writes the literal
    -- string 'NULL' where a wellbore does not inject, and hugin_to_number turns
    -- that into a real NULL rather than zero: not injecting and injecting
    -- nothing are different statements.
    {{ hugin_to_number('gi') }} as gas_inj_sm3,
    {{ hugin_to_number('wi') }} as water_inj_sm3,
    try_cast(_replay_date as date) as replay_date,
    _row_hash,
    _source_file
from deduplicated
where {{ hugin_to_number('year') }} is not null
  and {{ hugin_to_number('month') }} is not null
