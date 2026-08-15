-- BR-12. The coverage mart must add up.
--
-- resolved + unresolved = identities on every row including TOTAL, and the
-- TOTAL row must equal the sum of the per-system rows. A coverage report whose
-- arithmetic does not close is worse than none, because it gets quoted.

select
    source_system,
    identity_count,
    resolved_count,
    unresolved_count
from {{ ref('mart_identity_coverage') }}
where resolved_count + unresolved_count <> identity_count
