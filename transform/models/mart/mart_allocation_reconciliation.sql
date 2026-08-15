{{ config(materialized='table') }}

-- BR-02. Grain: wellbore_uid x month_key. One row per wellbore-month present in
-- either the daily or the monthly source.
--
-- The daily rows summed to a month and the operator's reported monthly figure
-- are two different numbers, and this model does not reconcile them - it
-- measures the gap. SPEC.md section 5 is explicit: "do not correct either one,
-- the difference is the information". Allocation back-calculates a well's share
-- of a commingled export stream, and the monthly figure is usually re-allocated
-- after the fact against better metering, so the two disagreeing is normal
-- operational reality rather than a defect.
--
-- Measured on this delivery: 497 wellbore-months, 325 of them agreeing exactly,
-- and a handful outside the +/-2% tolerance with a worst case above 20%. A
-- version of this model that returned nothing would mean the aggregation was
-- wrong, not that the data was clean.
--
-- A full outer join, not an inner one: a month present in only one source is
-- the most serious kind of disagreement, and an inner join would hide it.

with daily_rolled as (
    select
        wellbore_uid,
        cast({{ hugin_month_key('prod_date') }} as integer) as month_key,
        sum(oil_sm3) as daily_oil_sm3,
        sum(gas_sm3) as daily_gas_sm3,
        sum(water_sm3) as daily_water_sm3,
        sum(water_inj_sm3) as daily_water_inj_sm3,
        sum(on_stream_hours) as daily_on_stream_hours,
        count(*) as daily_row_count
    from {{ ref('silver_production_daily') }}
    where wellbore_uid is not null
    group by wellbore_uid, cast({{ hugin_month_key('prod_date') }} as integer)
),

monthly_reported as (
    select
        wellbore_uid,
        year_month as month_key,
        sum(oil_sm3) as monthly_oil_sm3,
        sum(gas_sm3) as monthly_gas_sm3,
        sum(water_sm3) as monthly_water_sm3,
        sum(coalesce(water_inj_sm3, 0)) as monthly_water_inj_sm3,
        sum(on_stream_hours) as monthly_on_stream_hours,
        count(*) as monthly_row_count
    from {{ ref('silver_production_monthly') }}
    where wellbore_uid is not null
    group by wellbore_uid, year_month
),

joined as (
    select
        coalesce(d.wellbore_uid, m.wellbore_uid) as wellbore_uid,
        coalesce(d.month_key, m.month_key) as month_key,
        coalesce(d.daily_oil_sm3, 0) as daily_oil_sm3,
        coalesce(m.monthly_oil_sm3, 0) as monthly_oil_sm3,
        coalesce(d.daily_gas_sm3, 0) as daily_gas_sm3,
        coalesce(m.monthly_gas_sm3, 0) as monthly_gas_sm3,
        coalesce(d.daily_water_sm3, 0) as daily_water_sm3,
        coalesce(m.monthly_water_sm3, 0) as monthly_water_sm3,
        coalesce(d.daily_water_inj_sm3, 0) as daily_water_inj_sm3,
        coalesce(m.monthly_water_inj_sm3, 0) as monthly_water_inj_sm3,
        coalesce(d.daily_on_stream_hours, 0) as daily_on_stream_hours,
        coalesce(m.monthly_on_stream_hours, 0) as monthly_on_stream_hours,
        coalesce(d.daily_row_count, 0) as daily_row_count,
        coalesce(m.monthly_row_count, 0) as monthly_row_count,
        case when d.wellbore_uid is null then true else false end as missing_from_daily,
        case when m.wellbore_uid is null then true else false end as missing_from_monthly
    from daily_rolled d
    full outer join monthly_reported m
        on d.wellbore_uid = m.wellbore_uid
       and d.month_key = m.month_key
),

variances as (
    select
        *,
        daily_oil_sm3 - monthly_oil_sm3 as oil_variance_sm3,
        daily_gas_sm3 - monthly_gas_sm3 as gas_variance_sm3,
        daily_water_sm3 - monthly_water_sm3 as water_variance_sm3,
        -- Relative to the reported monthly figure, which is the number the
        -- operator stands behind. Dividing by the daily sum instead would make
        -- the variance depend on the thing being questioned.
        {{ hugin_safe_divide('daily_oil_sm3 - monthly_oil_sm3', 'monthly_oil_sm3') }} as oil_variance_fraction,
        {{ hugin_safe_divide('daily_gas_sm3 - monthly_gas_sm3', 'monthly_gas_sm3') }} as gas_variance_fraction,
        {{ hugin_safe_divide('daily_water_sm3 - monthly_water_sm3', 'monthly_water_sm3') }} as water_variance_fraction
    from joined
)

select
    wellbore_uid,
    month_key,
    daily_row_count,
    monthly_row_count,
    missing_from_daily,
    missing_from_monthly,
    daily_oil_sm3,
    monthly_oil_sm3,
    oil_variance_sm3,
    oil_variance_fraction,
    daily_gas_sm3,
    monthly_gas_sm3,
    gas_variance_sm3,
    gas_variance_fraction,
    daily_water_sm3,
    monthly_water_sm3,
    water_variance_sm3,
    water_variance_fraction,
    daily_water_inj_sm3,
    monthly_water_inj_sm3,
    daily_on_stream_hours,
    monthly_on_stream_hours,
    -- The flag BR-02 asks for. A month present in only one source is out of
    -- tolerance whatever the volumes say: a missing month is not a small
    -- variance, it is an absence.
    case
        when missing_from_daily or missing_from_monthly then true
        when abs(coalesce(oil_variance_fraction, 0)) > {{ var('allocation_tolerance') }} then true
        when abs(coalesce(gas_variance_fraction, 0)) > {{ var('allocation_tolerance') }} then true
        when abs(coalesce(water_variance_fraction, 0)) > {{ var('allocation_tolerance') }} then true
        else false
    end as is_out_of_tolerance,
    {{ var('allocation_tolerance') }} as tolerance_fraction
from variances
