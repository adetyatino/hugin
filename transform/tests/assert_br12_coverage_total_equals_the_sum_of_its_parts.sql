-- BR-12. The TOTAL row is the sum of the per-system rows, not an independent
-- count that happens to look similar.

with total_row as (
    select identity_count, resolved_count
    from {{ ref('mart_identity_coverage') }}
    where is_total_row
),

parts as (
    select sum(identity_count) as identity_count, sum(resolved_count) as resolved_count
    from {{ ref('mart_identity_coverage') }}
    where not is_total_row
)

select
    t.identity_count as total_identities,
    p.identity_count as summed_identities,
    t.resolved_count as total_resolved,
    p.resolved_count as summed_resolved
from total_row t
cross join parts p
where t.identity_count <> p.identity_count
   or t.resolved_count <> p.resolved_count
