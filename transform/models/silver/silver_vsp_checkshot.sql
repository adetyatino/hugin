{{ config(materialized='table') }}

-- Grain: wellbore_uid x tvd_m. Depth/time pairs from the checkshot survey.
--
-- This is BR-09's independent truth: a directly measured relationship between
-- depth and travel time, from a source that knows nothing about the directional
-- survey. Comparing a computed trajectory against it is what separates a
-- minimum-curvature implementation that is tested from one that merely runs.

with bronze_rows as (
    select * from {{ source('bronze', 'vsp_checkshot') }}
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
    curve_name,
    cast({{ hugin_to_number('row_seq') }} as integer) as row_seq,
    {{ hugin_to_number('tvdbtdd') }} as tvd_below_datum_m,
    {{ hugin_to_number('tvd') }} as tvd_m,
    {{ hugin_to_number('tvdss') }} as tvd_subsea_m,
    -- The column is written 'Two Way Time' with no unit declared anywhere in
    -- the file, so the name says what it is and nothing asserts milliseconds.
    {{ hugin_to_number('two_way_time') }} as two_way_time,
    _row_hash
from deduplicated
where {{ hugin_to_number('tvd') }} is not null
