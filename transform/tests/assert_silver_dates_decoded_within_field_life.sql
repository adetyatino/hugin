-- The dual date encoding, checked at the far end.
--
-- Daily rows decode an Excel serial; monthly rows compose a key from separate
-- Year and Month columns. If either decoding were wrong the dates would land
-- outside the field's producing life - the kind of error that is invisible in
-- one row and obvious across a range.

select 'daily' as source_grain, count(*) as bad_rows
from {{ ref('silver_production_daily') }}
where prod_date < date '2007-01-01' or prod_date > date '2017-12-31'
having count(*) > 0

union all

select 'monthly' as source_grain, count(*) as bad_rows
from {{ ref('silver_production_monthly') }}
where year_month < 200701 or year_month > 201712
having count(*) > 0
