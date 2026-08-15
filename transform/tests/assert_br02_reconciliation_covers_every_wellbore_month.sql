-- BR-02. Every wellbore-month present in either source appears in the
-- reconciliation exactly once.
--
-- The rule this guards is "do not correct either one". A model that quietly
-- dropped the months that disagree, or replaced the monthly figure with the
-- daily sum, would still pass a variance test. It fails this one, because the
-- set of pairs would no longer match the union of the two sources.

with expected as (
    select distinct
        wellbore_uid,
        cast({{ hugin_month_key('prod_date') }} as integer) as month_key
    from {{ ref('silver_production_daily') }}
    where wellbore_uid is not null

    union

    select distinct wellbore_uid, year_month as month_key
    from {{ ref('silver_production_monthly') }}
    where wellbore_uid is not null
),

actual as (
    select wellbore_uid, month_key, count(*) as row_count
    from {{ ref('mart_allocation_reconciliation') }}
    group by wellbore_uid, month_key
)

select
    coalesce(e.wellbore_uid, a.wellbore_uid) as wellbore_uid,
    coalesce(e.month_key, a.month_key) as month_key,
    a.row_count
from expected e
full outer join actual a
    on e.wellbore_uid = a.wellbore_uid
   and e.month_key = a.month_key
where e.wellbore_uid is null
   or a.wellbore_uid is null
   or a.row_count <> 1
