{{ config(materialized='table') }}

-- Grain: wellbore_uid x version. SCD Type 2, built by the hugin_scd2 macro.
--
-- SPEC.md section 4.3 makes this dimension SCD2 to track "changes of operator
-- label and well role". Both are tracked here, but only one of them is dated in
-- this delivery, and the difference is worth stating plainly:
--
--   * **Well role is dated and really changes.** Production records each day's
--     WELL_TYPE, and 15/9-F-5 appears as OP on some days and WI on others - the
--     wellbore was converted from producer to water injector. That is a real
--     SCD2 event with real dates, and it is what makes this dimension more than
--     a decoration.
--   * **Operator label is not dated.** The labels this dataset carries -
--     Statoil, StatoilHydro, STATOIL PETROLEUM AS - come from LAS headers and
--     archive names, none of which say when the label applied. So the label is
--     attached to the wellbore and *tracked* by the same mechanism: the moment
--     a dated source disagrees, the macro emits a new version without any
--     change here. Inventing dates for the Statoil/StatoilHydro transition
--     would be fabricating history to make a dimension look richer.
--
-- Versions carrying identical tracked values are collapsed, so a wellbore
-- reported unchanged for eight years is one row, not three thousand.

with role_assertions as (
    select
        wellbore_uid,
        prod_date as asserted_on,
        case
            when upper(coalesce(well_type, '')) = 'WI' then 'INJECTOR'
            when upper(coalesce(well_type, '')) = 'OP' then 'PRODUCER'
            else 'UNKNOWN'
        end as well_role
    from {{ ref('silver_production_daily') }}
    where wellbore_uid is not null
),

-- One operator label per wellbore, from the LAS headers that state one.
--
-- Chosen by how often each spelling appears, not alphabetically. The delivery
-- contains 'STATOIL PETROLEUM AS' and 'STATOIL PETRPOLEUM AS' - the second is a
-- typo in the source - and an alphabetical pick would enshrine whichever sorted
-- first rather than whichever the files mostly say. Placeholders and blanks are
-- excluded: 'XXXXX' and an empty string are the absence of a label, and an
-- empty string sorts before every real one.
label_counts as (
    select
        wellbore_uid,
        operator_declared,
        count(*) as label_row_count
    from {{ ref('silver_log_curve') }}
    where wellbore_uid is not null
      and operator_declared is not null
      and trim(operator_declared) <> ''
      and upper(trim(operator_declared)) not in ('XXXXX', 'UNKNOWN', 'NA', 'N/A')
    group by wellbore_uid, operator_declared
),

ranked_labels as (
    select
        wellbore_uid,
        operator_declared,
        row_number() over (
            partition by wellbore_uid
            order by label_row_count desc, operator_declared
        ) as label_rank,
        count(*) over (partition by wellbore_uid) as operator_labels_seen
    from label_counts
),

operator_labels as (
    select
        wellbore_uid,
        operator_declared as operator_label,
        operator_labels_seen
    from ranked_labels
    where label_rank = 1
),

assertions as (
    select
        r.wellbore_uid,
        r.asserted_on,
        r.well_role,
        o.operator_label,
        coalesce(o.operator_labels_seen, 0) as operator_labels_seen
    from role_assertions r
    left join operator_labels o
        on r.wellbore_uid = o.wellbore_uid
),

versions as (
    {{ hugin_scd2(
        relation='assertions',
        business_key='wellbore_uid',
        tracked_columns=['well_role', 'operator_label'],
        order_column='asserted_on',
        surrogate_key='wellbore_key'
    ) }}
),

identity as (
    select
        wellbore_uid,
        max(well_code) as well_code,
        max(sidetrack_code) as sidetrack_code,
        count(distinct source_system) as source_system_count,
        count(*) as identity_variant_count
    from {{ ref('silver_wellbore_identity') }}
    where wellbore_uid is not null
    group by wellbore_uid
)

select
    v.wellbore_key,
    v.business_key as wellbore_uid,
    i.well_code,
    i.sidetrack_code,
    v.version_number,
    v.well_role,
    v.operator_label,
    v.valid_from,
    v.valid_to,
    v.is_current,
    i.source_system_count,
    -- How many different strings named this wellbore across the delivery. The
    -- crosswalk's whole job, visible as a number on the dimension.
    i.identity_variant_count
from versions v
left join identity i
    on v.business_key = i.wellbore_uid
