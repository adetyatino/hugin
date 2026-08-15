-- BR-02, inverted: this fails when the reconciliation finds *nothing*.
--
-- The brief is explicit that in real data the two figures are rarely identical,
-- and an empty reconciliation means the aggregation is wrong rather than the
-- data clean. Measured on this delivery: 497 wellbore-months, 325 agreeing to
-- the cubic metre, the rest differing and several beyond tolerance.
--
-- Every month agreeing exactly would mean both figures came from the same
-- place, and BR-02 would be comparing a number with itself.

select
    count(*) as total_months,
    sum(case when abs(coalesce(oil_variance_sm3, 0)) > 0.0001 then 1 else 0 end) as months_differing
from {{ ref('mart_allocation_reconciliation') }}
having sum(case when abs(coalesce(oil_variance_sm3, 0)) > 0.0001 then 1 else 0 end) = 0
