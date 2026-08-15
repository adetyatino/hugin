{{ config(materialized='table') }}

-- Grain: wellbore_key x source_file x curve_key x index_value.
--
-- SPEC.md section 4.3 gives the grain as wellbore x run x depth x curve. This
-- delivery has no run identifier, so the source file stands in for the run:
-- one LAS file is one logging pass, which is what a run is. Naming it
-- source_file rather than run_id keeps the substitution visible.
--
-- Sentinels are already NULL by the time rows arrive here (BR-08, applied in
-- silver against each file's own declared value). was_sentinel survives so the
-- count of discarded readings stays available.

with samples as (
    select * from {{ ref('silver_log_sample') }}
),

wellbore_current as (
    select wellbore_key, wellbore_uid
    from {{ ref('dim_wellbore') }}
    where is_current
),

curves as (
    select curve_key, curve_mnemonic
    from {{ ref('dim_curve') }}
)

select
    coalesce(w.wellbore_key, {{ hugin_surrogate_key(["'UNRESOLVED'", 's.source_identifier']) }}) as wellbore_key,
    c.curve_key,
    s.wellbore_uid,
    s.source_file,
    s.curve_mnemonic,
    s.index_mnemonic,
    s.index_value as depth_m,
    s.index_unit as depth_uom,
    s.curve_value as value,
    s.was_sentinel,
    s._row_hash as row_hash
from samples s
left join wellbore_current w
    on s.wellbore_uid = w.wellbore_uid
left join curves c
    on s.curve_mnemonic = c.curve_mnemonic
