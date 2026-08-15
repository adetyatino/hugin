{{ config(materialized='table') }}

-- Grain: one row per curve_mnemonic. SCD1.
--
-- The unit is the interesting column: the same mnemonic is logged in different
-- units by different service companies, and a fact table keyed on the mnemonic
-- alone would average metres with feet. distinct_unit_count above one is a
-- warning that any aggregate over that curve needs the unit in its group.

with curves as (
    select
        curve_mnemonic,
        count(distinct curve_unit) as distinct_unit_count,
        min(curve_unit) as unit_example,
        min(curve_description) as curve_description,
        count(distinct source_file) as file_count,
        count(distinct wellbore_uid) as wellbore_count
    from {{ ref('silver_log_curve') }}
    where curve_mnemonic is not null and curve_mnemonic <> ''
    group by curve_mnemonic
)

select
    {{ hugin_surrogate_key(['curve_mnemonic']) }} as curve_key,
    curve_mnemonic,
    unit_example as curve_unit,
    curve_description,
    distinct_unit_count,
    file_count,
    wellbore_count,
    case when distinct_unit_count > 1 then true else false end as has_mixed_units
from curves
