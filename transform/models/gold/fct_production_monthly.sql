{{ config(materialized='table') }}

-- Grain: wellbore_key x month_key. One row per wellbore per reported month.
--
-- These are the operator's reported aggregates, kept separate from the daily
-- fact on purpose. Summing the daily rows would produce a different number -
-- that difference is BR-02, and a single table could not express it.

with monthly as (
    select * from {{ ref('silver_production_monthly') }}
),

wellbore_current as (
    select wellbore_key, wellbore_uid
    from {{ ref('dim_wellbore') }}
    where is_current
)

select
    coalesce(w.wellbore_key, {{ hugin_surrogate_key(["'UNRESOLVED'", 'm.source_identifier']) }}) as wellbore_key,
    m.year_month as month_key,
    m.wellbore_uid,
    m.prod_year,
    m.prod_month,
    m.on_stream_hours,
    m.oil_sm3,
    m.gas_sm3,
    m.water_sm3,
    m.gas_inj_sm3,
    m.water_inj_sm3,
    m._row_hash as row_hash
from monthly m
left join wellbore_current w
    on m.wellbore_uid = w.wellbore_uid
