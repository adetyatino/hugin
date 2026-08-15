-- Gold must not lose or invent a production day. A join that fans out is the
-- usual cause, and it shows up as a fact table larger than its source.

with silver_count as (
    select count(*) as row_count from {{ ref('silver_production_daily') }}
),
gold_count as (
    select count(*) as row_count from {{ ref('fct_production_daily') }}
)

select s.row_count as silver_rows, g.row_count as gold_rows
from silver_count s
cross join gold_count g
where s.row_count <> g.row_count
