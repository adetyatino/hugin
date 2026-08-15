{{ config(materialized='table') }}

-- Grain: wellbore_uid x source_file x mnemonic. One row per curve per LAS file.
--
-- This model carries the declared NULL sentinel forward, which is what makes
-- BR-08 possible without reopening the files: silver_log_sample joins to it and
-- compares each value against the sentinel *its own file* declared.
--
-- The delivery declares four spellings of the sentinel - -999.25, -9999,
-- -999.2500, -999.25000 - so the parsed numeric value is what matters, not the
-- string. hugin_to_number does that once, here.

with bronze_rows as (
    select * from {{ source('bronze', 'las_curve_header') }}
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
    _source_file as source_file,
    upper(trim(mnemonic)) as curve_mnemonic,
    mnemonic as curve_mnemonic_raw,
    unit as curve_unit,
    description as curve_description,
    cast({{ hugin_to_number('curve_index') }} as integer) as curve_index,
    upper(trim(coalesce(index_mnemonic, ''))) as index_mnemonic,
    index_unit,
    well_name as well_name_declared,
    field as field_declared,
    company as operator_declared,
    service_company,
    date_declared,
    las_version,
    delimiter_declared,
    -- The sentinel, as text and as a number. The text is kept because it is
    -- what the file says and BR-08's test reports it; the number is what the
    -- comparison uses.
    null_value_declared as sentinel_declared,
    {{ hugin_to_number('null_value_declared') }} as sentinel_value,
    {{ hugin_to_number('start') }} as index_start,
    {{ hugin_to_number('stop') }} as index_stop,
    {{ hugin_to_number('step') }} as index_step,
    _row_hash
from deduplicated
where mnemonic is not null
