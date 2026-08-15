-- Exactly one current version per wellbore. Zero means the chain is broken and
-- a current-state query returns nothing; two means it returns double.

select
    wellbore_uid,
    sum(case when is_current then 1 else 0 end) as current_versions
from {{ ref('dim_wellbore') }}
group by wellbore_uid
having sum(case when is_current then 1 else 0 end) <> 1
