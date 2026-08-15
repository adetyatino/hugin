{{ config(materialized='table') }}

-- Grain: one row per facility_code. SCD1.
--
-- The only facility in this delivery is MAERSK INSPIRER, the jack-up that
-- produced Volve. Its name carries a Scandinavian ligature, which is the
-- cheapest end-to-end check that encoding survived ingestion, Parquet, Iceberg
-- and both query engines.

with facilities as (
    select
        facility_code,
        facility_name,
        min(prod_date) as first_seen_date,
        max(prod_date) as last_seen_date,
        count(*) as production_day_count
    from {{ ref('silver_production_daily') }}
    where facility_code is not null
    group by facility_code, facility_name
)

select
    {{ hugin_surrogate_key(['facility_code']) }} as facility_key,
    facility_code,
    facility_name,
    first_seen_date,
    last_seen_date,
    production_day_count
from facilities
