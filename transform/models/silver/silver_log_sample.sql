{{ config(materialized='table') }}

-- BR-08. Grain: wellbore_uid x source_file x curve_mnemonic x index_value.
--
-- The sentinel becomes a true NULL here, and the value it is compared against
-- comes from the curve metadata this sample's own file declared - never from a
-- constant. The delivery declares -999.25, -9999, -999.2500 and -999.25000,
-- each in the file that uses it, so code comparing against the constant
-- '-999.25' would carry three of them through as measurements. A depth reading
-- of -9999 does not look wrong in an average until the average is wrong.
--
-- Two sentinel sources are honoured, in this order:
--   1. the sentinel on the sample row, written there at ingest,
--   2. the sentinel on the curve header for the same file, joined here.
-- They agree in this delivery; the join is what makes the model still correct
-- if a future reader stops denormalising it onto the sample.

with samples as (
    select * from {{ source('bronze', 'las_sample') }}
),

deduplicated as (
    select *
    from (
        select
            samples.*,
            row_number() over (
                partition by _row_hash
                order by _ingested_at, _batch_id
            ) as row_rank
        from samples
    ) ranked
    where row_rank = 1
),

-- One sentinel per file. The header rows repeat it per curve, and taking the
-- max of a single distinct value is just the cheapest way to collapse them.
file_sentinel as (
    select
        source_file,
        max(sentinel_declared) as file_sentinel_declared,
        max(sentinel_value) as file_sentinel_value
    from {{ ref('silver_log_curve') }}
    group by source_file
),

joined as (
    select
        d._wellbore_uid as wellbore_uid,
        d._source_identifier as source_identifier,
        d._source_file as source_file,
        upper(trim(d.mnemonic)) as curve_mnemonic,
        upper(trim(coalesce(d.index_mnemonic, ''))) as index_mnemonic,
        d.index_unit,
        d.index_value as index_value_raw,
        d.value as value_raw,
        coalesce(d.null_value_declared, f.file_sentinel_declared) as sentinel_declared,
        d._row_hash,
        d._replay_date
    from deduplicated d
    left join file_sentinel f
        on d._source_file = f.source_file
)

select
    wellbore_uid,
    source_identifier,
    source_file,
    curve_mnemonic,
    index_mnemonic,
    index_unit,
    {{ hugin_to_number('index_value_raw') }} as index_value,
    -- The conversion BR-08 is about. Anything equal to the declared sentinel,
    -- and the NaN lasio substitutes for it when reading LAS 2.0, becomes NULL.
    {{ hugin_null_if_sentinel('value_raw', 'sentinel_declared') }} as curve_value,
    value_raw,
    sentinel_declared,
    -- Kept so the quantity of discarded readings is countable rather than
    -- inferred from the absence of rows.
    case
        when {{ hugin_null_if_sentinel('value_raw', 'sentinel_declared') }} is null
             and value_raw is not null
            then true
        else false
    end as was_sentinel,
    try_cast(_replay_date as date) as replay_date,
    _row_hash
from joined
