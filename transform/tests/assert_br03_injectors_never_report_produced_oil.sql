-- BR-03. sum(oil_sm3) for an injector must be zero across all history.
--
-- The source does report stray volumes against injectors; silver zeroes them
-- out of the production columns while keeping the raw figure in
-- reported_oil_sm3. So this proves the separation held, not that the source was
-- tidy.

select
    wellbore_uid,
    sum(oil_sm3) as total_oil_sm3,
    sum(gas_sm3) as total_gas_sm3,
    count(*) as day_count
from {{ ref('silver_production_daily') }}
where is_injector
group by wellbore_uid
having sum(oil_sm3) <> 0 or sum(gas_sm3) <> 0
