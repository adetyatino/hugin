-- BR-05. Choke opening is a percentage after normalisation, so it lies within
-- 0..100 wherever a value survives.
--
-- The unit is written per row in AVG_CHOKE_UOM. A row whose unit the rule does
-- not recognise yields NULL rather than an unconverted number, so a new unit in
-- a future delivery appears as missing data rather than as a choke of 0.87
-- percent.

select
    wellbore_uid,
    prod_date,
    choke_pct,
    choke_size_raw,
    choke_uom_raw
from {{ ref('silver_production_daily') }}
where choke_pct is not null
  and (choke_pct < 0 or choke_pct > 100)
