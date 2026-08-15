-- BR-12. No identity is lost between bronze and silver.
--
-- The rule is that an identity nothing can resolve is *kept* with a NULL
-- wellbore_uid, never filtered out. So the test compares the two layers: every
-- (source_system, source_identifier) that bronze saw must reach silver,
-- resolved or not.
--
-- An earlier version of this test asserted that unresolved identities *exist*.
-- That was wrong: it made a property of today's data into a rule, and it would
-- start failing the day the crosswalk got good enough to resolve everything —
-- which is the opposite of what BR-12 wants to protect.

with bronze_identities as (
    {% for source_name in [
        'prod_daily', 'prod_monthly', 'las_curve_header', 'trajectory_station',
        'ddr_activity', 'vsp_checkshot', 'witsml_message', 'segy_header'
    ] %}
    select distinct _source_system as source_system, _source_identifier as source_identifier
    from {{ source('bronze', source_name) }}
    where _source_identifier is not null
    {% if not loop.last %}union{% endif %}
    {% endfor %}
),

silver_identities as (
    select source_system, source_identifier
    from {{ ref('silver_wellbore_identity') }}
)

select
    b.source_system,
    b.source_identifier
from bronze_identities b
left join silver_identities s
    on b.source_system = s.source_system
   and b.source_identifier = s.source_identifier
where s.source_identifier is null
