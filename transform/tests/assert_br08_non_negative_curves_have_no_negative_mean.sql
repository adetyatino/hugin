-- BR-08. Gamma ray and bulk density cannot be negative.
--
-- This is the test that catches a sentinel that got through: a curve whose mean
-- is negative has almost certainly averaged in a -999.25 or a -9999. It is a
-- statement about physics rather than about parsing, which is what makes it a
-- useful second line - it fails even if the sentinel arrives in a spelling
-- nobody anticipated.

select
    curve_mnemonic,
    avg(curve_value) as mean_value,
    min(curve_value) as min_value,
    count(*) as sample_count
from {{ ref('silver_log_sample') }}
where curve_mnemonic in ('GR', 'RHOB', 'GRC', 'GR_EDTC')
  and curve_value is not null
group by curve_mnemonic
having avg(curve_value) < 0
