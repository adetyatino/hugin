-- BR-08. A discarded reading must be countable.
--
-- was_sentinel is what makes the conversion auditable: without it a NULL in
-- curve_value could mean the file said nothing, or that the pipeline threw a
-- reading away, and those are different facts. This fails if a row was flagged
-- as a sentinel while keeping a value, or carries a value with no raw text.

select
    source_file,
    curve_mnemonic,
    value_raw,
    curve_value,
    was_sentinel
from {{ ref('silver_log_sample') }}
where (was_sentinel and curve_value is not null)
   or (curve_value is not null and value_raw is null)
