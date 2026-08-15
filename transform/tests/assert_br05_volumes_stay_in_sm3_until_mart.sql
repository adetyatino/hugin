-- BR-05. Gold holds Sm3; the boe conversion happens only in mart.
--
-- Checked by arithmetic rather than by reading the models: if a gold volume had
-- been converted, mart's boe column would no longer equal the gold Sm3 figure
-- times the declared factor. The factor is a dbt variable, so this also fails
-- if it is changed in one place and not the other.

select
    p.wellbore_uid,
    p.prod_date,
    p.oil_sm3,
    p.oil_boe,
    f.oil_sm3 as gold_oil_sm3
from {{ ref('mart_well_performance') }} p
join {{ ref('fct_production_daily') }} f
    on p.wellbore_uid = f.wellbore_uid
   and p.prod_date = f.prod_date
where abs(p.oil_boe - f.oil_sm3 * {{ var('sm3_to_boe') }}) > 0.001
