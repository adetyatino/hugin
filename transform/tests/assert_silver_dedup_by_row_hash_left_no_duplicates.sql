-- Silver deduplicates by _row_hash. This proves it worked rather than that the
-- source happened to be free of repeats: a re-ingested batch produces identical
-- hashes by design, so a duplicate here means the dedup is wrong.

select _row_hash, count(*) as row_count
from {{ ref('silver_production_daily') }}
group by _row_hash
having count(*) > 1
