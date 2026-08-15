-- BR-02. The flag must agree with the arithmetic it claims to summarise.
--
-- Flags drift from their definition when a tolerance changes in one place and
-- not the other. This recomputes the comparison from the stored variances and
-- the stored tolerance, so the flag cannot silently disagree with the numbers
-- printed beside it.

select
    wellbore_uid,
    month_key,
    oil_variance_fraction,
    gas_variance_fraction,
    water_variance_fraction,
    tolerance_fraction,
    is_out_of_tolerance
from {{ ref('mart_allocation_reconciliation') }}
where is_out_of_tolerance <> (
    missing_from_daily
    or missing_from_monthly
    or abs(coalesce(oil_variance_fraction, 0)) > tolerance_fraction
    or abs(coalesce(gas_variance_fraction, 0)) > tolerance_fraction
    or abs(coalesce(water_variance_fraction, 0)) > tolerance_fraction
)
