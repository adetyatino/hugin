{{ config(materialized='table') }}

-- BR-12 crosswalk, promoted from bronze into silver.
--
-- Grain: source_system x source_identifier. Every identity string any source
-- used to name a wellbore appears exactly once, resolved or not. The unresolved
-- ones are not filtered out here: mart_identity_coverage counts them, and a
-- crosswalk that hid its failures would report 100% coverage forever.
--
-- Bronze carries the resolution the ingestion stage performed, so this reads
-- what every bronze table already agrees on rather than re-deriving it.

with all_identities as (
    {% for source_name in [
        'prod_daily', 'prod_monthly', 'las_curve_header', 'trajectory_station',
        'ddr_activity', 'vsp_checkshot', 'witsml_message', 'segy_header'
    ] %}
    select
        _source_system,
        _source_identifier,
        _wellbore_uid,
        _source_file
    from {{ source('bronze', source_name) }}
    where _source_identifier is not null
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
),

deduplicated as (
    select
        _source_system as source_system,
        _source_identifier as source_identifier,
        max(_wellbore_uid) as wellbore_uid,
        min(_source_file) as first_seen_in,
        count(*) as occurrence_count
    from all_identities
    group by _source_system, _source_identifier
)

select
    source_system,
    source_identifier,
    wellbore_uid,
    -- The canonical name carries the sidetrack after a space: '15/9-F-15 D' is
    -- well '15/9-F-15', sidetrack 'D'. Splitting here rather than in every
    -- consumer keeps one definition of what a well is.
    case
        when wellbore_uid is null then null
        when {{ hugin_strpos('wellbore_uid', "' '") }} > 0
            then substr(wellbore_uid, 1, {{ hugin_strpos('wellbore_uid', "' '") }} - 1)
        else wellbore_uid
    end as well_code,
    case
        when wellbore_uid is null then null
        when {{ hugin_strpos('wellbore_uid', "' '") }} > 0
            then substr(wellbore_uid, {{ hugin_strpos('wellbore_uid', "' '") }} + 1)
        else null
    end as sidetrack_code,
    case when wellbore_uid is null then false else true end as is_resolved,
    first_seen_in,
    occurrence_count
from deduplicated
