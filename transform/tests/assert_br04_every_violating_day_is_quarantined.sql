-- BR-04. Every day that breaks the uptime rule is in the quarantine.
--
-- The rule is not "no day breaks it" - days do. The rule is that none is
-- silently dropped, so this looks for a violating day the quarantine does not
-- know about.

with violating_days as (
    select wellbore_uid, prod_date
    from {{ ref('silver_production_daily') }}
    where (
            coalesce(on_stream_hours, 0) = 0
            and (coalesce(oil_sm3, 0) > 0 or coalesce(gas_sm3, 0) > 0 or coalesce(water_sm3, 0) > 0)
          )
       or (on_stream_hours is not null and (on_stream_hours < 0 or on_stream_hours > 24))
),

quarantined as (
    select distinct wellbore_uid, prod_date
    from {{ ref('silver_production_quarantine') }}
)

select v.wellbore_uid, v.prod_date
from violating_days v
left join quarantined q
    on v.wellbore_uid = q.wellbore_uid
   and v.prod_date = q.prod_date
where q.wellbore_uid is null
