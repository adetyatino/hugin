{{ config(materialized='table') }}

-- Grain: wellbore_uid x prod_date. Daily performance per wellbore.
--
-- Rates, water cut, GOR and uptime, plus the boe conversion BR-05 confines to
-- mart. The factor is a dbt variable so the number appears once and is visible
-- in the project file rather than buried in a case expression.
--
-- Water cut and GOR are the two ratios that decide when a well is worth
-- producing, and both divide by a quantity that is legitimately zero on a
-- shut-in day. hugin_safe_divide returns NULL rather than failing or, worse,
-- returning zero - a well with no oil does not have a water cut of 0%.

with daily as (
    select * from {{ ref('silver_production_daily') }}
),

with_ratios as (
    select
        wellbore_uid,
        prod_date,
        cast({{ hugin_month_key('prod_date') }} as integer) as month_key,
        is_injector,
        on_stream_hours,
        oil_sm3,
        gas_sm3,
        water_sm3,
        water_inj_sm3,
        oil_sm3 * {{ var('sm3_to_boe') }} as oil_boe,
        {{ hugin_safe_divide('oil_sm3', 'on_stream_hours') }} as oil_rate_sm3_per_hour,
        {{ hugin_safe_divide('water_sm3', 'oil_sm3 + water_sm3') }} as water_cut_fraction,
        {{ hugin_safe_divide('gas_sm3', 'oil_sm3') }} as gas_oil_ratio,
        {{ hugin_safe_divide('on_stream_hours', '24.0') }} as uptime_fraction,
        whp_bar,
        dh_pressure_bar,
        choke_pct
    from daily
)

select
    w.*,
    -- Decline against the same wellbore's first producing day, which is the
    -- comparison a reservoir engineer actually makes. NULL until the well has
    -- produced, rather than a decline of 100% on a day before first oil.
    first_oil.first_oil_sm3,
    {{ hugin_safe_divide('w.oil_sm3 - first_oil.first_oil_sm3', 'first_oil.first_oil_sm3') }}
        as oil_change_from_first_fraction
from with_ratios w
left join (
    select wellbore_uid, min_by(oil_sm3, prod_date) as first_oil_sm3
    from (
        select wellbore_uid, prod_date, oil_sm3
        from {{ ref('silver_production_daily') }}
        where oil_sm3 > 0
    ) producing
    group by wellbore_uid
) first_oil
    on w.wellbore_uid = first_oil.wellbore_uid
