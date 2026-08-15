-- BR-03, the other direction: injected volume must never be counted as
-- produced. A day where injection had been folded into production would show
-- produced water above the figure the source reported.

select
    wellbore_uid,
    prod_date,
    water_sm3,
    reported_water_sm3,
    water_inj_sm3
from {{ ref('silver_production_daily') }}
where not is_injector
  and water_sm3 > coalesce(reported_water_sm3, 0) + 0.0001
