-- BR-08. No sample keeps a value equal to the sentinel its own file declared.
--
-- The comparison is against the per-file sentinel, not a constant: the delivery
-- declares -999.25, -9999, -999.2500 and -999.25000, each in the file that uses
-- it. A test written against the constant would pass while three of the four
-- spellings sailed through as measurements.

select
    source_file,
    curve_mnemonic,
    sentinel_declared,
    curve_value,
    count(*) as surviving_sentinel_rows
from {{ ref('silver_log_sample') }}
where curve_value is not null
  and sentinel_declared is not null
  and curve_value = {{ hugin_to_number('sentinel_declared') }}
group by source_file, curve_mnemonic, sentinel_declared, curve_value
