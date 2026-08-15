-- BR-04. Quarantine is a register, not a filter.
--
-- SPEC.md section 5: violations are quarantined, not silently discarded. This
-- fails if a quarantined day has been removed from the daily model - which is
-- what quarantine usually means elsewhere and must not mean here, because the
-- daily total has to keep matching what the source reported.

select
    q.wellbore_uid,
    q.prod_date,
    q.violation
from {{ ref('silver_production_quarantine') }} q
left join {{ ref('silver_production_daily') }} d
    on q.wellbore_uid = d.wellbore_uid
   and q.prod_date = d.prod_date
where d.wellbore_uid is null
