-- BR-12. A wellbore_uid belongs to exactly one well_code, everywhere.
--
-- Same invariant as the Python-side test over the crosswalk file, asserted
-- again on the warehouse: the two are built by different code from different
-- artefacts, so a disagreement between them is worth catching here.

select
    wellbore_uid,
    count(distinct well_code) as distinct_well_codes
from {{ ref('silver_wellbore_identity') }}
where wellbore_uid is not null
group by wellbore_uid
having count(distinct well_code) > 1
