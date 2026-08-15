-- dim_wellbore is SCD2, so a wellbore has exactly one version valid on any
-- date. Overlapping validity is the classic SCD2 defect: every fact joining
-- through it silently doubles.

select
    a.wellbore_uid,
    a.version_number as version_a,
    b.version_number as version_b,
    a.valid_from as a_valid_from,
    a.valid_to as a_valid_to,
    b.valid_from as b_valid_from
from {{ ref('dim_wellbore') }} a
join {{ ref('dim_wellbore') }} b
    on a.wellbore_uid = b.wellbore_uid
   and a.version_number < b.version_number
where a.valid_to is null
   or a.valid_to > b.valid_from
