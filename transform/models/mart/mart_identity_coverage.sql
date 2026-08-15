{{ config(materialized='table') }}

-- BR-12 coverage. Grain: source_system. One row per source system, plus a TOTAL
-- row so the headline number is a query away rather than a calculation.
--
-- This is the model that keeps the identity work honest. Unresolved identities
-- are counted here rather than dropped upstream, so coverage can go down as
-- well as up when a new delivery arrives with names nothing recognises. A
-- crosswalk that filtered its failures would report 100% forever.

with identities as (
    select * from {{ ref('silver_wellbore_identity') }}
),

per_system as (
    select
        source_system,
        count(*) as identity_count,
        sum(case when is_resolved then 1 else 0 end) as resolved_count,
        sum(case when is_resolved then 0 else 1 end) as unresolved_count,
        count(distinct case when is_resolved then wellbore_uid end) as wellbore_count,
        sum(occurrence_count) as row_count
    from identities
    group by source_system
),

totals as (
    select
        'TOTAL' as source_system,
        count(*) as identity_count,
        sum(case when is_resolved then 1 else 0 end) as resolved_count,
        sum(case when is_resolved then 0 else 1 end) as unresolved_count,
        count(distinct case when is_resolved then wellbore_uid end) as wellbore_count,
        sum(occurrence_count) as row_count
    from identities
),

combined as (
    select * from per_system
    union all
    select * from totals
)

select
    source_system,
    identity_count,
    resolved_count,
    unresolved_count,
    wellbore_count,
    row_count,
    {{ hugin_safe_divide('resolved_count * 100.0', 'identity_count') }} as resolved_pct,
    case when source_system = 'TOTAL' then true else false end as is_total_row
from combined
