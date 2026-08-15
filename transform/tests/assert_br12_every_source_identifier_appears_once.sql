-- BR-12. Each (source_system, source_identifier) appears exactly once.
--
-- Nothing counted twice, nothing dropped. dbt-core has no composite uniqueness
-- test, so this is the singular form of one.

select
    source_system,
    source_identifier,
    count(*) as row_count
from {{ ref('silver_wellbore_identity') }}
group by source_system, source_identifier
having count(*) > 1
