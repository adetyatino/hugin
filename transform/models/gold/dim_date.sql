{{ config(materialized='table') }}

-- Grain: one row per calendar day. Static, covering field life from SPEC.md
-- section 2 rather than whatever range happens to have been loaded, so a join
-- against it never silently drops a fact for a day nobody ingested yet.

with spine as (
    {{ hugin_date_spine(var('field_start'), var('field_end')) }}
)

select
    cast({{ hugin_date_key('calendar_date') }} as integer) as date_key,
    calendar_date,
    cast(extract(year from calendar_date) as integer) as calendar_year,
    cast(extract(month from calendar_date) as integer) as calendar_month,
    cast(extract(day from calendar_date) as integer) as calendar_day,
    cast({{ hugin_month_key('calendar_date') }} as integer) as month_key,
    cast(extract(quarter from calendar_date) as integer) as calendar_quarter
from spine
