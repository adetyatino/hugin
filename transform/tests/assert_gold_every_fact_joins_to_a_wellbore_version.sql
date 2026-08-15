-- Every production day must find the dimension version valid on it.
--
-- A fact that misses the SCD2 window falls back to a synthetic UNRESOLVED key,
-- which is honest but must not happen for a wellbore the dimension knows about:
-- that would mean the validity ranges have a hole in them.

select
    f.wellbore_uid,
    f.prod_date,
    f.wellbore_key
from {{ ref('fct_production_daily') }} f
where f.wellbore_uid is not null
  and f.wellbore_key not in (select wellbore_key from {{ ref('dim_wellbore') }})
